"""
Test script to probe SYSTEMTESTING.mp4 with YOLO11n.
Inspects scenes at 1-second intervals (every 30 frames) to get a fast overview of what is in the video.
"""
import cv2
import json
from pathlib import Path
from ultralytics import YOLO

video_path = r"D:\Downloads\SYSTEMTESTING.mp4"
model_path = r"d:\Desktop\AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure\ibvap\apps\edge-agent\yolo11n.pt"

model = YOLO(model_path)
cap = cv2.VideoCapture(video_path)

fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"Video: {video_path}")
print(f"Resolution: {w}x{h}, FPS: {fps}, Total Frames: {total_frames}, Duration: {total_frames/fps:.1f}s")

# Sample 1 frame per second (60 samples across the 1 minute video)
detections_by_sec = {}
sample_step = int(fps)

frame_idx = 0
sec = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    if frame_idx % sample_step == 0:
        sec = int(frame_idx / fps)
        res = model.predict(frame, conf=0.25, verbose=False)[0]
        detected = []
        for box in res.boxes:
            cls_id = int(box.cls[0].item())
            cls_name = model.names.get(cls_id, str(cls_id))
            conf = float(box.conf[0].item())
            detected.append((cls_name, round(conf, 2)))
        
        if detected:
            detections_by_sec[sec] = detected
            print(f"Sec {sec:02d} (Frame {frame_idx:04d}): {detected}")
    
    frame_idx += 1

cap.release()
print("\n--- Summary of sampled detections ---")
all_classes = set()
for sec, dets in detections_by_sec.items():
    for name, conf in dets:
        all_classes.add(name)
print(f"Active seconds with detections: {len(detections_by_sec)} / {int(total_frames/fps)}")
print(f"Detected classes: {all_classes}")
