"""
Edge-agent application settings.

All configuration is loaded from environment variables (or a .env file).
Secrets such as RTSP URLs must never be hardcoded in source.

Load order: defaults → .env file → environment variables → explicit overrides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Validated application-wide settings for the edge agent.

    All values are read from environment variables.
    See .env.example for the full list of supported keys.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------
    app_env: Literal["development", "production", "test"] = "development"
    edge_site_id: str = "site-demo-01"
    edge_device_id: str = "edge-demo-01"

    # -----------------------------------------------------------------------
    # API server
    # -----------------------------------------------------------------------
    edge_api_port: int = Field(default=8001, ge=1, le=65535)
    edge_secret_key: str = "change-me-edge-secret-key-at-least-32-chars"

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    edge_database_url: str = "sqlite+aiosqlite:///./data/edge.db"

    # -----------------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------------
    edge_media_dir: Path = Path("./data/evidence")
    edge_logs_dir: Path = Path("./data/logs")

    # -----------------------------------------------------------------------
    # Central API
    # -----------------------------------------------------------------------
    central_api_url: str = "http://localhost:8000"
    central_api_key: str = "change-me-edge-api-key"
    sync_enabled: bool = True
    sync_batch_size: int = Field(default=25, ge=1)
    sync_retry_max: int = Field(default=10, ge=0)
    sync_retry_backoff_base_sec: float = Field(default=1.0, gt=0)
    sync_retry_backoff_max_sec: float = Field(default=60.0, gt=0)

    # -----------------------------------------------------------------------
    # AI model
    # -----------------------------------------------------------------------
    model_detector: str = "mock"
    # mock | yolo11n | yolo11s | yolo26n
    model_path: Path = Path("models/yolo26n.pt")
    model_device: Literal["auto", "cpu", "cuda", "mps"] = "cpu"
    model_confidence_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    model_iou_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    model_image_size: int = Field(default=640, ge=32)
    # Comma-separated class names to keep; empty = keep all COCO classes
    model_classes: str = "person,car,motorcycle,truck"

    # -----------------------------------------------------------------------
    # Processing rates
    # -----------------------------------------------------------------------
    detection_fps: int = Field(default=3, ge=1, le=60)
    tracking_fps: int = Field(default=10, ge=1, le=60)
    behavior_interval_sec: float = Field(default=1.0, gt=0)

    # -----------------------------------------------------------------------
    # Evidence capture
    # -----------------------------------------------------------------------
    pre_event_seconds: float = Field(default=5.0, ge=0)
    post_event_seconds: float = Field(default=10.0, ge=0)

    # -----------------------------------------------------------------------
    # Risk thresholds (configurable, spec defaults)
    # -----------------------------------------------------------------------
    risk_low_max: int = Field(default=19, ge=0, le=100)
    risk_medium_max: int = Field(default=49, ge=0, le=100)
    risk_high_max: int = Field(default=79, ge=0, le=100)

    # -----------------------------------------------------------------------
    # Demo / simulation
    # -----------------------------------------------------------------------
    demo_mode: bool = True
    demo_disconnect_central: bool = False

    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -----------------------------------------------------------------------
    # Intrusion detection
    # -----------------------------------------------------------------------
    intrusion_confirmation_frames: int = Field(default=3, ge=1)
    intrusion_alert_cooldown_seconds: float = Field(default=10.0, ge=0)
    track_state_ttl_seconds: float = Field(default=30.0, gt=0)

    # -----------------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------------

    @field_validator("model_classes")
    @classmethod
    def parse_classes(cls, v: str) -> str:
        """Strip whitespace from each class name."""
        cleaned = ",".join(c.strip() for c in v.split(",") if c.strip())
        return cleaned

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def allowed_classes(self) -> list[str]:
        """Return list of class names to keep from the detector output."""
        return [c for c in self.model_classes.split(",") if c]

    def ensure_dirs(self) -> None:
        """Create required data directories if they do not exist."""
        self.edge_media_dir.mkdir(parents=True, exist_ok=True)
        self.edge_logs_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton — import this throughout the app.
# Tests can override by constructing Settings() directly.
settings = Settings()
