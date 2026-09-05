"""
Full IBVAP pipeline evaluation on D:\\Downloads\\SYSTEMTESTING.mp4.

Tests:
1. Video stream ingestion & decoding
2. YOLO11n object detection & classification
3. ByteTrack multi-object tracking (unique track IDs, track persistence)
4. Virtual Polygon Perimeter intrusion detection
5. Event lifecycle (OPEN, CONFIRMATION after 3 frames, RESOLVED)
6. Evidence snapshot generation with bounding box annotations
7. Performance profiling (latency ms, throughput FPS)
8. Saves annotated visual frames into artifacts directory.
"""

import sys
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path
from collections import Counter, defaultdict

import cv2
import numpy as np
from ultralytics import YOLO

# Add contracts and edge-agent src to sys.path
BASE_DIR = Path(r"d:\Desktop\AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure\ibvap\apps\edge-agent")
CONTRACTS_DIR = Path(r"d:\Desktop\AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure\ibvap\packages\contracts\src")
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(CONTRACTS_DIR))

from src.geometry.zone_engine import point_in_polygon, foot_point, ZoneEngine, load_zones_from_yaml
from src.events.intrusion import IntrusionEngine
from ibvap_contracts.models.detection import BoundingBox, Detection
from ibvap_contracts.models.track import Track
from ibvap_contracts.enums import EventStatus

ARTIFACTS_DIR = Path(r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\cb2c2c83-13de-4915-9792-abaf975e5eae")
video_path = r"D:\Downloads\SYSTEMTESTING.mp4"
model_path = str(BASE_DIR / "yolo11n.pt")
zone_config = str(BASE_DIR / "configs" / "zones" / "demo-camera-01.yaml")

print("=" * 60)
print("IBVAP Surveillance Platform — Video Evaluation")
print(f"Target Video: {video_path}")
print(f"Model: {model_path}")
print(f"Zone Config: {zone_config}")
print("=" * 60)

# 1. Load Zones
zones = load_zones_from_yaml(zone_config)
print(f"Loaded {len(zones)} zones: {[z.name for z in zones]}")
zone_engine = ZoneEngine(zones, ttl_seconds=30.0)
intrusion_engine = IntrusionEngine(
    confirmation_frames=3,
    ttl_seconds=30.0,
    site_id="site-demo-01",
    detector_version="yolo11n",
    tracker_version="bytetrack",
)

# 2. Load YOLO Model
model = YOLO(model_path)

# 3. Open Video
cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration_sec = total_frames / src_fps

print(f"Source: {w}x{h} @ {src_fps:.1f}fps, {total_frames} frames ({duration_sec:.1f}s)")

# We process every 3rd frame (effective 10 fps detection & tracking, standard surveillance rate)
# or process every 2nd frame. Let's process step=2 (15 fps) for high temporal accuracy across 1800 frames.
FRAME_STEP = 2
processed_count = 0
frame_idx = 0

latencies = []
detected_class_counts = Counter()
unique_track_ids = set()
events_generated = []
snapshot_saved_frames = [30, 300, 600, 900, 1200, 1500]
saved_snapshots = []

t_start = time.perf_counter()

# Zone polygon normalized coordinates for perimeter-01
perimeter_poly_norm = [(pt[0], pt[1]) for pt in zones[0].coordinates]  # [(x, y), ...]
perimeter_poly_px = np.array([[int(x * w), int(y * h)] for x, y in perimeter_poly_norm], dtype=np.int32)

print("\nProcessing video frames through surveillance pipeline...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    if frame_idx % FRAME_STEP != 0:
        frame_idx += 1
        continue

    processed_count += 1
    t0 = time.perf_counter()

    # Step A: YOLO + ByteTrack
    results = model.track(
        frame,
        persist=True,
        conf=0.35,
        classes=[0, 1, 2, 3, 5, 7],  # person, bicycle, car, motorcycle, bus, truck
        verbose=False,
    )

    t_infer = (time.perf_counter() - t0) * 1000
    latencies.append(t_infer)

    # Step B: Parse detections & tracks
    current_tracks = []
    active_boxes = []

    if results and len(results) > 0 and results[0].boxes is not None:
        boxes = results[0].boxes
        now_dt = datetime.now(tz=UTC)
        for box in boxes:
            cls_id = int(box.cls[0].item())
            cls_name = model.names.get(cls_id, str(cls_id))
            conf = float(box.conf[0].item())
            track_id = int(box.id[0].item()) if box.id is not None else None

            detected_class_counts[cls_name] += 1
            if track_id is not None:
                unique_track_ids.add(track_id)

            x1_px, y1_px, x2_px, y2_px = box.xyxy[0].cpu().numpy().astype(int)
            active_boxes.append((track_id, cls_name, conf, (x1_px, y1_px, x2_px, y2_px)))

            if track_id is not None:
                bbox_norm = BoundingBox(
                    x1=max(0.0, min(1.0, x1_px / w)),
                    y1=max(0.0, min(1.0, y1_px / h)),
                    x2=max(0.0, min(1.0, x2_px / w)),
                    y2=max(0.0, min(1.0, y2_px / h)),
                )
                current_tracks.append(
                    Track(
                        track_id=track_id,
                        camera_id="demo-camera-01",
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                        bbox=bbox_norm,
                        first_seen=now_dt,
                        last_seen=now_dt,
                        frame_count=1,
                    )
                )

    # Step C: Zone evaluation
    crossings = zone_engine.evaluate(current_tracks)

    # Step D: Intrusion Events
    new_events = intrusion_engine.process(crossings)
    for ev in new_events:
        risk_score = ev.risk.risk_score if ev.risk else None
        events_generated.append((frame_idx, ev.status.value, ev.zone_id, ev.track_ids, risk_score))

    # Step E: Save key visual snapshots for report
    if frame_idx in snapshot_saved_frames or (len(saved_snapshots) < 4 and len(new_events) > 0):
        # Annotate frame
        annotated = frame.copy()
        # Draw perimeter
        is_breached = any(ev.status == EventStatus.OPEN for ev in new_events) or len(crossings) > 0
        poly_color = (0, 0, 240) if is_breached else (0, 220, 0)
        cv2.polylines(annotated, [perimeter_poly_px], isClosed=True, color=poly_color, thickness=2)
        cv2.putText(annotated, "SURVEILLANCE PERIMETER", (perimeter_poly_px[0][0] + 10, perimeter_poly_px[0][1] + 25),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, poly_color, 1)

        # Draw boxes
        for trk_id, cname, conf, (bx1, by1, bx2, by2) in active_boxes:
            # Check foot point inside zone
            foot_x = ((bx1 + bx2) / 2.0) / float(w)
            foot_y = float(by2) / float(h)
            inside = point_in_polygon((foot_x, foot_y), perimeter_poly_norm)
            box_col = (0, 0, 240) if inside else (0, 220, 100)
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), box_col, 2)
            lbl = f"ID:{trk_id} {cname} {int(conf*100)}%" + (" [INTRUDER]" if inside else "")
            cv2.putText(annotated, lbl, (bx1, max(15, by1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # HUD banner
        cv2.rectangle(annotated, (0, 0), (w, 40), (20, 24, 30), -1)
        sec_current = frame_idx / src_fps
        hud_txt = f"IBVAP EDGE AGENT | Time: {sec_current:4.1f}s | Frame {frame_idx}/{total_frames} | Tracks: {len(current_tracks)} | Latency: {t_infer:3.1f}ms"
        cv2.putText(annotated, hud_txt, (10, 25), cv2.FONT_HERSHEY_DUPLEX, 0.48, (0, 230, 255), 1)

        out_fname = f"systemtest_frame_{frame_idx:04d}.jpg"
        out_path = ARTIFACTS_DIR / out_fname
        cv2.imwrite(str(out_path), annotated)
        saved_snapshots.append(out_fname)

    if processed_count % 100 == 0:
        sec_done = frame_idx / src_fps
        avg_lat = np.mean(latencies[-100:])
        print(f"Processed frame {frame_idx}/{total_frames} ({sec_done:.1f}s) | Avg Latency: {avg_lat:.1f}ms | Unique tracks: {len(unique_track_ids)} | Events: {len(events_generated)}")

    frame_idx += 1

cap.release()
t_total = time.perf_counter() - t_start

# Compute Summary Statistics
avg_latency = float(np.mean(latencies)) if latencies else 0.0
p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
p50_latency = float(np.median(latencies)) if latencies else 0.0
proc_fps = processed_count / t_total if t_total > 0 else 0.0

print("\n" + "=" * 60)
print("PIPELINE EXECUTION SUMMARY")
print("=" * 60)
print(f"Total Video Duration: {duration_sec:.1f} seconds ({total_frames} frames)")
print(f"Frames Processed:     {processed_count} frames (step={FRAME_STEP})")
print(f"Processing Time:      {t_total:.2f} seconds")
print(f"Throughput:           {proc_fps:.1f} FPS")
print(f"Latency Mean:         {avg_latency:.1f} ms / frame")
print(f"Latency Median (p50): {p50_latency:.1f} ms / frame")
print(f"Latency 95th (p95):   {p95_latency:.1f} ms / frame")
print(f"Total Unique Tracks:  {len(unique_track_ids)}")
print(f"Total Zone Events:    {len(events_generated)}")
print("\nDetections by Class:")
for cls_name, cnt in detected_class_counts.most_common():
    print(f"  - {cls_name:12s}: {cnt:5d} bounding boxes")

print(f"\nSaved {len(saved_snapshots)} annotated visual frames to:")
for s in saved_snapshots:
    print(f"  - {ARTIFACTS_DIR / s}")

# Save JSON report for reference
report_data = {
    "video_path": video_path,
    "resolution": f"{w}x{h}",
    "duration_sec": duration_sec,
    "total_frames": total_frames,
    "processed_frames": processed_count,
    "throughput_fps": round(proc_fps, 2),
    "latency_mean_ms": round(avg_latency, 2),
    "latency_p50_ms": round(p50_latency, 2),
    "latency_p95_ms": round(p95_latency, 2),
    "unique_track_ids": len(unique_track_ids),
    "events_count": len(events_generated),
    "detected_classes": dict(detected_class_counts),
    "snapshots": saved_snapshots,
    "events_sample": events_generated[:20],
}

with open(ARTIFACTS_DIR / "systemtest_report.json", "w") as f:
    import json
    json.dump(report_data, f, indent=2)

print("\nReport JSON saved successfully.")
