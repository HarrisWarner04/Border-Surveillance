"""
Verify YOLO26n model loads and runs inference correctly.

Usage:
    python scripts/verify_yolo26.py
    python scripts/verify_yolo26.py --image path/to/test.jpg

Stop conditions (will sys.exit(1)):
  - ultralytics cannot be imported
  - model file cannot be loaded
  - inference on a dummy frame fails
  - no detections are returned on a test image (warning only)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify YOLO26n installation")
    parser.add_argument("--model", default="models/yolo26n.pt", help="Path to .pt weights")
    parser.add_argument("--image", default=None, help="Optional test image path")
    parser.add_argument("--device", default="auto", help="auto | cpu | cuda | mps")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # 1. Import check
    # -----------------------------------------------------------------------
    print("Step 1: Checking ultralytics import...")
    try:
        import ultralytics
        print(f"  ✓ ultralytics {ultralytics.__version__}")
    except ImportError as exc:
        print(f"  ✗ ultralytics not found: {exc}")
        print("    Fix: pip install -U ultralytics")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 2. PyTorch check
    # -----------------------------------------------------------------------
    print("Step 2: Checking PyTorch...")
    try:
        import torch
        print(f"  ✓ torch {torch.__version__}")
        print(f"  CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("  Running on CPU (acceptable for development)")
    except ImportError as exc:
        print(f"  ✗ torch not found: {exc}")
        print("    Fix: install PyTorch from https://pytorch.org/get-started/locally/")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 3. Model load
    # -----------------------------------------------------------------------
    print(f"Step 3: Loading model from {args.model}...")
    model_path = Path(args.model)
    if not model_path.exists() and not args.model.endswith(".pt"):
        print(f"  ✗ Model file not found: {model_path}")
        sys.exit(1)

    try:
        from ultralytics import YOLO
        model = YOLO(args.model)
        print(f"  ✓ Model loaded  task={model.task}")
        names = list(model.names.values())[:5]
        print(f"  ✓ Classes (first 5): {names}")
    except Exception as exc:
        print(f"  ✗ Model load failed: {exc}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 4. Dummy inference (warmup)
    # -----------------------------------------------------------------------
    print("Step 4: Running dummy inference (warmup)...")
    import numpy as np
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    t0 = time.perf_counter()
    try:
        results = model(dummy, verbose=False)
        latency_ms = (time.perf_counter() - t0) * 1000
        print(f"  ✓ Inference OK  latency={latency_ms:.1f}ms")
    except Exception as exc:
        print(f"  ✗ Inference failed: {exc}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 5. Optional test image
    # -----------------------------------------------------------------------
    if args.image:
        import cv2
        print(f"Step 5: Running inference on {args.image}...")
        img = cv2.imread(args.image)
        if img is None:
            print(f"  ✗ Cannot read image: {args.image}")
            sys.exit(1)
        t0 = time.perf_counter()
        results = model(img, verbose=False)
        latency_ms = (time.perf_counter() - t0) * 1000
        n_dets = sum(len(r.boxes) for r in results)
        print(f"  ✓ Detections: {n_dets}  latency={latency_ms:.1f}ms")
        if n_dets == 0:
            print("  ⚠ Warning: no detections — expected for a blank/synthetic image")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n--- YOLO26n Verification Summary ---")
    print(f"  ultralytics version : {ultralytics.__version__}")
    print(f"  torch version       : {torch.__version__}")
    print(f"  model path          : {args.model}")
    print(f"  CUDA available      : {torch.cuda.is_available()}")
    print(f"  model task          : {model.task}")
    print("\n  ✓ All checks passed. YOLO26n is ready.")


if __name__ == "__main__":
    main()
