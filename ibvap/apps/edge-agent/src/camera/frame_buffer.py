"""
Bounded frame buffer.

The producer (RTSP reader) always writes the latest frame.
The consumer (inference loop) reads at its own pace.

When the buffer is full, the oldest stale frame is dropped
so the consumer always processes the most recent frame available.
This is correct semantics for real-time surveillance.

Metrics:
  frames_received_total   incremented on every put()
  frames_dropped_total    incremented on every drop
"""

from __future__ import annotations

import threading
from collections import deque

from src.camera.frame import FramePacket
from src.observability.metrics import metrics


class BoundedFrameBuffer:
    """
    Thread-safe ring buffer for FramePacket objects.

    Parameters
    ----------
    capacity : int
        Maximum number of frames retained.  When full, the oldest frame
        is silently dropped and the metric is incremented.
        Recommended: 2–4 frames for real-time surveillance.
    """

    def __init__(self, capacity: int = 4) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._buffer: deque[FramePacket] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    def put(self, packet: FramePacket) -> None:
        """
        Add a frame to the buffer.

        If the buffer is already full, the oldest frame is implicitly
        dropped (deque maxlen behaviour) and the drop metric incremented.
        """
        metrics.frames_received_total.inc()
        with self._not_empty:
            if len(self._buffer) >= self._capacity:
                metrics.frames_dropped_total.inc()
            self._buffer.append(packet)
            self._not_empty.notify()

    # ------------------------------------------------------------------
    # Consumer side
    # ------------------------------------------------------------------

    def get(self, timeout: float = 1.0) -> FramePacket | None:
        """
        Return the oldest frame, blocking up to *timeout* seconds.

        Returns None on timeout so callers can check shutdown flags.
        """
        with self._not_empty:
            if not self._buffer and not self._not_empty.wait(timeout):
                return None
            if not self._buffer:
                return None
            return self._buffer.popleft()

    def get_latest(self) -> FramePacket | None:
        """Non-blocking: return and remove the newest frame, discarding older ones."""
        with self._lock:
            if not self._buffer:
                return None
            # Discard all but the last
            dropped = len(self._buffer) - 1
            for _ in range(dropped):
                self._buffer.popleft()
                metrics.frames_dropped_total.inc()
            return self._buffer.popleft() if self._buffer else None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def qsize(self) -> int:
        with self._lock:
            return len(self._buffer)

    def empty(self) -> bool:
        with self._lock:
            return len(self._buffer) == 0

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
