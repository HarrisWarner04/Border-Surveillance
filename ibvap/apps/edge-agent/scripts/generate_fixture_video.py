"""
Generate a synthetic demo video fixture for CI and local testing.

Creates:
    tests/fixtures/videos/demo_walk.mp4

Sequence:
  Frames   0-29:  Person outside zone (above top edge y=0.20)
  Frames  30-90:  Person walks inside zone
  Frames 91-120:  Person exits zone

Expected pipeline result:
  1 confirmed PERIMETER_INTRUSION event (after confirmation_frames=3)
  0 duplicate events while track stays inside continuously
  1 RESOLVED event on exit

Usage:
    python scripts/generate_fixture_video.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

OUTPUT = Path(__file__).parents[1] / "tests" / "fixtures" / "videos" / "demo_walk.mp4"
WIDTH, HEIGHT = 640, 480
FPS = 10
DURATION_FRAMES = 120


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUTPUT), fourcc, FPS, (WIDTH, HEIGHT))

    if not writer.isOpened():
        print(f"ERROR: Cannot open video writer for {OUTPUT}")
        print("Ensure OpenCV is installed: pip install opencv-python-headless")
        sys.exit(1)

    # Zone boundary pixels (x=[0.05,0.95], y=[0.20,0.90])
    zone_pts = np.array([
        [int(0.05 * WIDTH), int(0.20 * HEIGHT)],
        [int(0.95 * WIDTH), int(0.20 * HEIGHT)],
        [int(0.95 * WIDTH), int(0.90 * HEIGHT)],
        [int(0.05 * WIDTH), int(0.90 * HEIGHT)],
    ], np.int32)

    for i in range(DURATION_FRAMES):
        frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

        # Draw zone
        cv2.polylines(frame, [zone_pts.reshape((-1, 1, 2))], True, (0, 200, 0), 2)
        cv2.putText(frame, "RESTRICTED ZONE", (20, int(0.20 * HEIGHT) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)

        x_px = WIDTH // 2
        bw, bh = 40, 90

        if i < 30:
            # Outside — above zone top
            y_px = int(0.12 * HEIGHT)
            colour = (120, 120, 120)
            label = "OUTSIDE"
        elif i < 90:
            # Inside — moving downward
            progress = (i - 30) / 60.0
            y_px = int((0.28 + progress * 0.45) * HEIGHT)
            colour = (50, 50, 220)
            label = "INSIDE"
        else:
            # Exiting — below zone
            y_px = int(0.95 * HEIGHT)
            colour = (120, 120, 120)
            label = "OUTSIDE"

        # Draw person rectangle (foot point = bottom centre)
        cv2.rectangle(frame, (x_px - bw // 2, y_px - bh), (x_px + bw // 2, y_px), colour, -1)
        cv2.putText(frame, "ID:1", (x_px - 15, y_px - bh - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(frame, label, (x_px - 25, y_px + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

        # Frame counter
        cv2.putText(frame, f"Frame {i:03d} / {DURATION_FRAMES}", (8, HEIGHT - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)

        writer.write(frame)

    writer.release()
    print(f"✓ Fixture written: {OUTPUT}  ({DURATION_FRAMES} frames @ {FPS} fps)")
    print("  Expected: 1 PERIMETER_INTRUSION event, 0 alert spam while inside, 1 RESOLVED on exit.")


if __name__ == "__main__":
    main()
