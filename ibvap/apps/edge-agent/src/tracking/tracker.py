"""
Tracking layer: Tracker protocol, ByteTrackTracker, MockTracker.

Rules:
  - Tracker state is PER CAMERA SESSION. Reset on every reconnect.
  - track_id values are not globally unique — they are local to one session.
  - Never share tracker state across cameras.
  - Callers only see the Track domain model, never Ultralytics internals.

Design decision (Phase 1, Option A):
  ByteTrackTracker uses Ultralytics' built-in tracker with persist=True.
  The YOLO model is called ONCE per frame with tracking enabled, which
  replaces the separate Detector call. The CameraPipeline detects whether
  tracking mode is active and skips the standalone detector accordingly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import numpy as np

from src.observability.logging import get_logger
from src.observability.metrics import metrics

try:
    from ibvap_contracts.models.detection import BoundingBox, Detection
    from ibvap_contracts.models.track import Track
except ImportError:
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.models.detection import BoundingBox, Detection  # type: ignore[no-redef]
    from ibvap_contracts.models.track import Track  # type: ignore[no-redef]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tracker Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Tracker(Protocol):
    """
    Protocol for multi-object trackers.

    update() accepts the current frame and the detections for that frame.
    It returns the current set of active Track objects.

    reset() must be called when the camera stream session changes (reconnect).
    """

    def update(self, frame: np.ndarray, detections: list[Detection]) -> list[Track]: ...

    def reset(self) -> None:
        """Discard all tracking state. Call on stream reconnect."""
        ...


# ---------------------------------------------------------------------------
# MockTracker — deterministic, no model needed
# ---------------------------------------------------------------------------


class MockTracker:
    """
    Assigns sequential integer IDs to each detection.
    Maintains minimal state to simulate persistent IDs within a session.

    Used for CI and geometry/event layer tests that don't need real tracking.
    """

    def __init__(self) -> None:
        self._next_id = 1
        # Key is (class_name, grid_x, grid_y) — coarse spatial identity
        self._active: dict[tuple[str, int, int], int] = {}

    def update(self, frame: np.ndarray, detections: list[Detection]) -> list[Track]:
        now = datetime.now(tz=UTC)
        tracks: list[Track] = []

        for det in detections:
            # Use a coarse grid cell as a simple identity proxy
            grid_x = int(det.bbox.center_x * 5)
            grid_y = int(det.bbox.center_y * 5)
            key = (det.class_name, grid_x, grid_y)

            if key not in self._active:
                self._active[key] = self._next_id
                self._next_id += 1

            tid = self._active[key]
            track = Track(
                track_id=tid,
                camera_id=det.camera_id,
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                first_seen=now,
                last_seen=now,
                trajectory=[(det.bbox.foot_x, det.bbox.foot_y)],
            )
            tracks.append(track)

        metrics.active_tracks.set(float(len(tracks)))
        return tracks

    def reset(self) -> None:
        self._active.clear()
        self._next_id = 1
        logger.info("mock_tracker_reset")


# ---------------------------------------------------------------------------
# ByteTrackTracker — wraps Ultralytics ByteTrack (Option A)
#
# Single YOLO call with persist=True replaces both detector and tracker.
# The Detector's output is IGNORED when ByteTrackTracker is active;
# instead, the tracker calls YOLO once with tracking enabled.
# ---------------------------------------------------------------------------


class ByteTrackTracker:
    """
    Wraps Ultralytics YOLO + ByteTrack for combined detection+tracking.

    Option A design: a single YOLO call with persist=True and
    tracker="bytetrack.yaml" produces both detections and track IDs,
    eliminating the double-inference problem.

    The `detections` parameter in update() is accepted for Protocol
    compatibility but is not used — the tracker runs its own YOLO call.
    The CameraPipeline uses `tracker.has_builtin_detector` to skip the
    standalone detector when ByteTrackTracker is active.
    """

    # Flag so the pipeline knows not to call the standalone detector
    has_builtin_detector: bool = True

    def __init__(
        self,
        model_path: str = "models/yolo26n.pt",
        device: str = "cpu",
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.50,
        image_size: int = 640,
        allowed_classes: list[str] | None = None,
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._conf = confidence_threshold
        self._iou = iou_threshold
        self._imgsz = image_size
        self._allowed_classes = set(allowed_classes or ["person", "car", "motorcycle", "truck"])
        self._model: object = None
        self._track_history: dict[int, Track] = {}
        self._load_model()

    # ------------------------------------------------------------------
    # Tracker Protocol
    # ------------------------------------------------------------------

    def update(self, frame: np.ndarray, detections: list[Detection]) -> list[Track]:
        """
        Run YOLO with ByteTrack on the frame and return active tracks.

        Single YOLO call: detection + tracking in one pass.
        The `detections` parameter is used only for camera_id extraction.
        """
        if self._model is None:
            return []

        import time
        t0 = time.perf_counter()

        try:
            results = self._model(  # type: ignore[operator]
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=self._conf,
                iou=self._iou,
                imgsz=self._imgsz,
                verbose=False,
            )
        except Exception as exc:
            logger.error("bytetrack_inference_error", error=str(exc))
            return []

        latency_ms = (time.perf_counter() - t0) * 1000
        metrics.inference_latency_ms.observe(latency_ms)
        metrics.frames_processed_total.inc()

        camera_id = detections[0].camera_id if detections else "unknown"
        return self._parse_results(results, camera_id)

    def reset(self) -> None:
        """
        Reset all tracking state.
        Must be called when a camera stream session changes (reconnect).
        """
        self._track_history.clear()
        # Ultralytics persists track state in the model object; re-loading
        # is the safest reset approach.
        self._load_model()
        logger.info("bytetrack_reset")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import]
            self._model = YOLO(self._model_path)
            # Apply device configuration
            if self._device != "cpu":
                self._model.to(self._device)  # type: ignore[attr-defined]
            logger.info("bytetrack_model_loaded", path=self._model_path, device=self._device)
        except Exception as exc:
            logger.error("bytetrack_model_load_failed", error=str(exc))
            self._model = None

    def _parse_results(
        self,
        results: list[object],
        camera_id: str,
    ) -> list[Track]:
        tracks: list[Track] = []
        now = datetime.now(tz=UTC)

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names: dict[int, str] = getattr(result, "names", {})

            ids = getattr(boxes, "id", None)
            data = getattr(boxes, "xyxyn", None)
            confs = getattr(boxes, "conf", None)
            clss = getattr(boxes, "cls", None)

            if data is None or ids is None:
                continue

            for i in range(len(data)):
                try:
                    tid = int(ids[i])
                    x1, y1, x2, y2 = (
                        float(data[i][0]), float(data[i][1]),
                        float(data[i][2]), float(data[i][3]),
                    )
                    conf = float(confs[i]) if confs is not None else 0.0
                    cls_id = int(clss[i]) if clss is not None else 0
                    cls_name = names.get(cls_id, str(cls_id))

                    if cls_name not in self._allowed_classes:
                        continue
                    if x1 >= x2 or y1 >= y2:
                        continue

                    bbox = BoundingBox(
                        x1=max(0.0, min(1.0, x1)),
                        y1=max(0.0, min(1.0, y1)),
                        x2=max(0.0, min(1.0, x2)),
                        y2=max(0.0, min(1.0, y2)),
                    )
                    foot = (bbox.foot_x, bbox.foot_y)

                    if tid in self._track_history:
                        existing = self._track_history[tid]
                        existing.last_seen = now
                        existing.bbox = bbox
                        existing.confidence = conf
                        existing.trajectory.append(foot)
                        track = existing
                    else:
                        track = Track(
                            track_id=tid,
                            camera_id=camera_id,
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=bbox,
                            first_seen=now,
                            last_seen=now,
                            trajectory=[foot],
                        )
                        self._track_history[tid] = track

                    tracks.append(track)
                except Exception as exc:
                    logger.warning("bytetrack_parse_error", index=i, error=str(exc))

        metrics.active_tracks.set(float(len(tracks)))
        return tracks


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_tracker(
    use_mock: bool = True,
    model_path: str = "models/yolo26n.pt",
    device: str = "cpu",
    allowed_classes: list[str] | None = None,
) -> Tracker:
    if use_mock:
        return MockTracker()
    return ByteTrackTracker(
        model_path=model_path,
        device=device,
        allowed_classes=allowed_classes,
    )
