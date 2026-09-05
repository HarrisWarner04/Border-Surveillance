"""
Test RTSP connectivity before integrating with the pipeline.

Usage:
    python scripts/test_rtsp.py --url rtsp://host/stream --frames 30
    python scripts/test_rtsp.py --file path/to/video.mp4

Never paste real credentials in shell history.
Use the RTSP_URL environment variable instead:
    $env:RTSP_URL="rtsp://user:pass@host/stream"
    python scripts/test_rtsp.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Test camera source connectivity")
    parser.add_argument("--url", default=None, help="RTSP URL (or use RTSP_URL env var)")
    parser.add_argument("--file", default=None, help="Local video file path")
    parser.add_argument("--frames", type=int, default=30, help="Number of frames to read")
    parser.add_argument("--timeout", type=float, default=10.0, help="Connection timeout (s)")
    args = parser.parse_args()

    # Prefer env var to avoid credentials in shell history
    url = args.url or os.environ.get("RTSP_URL") or args.file
    if not url:
        print("ERROR: Provide --url, --file, or set RTSP_URL environment variable")
        sys.exit(1)

    # Redact credentials for logging
    import re
    safe_url = re.sub(r"://[^:]+:[^@]+@", "://<redacted>@", url)

    try:
        import cv2
    except ImportError:
        print("ERROR: opencv not installed. Run: pip install opencv-python-headless")
        sys.exit(1)

    print(f"Connecting to: {safe_url}")
    print(f"Target frames: {args.frames}")

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("ERROR: Could not open source.")
        print("Possible causes: URL/path, credentials, network, codec, firewall.")
        sys.exit(1)

    print("Connected.")
    fps_cap = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  Source FPS: {fps_cap:.1f}  Resolution: {w}x{h}")

    t_start = time.monotonic()
    frames_read = 0
    frames_empty = 0

    for i in range(args.frames):
        ret, frame = cap.read()
        if not ret or frame is None:
            frames_empty += 1
            if frames_empty > 5:
                print(f"  Stream appears stalled after frame {i}")
                break
            continue

        frames_read += 1
        elapsed = time.monotonic() - t_start
        actual_fps = frames_read / elapsed if elapsed > 0 else 0
        print(f"  Frame {frames_read:3d}  shape={frame.shape}  fps={actual_fps:.1f}")

    elapsed_total = time.monotonic() - t_start
    avg_fps = frames_read / elapsed_total if elapsed_total > 0 else 0

    cap.release()

    print("\n--- Results ---")
    print(f"  Frames read   : {frames_read}")
    print(f"  Empty frames  : {frames_empty}")
    print(f"  Elapsed       : {elapsed_total:.2f}s")
    print(f"  Average FPS   : {avg_fps:.2f}")

    if frames_read == 0:
        print("FAIL: No frames received.")
        sys.exit(1)
    else:
        print("PASS: Source is readable.")


if __name__ == "__main__":
    main()
