"""
Camera source adapters and reconnect manager.

Hierarchy:
    CameraSource (Protocol)
    ├── FileSource      reads local video file via OpenCV, loops
    ├── MockSource      generates synthetic frames (no model/file needed)
    └── RTSPSource      reads RTSP stream via OpenCV with reconnect

Each source runs inside its own thread started by the pipeline orchestrator.
A failure in one source never blocks others.

Reconnect state machine (RTSPSource):
    DISCONNECTED → CONNECTING → CONNECTED → DEGRADED/OFFLINE → backoff → CONNECTING
"""

from __future__ import annotations

import os
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime

import cv2
import numpy as np

from src.camera.frame import FramePacket
from src.camera.models import CameraConfig
from src.observability.logging import get_logger
from src.observability.metrics import metrics

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol / base
# ---------------------------------------------------------------------------


class CameraSource(ABC):
    """Abstract base for all camera source adapters."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._stop_flag = False
        self._session_id: str = str(uuid.uuid4())

    @property
    def camera_id(self) -> str:
        return self.config.camera_id

    def stop(self) -> None:
        self._stop_flag = True

    def _new_session(self) -> str:
        self._session_id = str(uuid.uuid4())
        return self._session_id

    @abstractmethod
    def frames(self) -> Iterator[FramePacket]:
        """Yield FramePackets until stop() is called."""
        ...


# ---------------------------------------------------------------------------
# MockSource — deterministic synthetic frames for CI / demo
# ---------------------------------------------------------------------------


class MockSource(CameraSource):
    """
    Generates synthetic 640×480 frames at the configured fps.

    Each frame has a moving white rectangle to simulate a walking person.
    Useful for CI pipelines that must not depend on real video files.
    """

    def __init__(self, config: CameraConfig, width: int = 640, height: int = 480) -> None:
        super().__init__(config)
        self._width = width
        self._height = height

    def frames(self) -> Iterator[FramePacket]:
        session_id = self._new_session()
        frame_index = 0
        x = 50  # simulated object x position

        while not self._stop_flag:
            frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

            # Draw a moving white rectangle (person simulation)
            x = (x + 4) % (self._width - 80)
            y = self._height // 2 - 60
            cv2.rectangle(frame, (x, y), (x + 50, y + 120), (220, 220, 220), -1)

            # Draw a static zone boundary for visual reference
            cv2.rectangle(frame, (30, 100), (610, 420), (0, 200, 0), 2)

            packet = FramePacket(
                camera_id=self.camera_id,
                session_id=session_id,
                frame_index=frame_index,
                captured_at=datetime.now(tz=UTC),
                width=self._width,
                height=self._height,
                image=frame,
            )
            metrics.frames_received_total.inc()
            yield packet
            frame_index += 1
            time.sleep(1.0 / self.config.target_fps)


# ---------------------------------------------------------------------------
# FileSource — reads local MP4 / AVI, loops when finished
# ---------------------------------------------------------------------------


class FileSource(CameraSource):
    """
    Reads frames from a local video file using OpenCV.

    Loops the file on completion so the pipeline keeps running during demos.
    Stops cleanly when stop() is called.
    """

    def frames(self) -> Iterator[FramePacket]:
        uri = self.config.stream_uri.get_secret_value()
        session_id = self._new_session()
        frame_index = 0

        while not self._stop_flag:
            cap = cv2.VideoCapture(uri)
            if not cap.isOpened():
                logger.warning(
                    "file_source_open_failed",
                    camera_id=self.camera_id,
                    # log path without credentials (file paths are safe here)
                    path=uri,
                )
                metrics.camera_reconnect_total.inc()
                time.sleep(2.0)
                continue

            logger.info("file_source_opened", camera_id=self.camera_id, path=uri)
            metrics.camera_connected.set(1)

            fps = cap.get(cv2.CAP_PROP_FPS) or self.config.target_fps
            delay = 1.0 / min(fps, self.config.target_fps)

            while not self._stop_flag:
                ret, frame = cap.read()
                if not ret:
                    # End of file — loop
                    logger.debug("file_source_loop", camera_id=self.camera_id)
                    break

                packet = FramePacket(
                    camera_id=self.camera_id,
                    session_id=session_id,
                    frame_index=frame_index,
                    captured_at=datetime.now(tz=UTC),
                    width=frame.shape[1],
                    height=frame.shape[0],
                    image=frame,
                )
                metrics.frames_received_total.inc()
                yield packet
                frame_index += 1
                time.sleep(delay)

            cap.release()

        metrics.camera_connected.set(0)
        logger.info("file_source_stopped", camera_id=self.camera_id)


# ---------------------------------------------------------------------------
# RTSPSource — live RTSP with exponential-backoff reconnect
# ---------------------------------------------------------------------------


class RTSPSource(CameraSource):
    """
    Reads a live RTSP stream via OpenCV.

    Reconnects automatically using bounded exponential backoff.
    Each connection attempt gets a new session_id so downstream
    tracker state is reset on reconnect.

    NEVER logs the stream URI (it may contain credentials).
    """

    # How long without a fresh frame before declaring the stream stalled
    STALL_TIMEOUT_SECONDS: float = 5.0

    def frames(self) -> Iterator[FramePacket]:
        backoff = self.config.reconnect_initial_seconds
        attempt = 0
        session_id = self._new_session()
        frame_index = 0

        while not self._stop_flag:
            attempt += 1
            if (
                self.config.reconnect_max_attempts > 0
                and attempt > self.config.reconnect_max_attempts
            ):
                logger.error(
                    "rtsp_max_reconnect_reached",
                    camera_id=self.camera_id,
                    attempts=attempt,
                )
                break

            logger.info("rtsp_connecting", camera_id=self.camera_id, attempt=attempt)
            metrics.camera_reconnect_total.inc()

            uri = self.config.stream_uri.get_secret_value()
            # Set RTSP transport before opening — OpenCV reads this env var
            if self.config.transport == "tcp":
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            cap = cv2.VideoCapture(uri, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                logger.warning(
                    "rtsp_connect_failed",
                    camera_id=self.camera_id,
                    attempt=attempt,
                    backoff_sec=backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, self.config.reconnect_max_seconds)
                continue

            # Connected — reset backoff, new session
            backoff = self.config.reconnect_initial_seconds
            session_id = self._new_session()
            frame_index = 0
            last_frame_time = time.monotonic()
            metrics.camera_connected.set(1)
            logger.info("rtsp_connected", camera_id=self.camera_id, session_id=session_id)

            while not self._stop_flag:
                ret, frame = cap.read()

                # Stall detection
                if not ret or frame is None or frame.size == 0:
                    elapsed = time.monotonic() - last_frame_time
                    if elapsed > self.STALL_TIMEOUT_SECONDS:
                        logger.warning(
                            "rtsp_stream_stalled",
                            camera_id=self.camera_id,
                            stall_seconds=elapsed,
                        )
                        metrics.camera_connected.set(0)
                        break
                    time.sleep(0.01)
                    continue

                last_frame_time = time.monotonic()
                packet = FramePacket(
                    camera_id=self.camera_id,
                    session_id=session_id,
                    frame_index=frame_index,
                    captured_at=datetime.now(tz=UTC),
                    width=frame.shape[1],
                    height=frame.shape[0],
                    image=frame,
                )
                metrics.frames_received_total.inc()
                yield packet
                frame_index += 1

            cap.release()
            logger.warning(
                "rtsp_disconnected",
                camera_id=self.camera_id,
                session_id=session_id,
                backoff_sec=backoff,
            )
            metrics.camera_connected.set(0)
            time.sleep(backoff)
            backoff = min(backoff * 2, self.config.reconnect_max_seconds)

        logger.info("rtsp_source_stopped", camera_id=self.camera_id)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_camera_source(config: CameraConfig) -> CameraSource:
    """Return the correct source adapter based on the camera protocol."""
    if config.protocol == "MOCK":
        return MockSource(config)
    elif config.protocol == "FILE":
        return FileSource(config)
    elif config.protocol == "RTSP":
        return RTSPSource(config)
    else:
        raise ValueError(f"Unsupported camera protocol: {config.protocol}")
