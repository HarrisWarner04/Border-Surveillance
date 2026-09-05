"""
IBVAP — Interactive Visual Video Analytics & Surveillance Demo.

Features:
  - Real-time video playback window with OpenCV GUI
  - DirectShow (cv2.CAP_DSHOW) backend on Windows to prevent MSMF camera grab errors
  - Continuous loop playback for video files (re-opens cleanly)
  - Resilient frame grab with retry loop (never stops on transient camera lag)
  - Object detection & classification (YOLO) with bounding boxes & confidence
  - Real-time object counter & breakdown panel
  - Multi-object tracking (ByteTrack) with persistent track IDs
  - Virtual polygon fence overlay
  - Real-time intrusion detection (zone breach turns boxes RED and triggers alarm banner)
  - Supports local MP4/AVI videos, RTSP streams, and live Webcams (0)

Usage:
  python scripts/visual_demo.py --source 0                       # Webcam
  python scripts/visual_demo.py --source path/to/video.mp4       # Real video
  python scripts/visual_demo.py --source tests/fixtures/videos/demo_walk.mp4
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IBVAP Live Video Analytics Visual Demo")
    parser.add_argument(
        "--source",
        default="0",
        help="Path to video file, '0' for webcam, or RTSP stream URI",
    )
    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help="YOLO model path or name (e.g. yolo11n.pt, yolo11s.pt, models/yolo26n.pt)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.35,
        help="Confidence threshold (0.0 to 1.0)",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=["person", "car", "motorcycle", "bus", "truck", "bicycle"],
        help="List of class names to detect",
    )
    return parser.parse_args()


def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray casting algorithm to check if normalized (x,y) is inside polygon."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def draw_hud(
    frame: np.ndarray,
    counts: dict[str, int],
    intrusion: bool,
    fps: float,
    latency_ms: float,
    frame_idx: int,
) -> None:
    """Draw top dashboard panel showing object counts, status, and FPS."""
    h, w = frame.shape[:2]

    # Semi-transparent top HUD banner
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 65), (15, 18, 25), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.line(frame, (0, 65), (w, 65), (45, 55, 75), 1)

    # Title & System Status
    cv2.putText(frame, "IBVAP SURVEILLANCE ANALYTICS", (14, 25), cv2.FONT_HERSHEY_DUPLEX, 0.65, (240, 240, 240), 1)

    # Alarm or Secure badge
    if intrusion:
        pulse = int((time.time() * 4) % 2)
        bg_col = (30, 30, 220) if pulse else (20, 20, 160)
        cv2.rectangle(frame, (14, 34), (230, 56), bg_col, -1)
        cv2.putText(frame, "!! ZONE INTRUSION !!", (22, 50), cv2.FONT_HERSHEY_DUPLEX, 0.48, (255, 255, 255), 1)
    else:
        cv2.rectangle(frame, (14, 34), (160, 56), (35, 130, 35), -1)
        cv2.putText(frame, "[SECURE - NO BREACH]", (20, 50), cv2.FONT_HERSHEY_DUPLEX, 0.42, (255, 255, 255), 1)

    # Object count & classification breakdown
    total_objects = sum(counts.values())
    breakdown_parts = [f"{cls}: {cnt}" for cls, cnt in counts.items()]
    breakdown_text = f"Objects: {total_objects}" + (f" ({', '.join(breakdown_parts)})" if breakdown_parts else " (None)")
    cv2.putText(frame, breakdown_text, (250, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 225, 255), 1)

    # Metrics on top right
    stats_text = f"FPS: {fps:4.1f} | Latency: {latency_ms:4.1f}ms | Frame: {frame_idx}"
    cv2.putText(frame, stats_text, (w - 380, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 190, 200), 1)
    cv2.putText(frame, "Press 'Q' to Exit | 'SPACE' to Pause", (w - 380, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 145, 150), 1)


def _clean_source(val: str) -> str:
    """Strip whitespace, quotes, and invisible Windows Unicode formatting characters."""
    bad_chars = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff'\" "
    cleaned = val.strip()
    for ch in bad_chars:
        cleaned = cleaned.replace(ch, "") if ord(ch) > 127 else cleaned
    return cleaned.strip("'\" ")


def open_capture(source_val: str | int) -> cv2.VideoCapture:
    """Open video source using DirectShow on Windows for webcams or OpenCV for files."""
    if isinstance(source_val, str):
        source_val = _clean_source(source_val)
        if source_val.isdigit():
            source_val = int(source_val)

    if isinstance(source_val, int):
        # Prefer DirectShow on Windows to bypass MSMF driver issues
        if sys.platform.startswith("win"):
            cap = cv2.VideoCapture(source_val, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return cap
        return cv2.VideoCapture(source_val)
    else:
        return cv2.VideoCapture(source_val)


def main() -> None:
    args = parse_args()

    # 1. Load YOLO model
    print(f"\n[1/3] Loading detector model: {args.model}...")
    try:
        from ultralytics import YOLO
        model = YOLO(args.model)
        print(f"      Model loaded successfully! Supported classes: {len(model.names)}")
    except Exception as exc:
        print(f"\n[ERROR] Failed to load YOLO model: {exc}")
        print("Ensure ultralytics is installed: uv pip install ultralytics")
        sys.exit(1)

    # 2. Open Video Source (clean invisible Windows clipboard Unicode artifacts)
    raw_source = args.source
    if isinstance(raw_source, str) and not raw_source.strip().isdigit():
        source_val = _clean_source(raw_source)
    elif str(raw_source).strip().isdigit():
        source_val = int(raw_source)
    else:
        source_val = raw_source

    if isinstance(source_val, int):
        print(f"[2/3] Opening Webcam #{source_val} (DirectShow backend)...")
    else:
        print(f"[2/3] Opening Video Source: {source_val}...")

    cap = open_capture(source_val)
    if not cap.isOpened():
        print(f"\n[ERROR] Could not open video source: {source_val}")
        from pathlib import Path
        if isinstance(source_val, str) and not Path(source_val).exists():
            print(f"      File does not exist on disk: {source_val}")
        if source_val == "tests/fixtures/videos/demo_walk.mp4":
            print("Generate the fixture first: python scripts/generate_fixture_video.py")
        sys.exit(1)

    # Target frame timing
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if not source_fps or source_fps <= 0 or source_fps > 60:
        source_fps = 30.0
    frame_delay_ms = max(1, int(1000 / source_fps)) if isinstance(source_val, str) else 1

    # Standard demo perimeter zone polygon: normalized coords [0, 1]
    zone_poly_norm = [
        (0.10, 0.25),
        (0.90, 0.25),
        (0.90, 0.90),
        (0.10, 0.90),
    ]

    window_name = "IBVAP - Live Surveillance Analytics & Detection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1024, 768)

    print("\n[3/3] Starting Live Visual Analysis Window...")
    print("-----------------------------------------------------")
    print(" - Press 'Q' or 'ESC' to close the visual window.")
    print(" - Press 'SPACE' to pause or resume playback.")
    print("-----------------------------------------------------\n")

    frame_idx = 0
    t_prev = time.perf_counter()
    fps = 0.0
    paused = False
    consecutive_empty = 0

    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret or frame is None:
                consecutive_empty += 1
                # If this is a video file, loop back by re-opening cleanly
                if isinstance(source_val, str):
                    cap.release()
                    time.sleep(0.05)
                    cap = open_capture(source_val)
                    consecutive_empty = 0
                    continue
                else:
                    # Webcam transient lag: retry up to 50 times (~2.5 seconds)
                    if consecutive_empty > 50:
                        print("[ERROR] Lost connection to camera stream.")
                        break
                    time.sleep(0.05)
                    continue

            consecutive_empty = 0
            frame_idx += 1
            h, w = frame.shape[:2]

            # Scale zone polygon to frame pixel coordinates
            zone_pts_px = np.array(
                [[int(x * w), int(y * h)] for x, y in zone_poly_norm],
                dtype=np.int32,
            )

            t0 = time.perf_counter()

            # Run YOLO Tracking (ByteTrack)
            try:
                results = model.track(
                    frame,
                    persist=True,
                    conf=args.conf,
                    classes=[k for k, v in model.names.items() if v in args.classes],
                    verbose=False,
                )
            except Exception:
                # Fallback to standard detect if tracking backend has an exception
                results = model.predict(frame, conf=args.conf, verbose=False)

            latency_ms = (time.perf_counter() - t0) * 1000

            # Compute FPS
            now = time.perf_counter()
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # Analyze detections & intrusion
            detected_classes: list[str] = []
            intrusion_detected = False

            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = model.names.get(cls_id, str(cls_id))
                    conf = float(box.conf[0].item())
                    track_id = int(box.id[0].item()) if box.id is not None else None

                    detected_classes.append(cls_name)

                    # Bounding box coords
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                    # Foot point (bottom center of bbox)
                    foot_x_norm = ((x1 + x2) / 2.0) / float(w)
                    foot_y_norm = float(y2) / float(h)

                    # Check if object is inside the restricted zone
                    is_inside_zone = point_in_polygon(foot_x_norm, foot_y_norm, zone_poly_norm)
                    if is_inside_zone:
                        intrusion_detected = True

                    # Color: Red for intruder inside zone, Bright Green for outside
                    box_color = (0, 0, 245) if is_inside_zone else (0, 220, 100)
                    text_color = (255, 255, 255)

                    # Draw Bounding Box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

                    # Label text
                    id_label = f"ID:{track_id} " if track_id is not None else ""
                    zone_status_label = " [INTRUDER]" if is_inside_zone else ""
                    label = f"{id_label}{cls_name} {int(conf * 100)}%{zone_status_label}"

                    # Label background pill
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
                    cv2.rectangle(frame, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, max(0, y1)), box_color, -1)
                    cv2.putText(frame, label, (x1 + 3, max(0, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, text_color, 1)

                    # Foot point marker
                    cv2.circle(frame, ((x1 + x2) // 2, y2), 4, (0, 255, 255), -1)

            # Draw Restricted Perimeter Polygon
            poly_color = (0, 0, 230) if intrusion_detected else (0, 210, 0)
            cv2.polylines(frame, [zone_pts_px], isClosed=True, color=poly_color, thickness=2)
            cv2.putText(
                frame,
                "RESTRICTED SURVEILLANCE PERIMETER",
                (zone_pts_px[0][0] + 10, zone_pts_px[0][1] + 25),
                cv2.FONT_HERSHEY_DUPLEX,
                0.55,
                poly_color,
                1,
            )

            # Class count summary
            counts = dict(Counter(detected_classes))

            # Draw Top HUD
            draw_hud(frame, counts, intrusion_detected, fps, latency_ms, frame_idx)

            # Show frame
            cv2.imshow(window_name, frame)

        # Handle keyboard input
        wait_time = frame_delay_ms if not paused else 50
        key = cv2.waitKey(wait_time) & 0xFF
        if key in (ord("q"), ord("Q"), 27):  # 'q' or ESC
            break
        elif key == ord(" "):  # Spacebar
            paused = not paused

    cap.release()
    cv2.destroyAllWindows()
    print("\nVisual demo terminated cleanly.")


if __name__ == "__main__":
    main()
