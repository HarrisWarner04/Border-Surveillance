"""
Inference layer: Detector protocol, YOLO26Detector, MockDetector.

The business logic (events, risk, zones) must only interact with the
Detector Protocol — never with Ultralytics directly.  This lets the
project swap between YOLO26n, YOLO11n, ONNX, TensorRT, or a mock
without touching any other module.

Responsibilities of a Detector:
  - Accept a numpy BGR frame
  - Return a list of Detection domain objects
  - Record inference latency
  - Never write evidence, alerts, or DB rows
  - Never know about zones or RTSP
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import numpy as np

from src.observability.logging import get_logger
from src.observability.metrics import metrics

# Contracts are imported from the shared package
# Adjust the import path if you run from the ibvap root vs edge-agent root.
try:
    from ibvap_contracts.models.detection import BoundingBox, Detection
except ImportError:
    # Fallback for when contracts are not installed as a package yet
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parents[5] / "packages" / "contracts" / "src"))
    from ibvap_contracts.models.detection import BoundingBox, Detection  # type: ignore[no-redef]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Detector Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Detector(Protocol):
    """
    Protocol that every detector implementation must satisfy.

    model_name and model_version are exposed so events can record
    which model version produced a given detection.
    """

    @property
    def model_name(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def detect(self, frame: np.ndarray, camera_id: str) -> list[Detection]:
        """
        Run inference on a single BGR frame.

        Parameters
        ----------
        frame     : HxWx3 BGR uint8 numpy array
        camera_id : used to populate the Detection.camera_id field

        Returns
        -------
        List of Detection objects (may be empty).  Never raises on
        empty results — only raises on unrecoverable model errors.
        """
        ...

    def warmup(self) -> None:
        """
        Optional: run one dummy inference to pre-load model weights.
        Call once after construction, before the frame loop.
        """
        ...


# ---------------------------------------------------------------------------
# MockDetector — deterministic, no model weights needed
# ---------------------------------------------------------------------------


class MockDetector:
    """
    Returns pre-configured synthetic detections for CI and demo.

    By default returns one 'person' detection that moves horizontally
    so zone-crossing logic can be exercised without real video.

    frame_sequence controls which frame pattern to generate:
        'walk_through_zone' (default) — person walks left to right
        'outside_only'                — person stays outside zone
        'static_inside'               — person stays inside zone
    """

    def __init__(
        self,
        frame_sequence: str = "walk_through_zone",
        allowed_classes: list[str] | None = None,
        confidence: float = 0.85,
    ) -> None:
        self._frame_sequence = frame_sequence
        self._allowed_classes = allowed_classes or ["person", "car", "motorcycle", "truck"]
        self._confidence = confidence
        self._frame_count = 0

    @property
    def model_name(self) -> str:
        return "mock_detector"

    @property
    def model_version(self) -> str:
        return "1.0.0"

    def detect(self, frame: np.ndarray, camera_id: str) -> list[Detection]:
        t0 = time.perf_counter()
        self._frame_count += 1
        detections = self._generate(camera_id)
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics.inference_latency_ms.observe(latency_ms)
        metrics.frames_processed_total.inc()
        return detections

    def warmup(self) -> None:
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        self.detect(dummy, "warmup")
        logger.info("mock_detector_warmup_complete")

    def _generate(self, camera_id: str) -> list[Detection]:
        """Generate synthetic detections based on frame sequence type."""
        now = datetime.now(tz=UTC)

        if self._frame_sequence == "outside_only":
            # Person is always outside the typical demo zone (top strip)
            x_center = 0.5
            bbox = BoundingBox(x1=x_center - 0.04, y1=0.02, x2=x_center + 0.04, y2=0.15)
        elif self._frame_sequence == "static_inside":
            # Person is always inside the typical demo zone
            bbox = BoundingBox(x1=0.40, y1=0.30, x2=0.55, y2=0.70)
        else:
            # walk_through_zone: person walks from left (outside) to right (inside zone)
            # The demo zone spans x=[0.05, 0.95], y=[0.20, 0.90]
            # Person starts outside (y < 0.20) then enters zone at frame ~10
            progress = (self._frame_count % 60) / 60.0
            x_center = 0.1 + progress * 0.8
            if progress < 0.15:
                # Above zone (outside)
                y1, y2 = 0.05, 0.18
            else:
                # Inside zone
                y1, y2 = 0.30, 0.75
            bbox = BoundingBox(
                x1=max(0.0, x_center - 0.04),
                y1=y1,
                x2=min(1.0, x_center + 0.04),
                y2=y2,
            )

        return [
            Detection(
                id=uuid.uuid4(),
                camera_id=camera_id,
                timestamp=now,
                class_id=0,
                class_name="person",
                confidence=self._confidence,
                bbox=bbox,
                model_name=self.model_name,
                model_version=self.model_version,
            )
        ]


# ---------------------------------------------------------------------------
# YOLO26Detector — wraps Ultralytics YOLO
# ---------------------------------------------------------------------------


class YOLO26Detector:
    """
    Production detector backed by Ultralytics YOLO26n (or any YOLO variant).

    The model is loaded once at construction and never reloaded per frame.
    Raw Ultralytics results are converted to canonical Detection objects
    before being returned.

    Parameters
    ----------
    model_path       : Path to .pt weight file
    device           : 'auto' | 'cpu' | 'cuda' | 'mps'
    confidence_threshold : Minimum confidence to keep a detection
    iou_threshold    : NMS IoU threshold
    image_size       : Inference image size (long side)
    allowed_classes  : Only return detections for these class names
    """

    def __init__(
        self,
        model_path: str = "models/yolo26n.pt",
        device: str = "auto",
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.50,
        image_size: int = 640,
        allowed_classes: list[str] | None = None,
    ) -> None:
        self._model_path = model_path
        self._device = self._resolve_device(device)
        self._conf = confidence_threshold
        self._iou = iou_threshold
        self._imgsz = image_size
        self._allowed_classes = set(allowed_classes or ["person", "car", "motorcycle", "truck"])
        self._model_version: str = "unknown"
        self._model: object = None  # typed as object to avoid hard dependency at import

        self._load_model()

    @property
    def model_name(self) -> str:
        return "yolo26n"

    @property
    def model_version(self) -> str:
        return self._model_version

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, camera_id: str) -> list[Detection]:
        """Run inference and return filtered Detection objects."""
        if self._model is None:
            logger.error("yolo_model_not_loaded", camera_id=camera_id)
            return []

        t0 = time.perf_counter()
        try:
            results = self._model(  # type: ignore[operator]
                frame,
                conf=self._conf,
                iou=self._iou,
                imgsz=self._imgsz,
                verbose=False,
            )
        except Exception as exc:
            logger.error("yolo_inference_error", error=str(exc), camera_id=camera_id)
            return []

        latency_ms = (time.perf_counter() - t0) * 1000
        metrics.inference_latency_ms.observe(latency_ms)
        metrics.frames_processed_total.inc()

        return self._parse_results(results, camera_id)

    def warmup(self) -> None:
        """Run one dummy inference to pre-load CUDA kernels."""
        logger.info("yolo_warmup_start", model_path=self._model_path, device=self._device)
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self.detect(dummy, "warmup")
        logger.info("yolo_warmup_complete")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        try:
            import ultralytics  # type: ignore[import]
            from ultralytics import YOLO  # type: ignore[import]

            self._model = YOLO(self._model_path)
            # Apply device for GPU acceleration
            if self._device != "cpu":
                self._model.to(self._device)  # type: ignore[attr-defined]
            self._model_version = ultralytics.__version__  # type: ignore[attr-defined]
            logger.info(
                "yolo_model_loaded",
                path=self._model_path,
                device=self._device,
                version=self._model_version,
            )
        except Exception as exc:
            logger.error("yolo_model_load_failed", path=self._model_path, error=str(exc))
            raise RuntimeError(f"Failed to load YOLO model: {exc}") from exc

    def _resolve_device(self, device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch  # type: ignore[import]
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _parse_results(self, results: list[object], camera_id: str) -> list[Detection]:
        detections: list[Detection] = []
        now = datetime.now(tz=UTC)

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names: dict[int, str] = getattr(result, "names", {})

            # boxes.data is tensor (N, 6): [x1, y1, x2, y2, conf, cls]
            data = getattr(boxes, "xyxyn", None)  # normalized coords
            confs = getattr(boxes, "conf", None)
            clss = getattr(boxes, "cls", None)

            if data is None:
                continue

            for i in range(len(data)):
                try:
                    x1, y1, x2, y2 = float(data[i][0]), float(data[i][1]), float(data[i][2]), float(data[i][3])
                    conf = float(confs[i]) if confs is not None else 0.0
                    cls_id = int(clss[i]) if clss is not None else 0
                    cls_name = names.get(cls_id, str(cls_id))

                    if cls_name not in self._allowed_classes:
                        continue
                    if conf < self._conf:
                        continue
                    # Validate bbox before constructing
                    if x1 >= x2 or y1 >= y2:
                        continue

                    bbox = BoundingBox(
                        x1=max(0.0, min(1.0, x1)),
                        y1=max(0.0, min(1.0, y1)),
                        x2=max(0.0, min(1.0, x2)),
                        y2=max(0.0, min(1.0, y2)),
                    )
                    detections.append(
                        Detection(
                            id=uuid.uuid4(),
                            camera_id=camera_id,
                            timestamp=now,
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=bbox,
                            model_name=self.model_name,
                            model_version=self._model_version,
                        )
                    )
                except Exception as exc:
                    logger.warning("yolo_parse_box_error", index=i, error=str(exc))

        return detections


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_detector(
    model_name: str = "mock",
    model_path: str = "models/yolo26n.pt",
    device: str = "cpu",
    confidence_threshold: float = 0.35,
    iou_threshold: float = 0.50,
    image_size: int = 640,
    allowed_classes: list[str] | None = None,
) -> Detector:
    """Return the appropriate detector based on model_name config."""
    if model_name == "mock":
        return MockDetector(allowed_classes=allowed_classes)
    elif model_name in ("yolo26n", "yolo11n", "yolo11s", "yolo26s"):
        return YOLO26Detector(
            model_path=model_path,
            device=device,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            allowed_classes=allowed_classes,
        )
    else:
        raise ValueError(f"Unknown detector model: {model_name!r}")
