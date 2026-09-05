"""
Benchmark the YOLO26n detector: measures latency, throughput, CPU/GPU usage.

Usage:
    python scripts/benchmark_detector.py
    python scripts/benchmark_detector.py --frames 200 --device cuda

Output is written to docs/benchmarks/detector_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark YOLO detector")
    parser.add_argument("--model", default="models/yolo26n.pt")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
        import torch
    except ImportError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"Loading model {args.model} on {args.device}...")
    model = YOLO(args.model)
    dummy = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)

    # Warmup — not included in measurements
    print("Warming up (3 frames)...")
    for _ in range(3):
        model(dummy, verbose=False)

    print(f"Benchmarking {args.frames} frames @ {args.imgsz}px...")
    latencies: list[float] = []
    t_total_start = time.perf_counter()

    for _ in range(args.frames):
        t0 = time.perf_counter()
        model(dummy, verbose=False)
        latencies.append((time.perf_counter() - t0) * 1000)

    t_total = time.perf_counter() - t_total_start
    fps = args.frames / t_total

    results = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "model": args.model,
        "device": args.device,
        "image_size": args.imgsz,
        "frames": args.frames,
        "total_seconds": round(t_total, 3),
        "fps": round(fps, 2),
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 2),
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "min": round(min(latencies), 2),
            "max": round(max(latencies), 2),
        },
        "system": {
            "python": platform.python_version(),
            "os": platform.system(),
            "cuda_available": torch.cuda.is_available(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        },
    }

    # Print summary
    print("\n--- Benchmark Results ---")
    print(f"  Device       : {args.device}")
    print(f"  Model        : {args.model}")
    print(f"  Image size   : {args.imgsz}px")
    print(f"  Frames       : {args.frames}")
    print(f"  Total time   : {t_total:.2f}s")
    print(f"  FPS          : {fps:.2f}")
    print(f"  Latency mean : {results['latency_ms']['mean']}ms")
    print(f"  Latency p50  : {results['latency_ms']['p50']}ms")
    print(f"  Latency p95  : {results['latency_ms']['p95']}ms")
    print("\n  NOTE: These are benchmark targets, NOT production claims.")
    print("        Actual performance depends on hardware and workload.")

    # Save to file
    out_dir = Path("docs/benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"detector_{args.device}_{ts}.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\n  Results saved: {out_file}")


if __name__ == "__main__":
    main()
