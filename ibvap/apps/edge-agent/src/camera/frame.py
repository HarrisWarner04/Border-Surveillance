"""
Frame data structures for the video pipeline.

FramePacket carries metadata alongside the raw numpy frame array.
The image array is NOT serialised through Pydantic to avoid copies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass
class FramePacket:
    """
    A single decoded video frame plus metadata.

    Attributes
    ----------
    camera_id:    Camera that produced this frame.
    session_id:   Unique ID for the current stream session.
                  Resets on every reconnect so stale state can be detected.
    frame_index:  Monotonically increasing counter within the session.
    captured_at:  UTC timestamp assigned when the frame was read from the source.
    width:        Frame width in pixels.
    height:       Frame height in pixels.
    image:        Raw BGR numpy array (H, W, 3) — may be None if frame is empty/stale.
    """

    camera_id: str
    session_id: str
    frame_index: int
    captured_at: datetime
    width: int
    height: int
    image: np.ndarray | None = field(default=None, repr=False)

    @property
    def is_valid(self) -> bool:
        """True when the frame contains actual image data."""
        return self.image is not None and self.image.size > 0

    @classmethod
    def empty(cls, camera_id: str, session_id: str, frame_index: int) -> FramePacket:
        """Create a sentinel empty packet used to signal stall/disconnect."""
        return cls(
            camera_id=camera_id,
            session_id=session_id,
            frame_index=frame_index,
            captured_at=datetime.now(tz=UTC),
            width=0,
            height=0,
            image=None,
        )
