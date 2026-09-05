"""
In-process metrics registry.

Prometheus-style counters and gauges stored in memory.
Can be exported via the /metrics HTTP endpoint.

No external Prometheus client is required for Phase 1 —
this is a simple thread-safe implementation that can be
swapped for prometheus_client in Phase 8.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Counter:
    """Monotonically increasing counter."""

    name: str
    help: str
    _value: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        """For testing only — counters don't reset in production."""
        with self._lock:
            self._value = 0.0


@dataclass
class Gauge:
    """Value that can go up and down."""

    name: str
    help: str
    _value: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class Histogram:
    """Simple latency histogram that tracks count, sum, and percentile buckets."""

    name: str
    help: str
    _observations: list[float] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def observe(self, value_ms: float) -> None:
        with self._lock:
            self._observations.append(value_ms)
            # Keep only recent 1000 observations to bound memory
            if len(self._observations) > 1000:
                self._observations = self._observations[-1000:]

    def p50(self) -> float:
        return self._percentile(50)

    def p95(self) -> float:
        return self._percentile(95)

    def mean(self) -> float:
        with self._lock:
            if not self._observations:
                return 0.0
            return sum(self._observations) / len(self._observations)

    def count(self) -> int:
        with self._lock:
            return len(self._observations)

    def _percentile(self, p: float) -> float:
        with self._lock:
            if not self._observations:
                return 0.0
            sorted_obs = sorted(self._observations)
            idx = int(len(sorted_obs) * p / 100)
            idx = min(idx, len(sorted_obs) - 1)
            return sorted_obs[idx]


class MetricsRegistry:
    """
    Central registry for all edge-agent in-process metrics.

    Access via the module-level `metrics` singleton.
    """

    def __init__(self) -> None:
        # Camera
        self.camera_connected = Gauge(
            "camera_connected", "1 if the camera stream is connected, else 0"
        )
        self.camera_reconnect_total = Counter(
            "camera_reconnect_total", "Total reconnect attempts"
        )
        # Frames
        self.frames_received_total = Counter(
            "frames_received_total", "Total frames received from camera"
        )
        self.frames_dropped_total = Counter(
            "frames_dropped_total", "Frames dropped due to buffer overflow"
        )
        self.frames_processed_total = Counter(
            "frames_processed_total", "Frames passed through inference"
        )
        # Inference
        self.inference_latency_ms = Histogram(
            "inference_latency_ms", "Per-frame inference latency in milliseconds"
        )
        self.pipeline_latency_ms = Histogram(
            "pipeline_latency_ms", "End-to-end per-frame pipeline latency in milliseconds"
        )
        # Tracking
        self.active_tracks = Gauge(
            "active_tracks", "Currently active track IDs"
        )
        # Events / alerts
        self.intrusions_total = Counter(
            "intrusions_total", "Total confirmed intrusion events"
        )
        self.alerts_sent_total = Counter(
            "alerts_sent_total", "Total alerts dispatched"
        )
        self.alerts_suppressed_total = Counter(
            "alerts_suppressed_total", "Alerts suppressed by cooldown"
        )
        # Evidence / storage
        self.evidence_write_failures_total = Counter(
            "evidence_write_failures_total", "Failed evidence file writes"
        )
        self.db_write_failures_total = Counter(
            "db_write_failures_total", "Failed SQLite event persists"
        )

    def snapshot(self) -> dict[str, object]:
        """Return a plain-dict snapshot for the /metrics endpoint."""
        return {
            "camera_connected": self.camera_connected.value(),
            "camera_reconnect_total": self.camera_reconnect_total.value(),
            "frames_received_total": self.frames_received_total.value(),
            "frames_dropped_total": self.frames_dropped_total.value(),
            "frames_processed_total": self.frames_processed_total.value(),
            "inference_latency_ms_p50": self.inference_latency_ms.p50(),
            "inference_latency_ms_p95": self.inference_latency_ms.p95(),
            "inference_latency_ms_mean": self.inference_latency_ms.mean(),
            "pipeline_latency_ms_p50": self.pipeline_latency_ms.p50(),
            "active_tracks": self.active_tracks.value(),
            "intrusions_total": self.intrusions_total.value(),
            "alerts_sent_total": self.alerts_sent_total.value(),
            "alerts_suppressed_total": self.alerts_suppressed_total.value(),
            "evidence_write_failures_total": self.evidence_write_failures_total.value(),
            "db_write_failures_total": self.db_write_failures_total.value(),
        }


# Module-level singleton
metrics = MetricsRegistry()
