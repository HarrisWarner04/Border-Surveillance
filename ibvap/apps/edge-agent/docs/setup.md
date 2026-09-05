# Edge Agent — Setup & Run Guide

## Prerequisites

- Python 3.12.x
- Git
- FFmpeg on PATH (for RTSP diagnostics)

## 1. Create virtual environment

**Windows PowerShell:**
```powershell
cd ibvap\apps\edge-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
cd ibvap/apps/edge-agent
python3.12 -m venv .venv
source .venv/bin/activate
```

## 2. Install PyTorch (do this BEFORE installing the package)

Visit https://pytorch.org/get-started/locally/ and select your platform.

**CPU only (works on any laptop):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

**NVIDIA GPU (CUDA 12.x):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Verify:
```bash
python -c "import torch; print(torch.__version__, 'cuda:', torch.cuda.is_available())"
```

## 3. Install the package

```bash
# From ibvap/apps/edge-agent/
pip install -e ".[dev]"

# Install contracts package (required)
pip install -e "../../packages/contracts"
```

## 4. Verify installation

```bash
python -c "import ultralytics; print('ultralytics:', ultralytics.__version__)"
python -c "import cv2; print('opencv:', cv2.__version__)"
python -c "import pydantic; print('pydantic:', pydantic.__version__)"
```

## 5. Verify YOLO26n

```bash
python scripts/verify_yolo26.py
```

This will auto-download yolo26n.pt if not present.

## 6. Copy environment file

```bash
cp .env.example .env
```

Edit `.env` to set `MODEL_DETECTOR=mock` for Phase 1 (no real model needed for tests).

## 7. Run tests

```bash
# All unit and integration tests (no camera, no GPU required)
pytest tests/ -v -m "unit or integration"

# Unit tests only (fastest)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v
```

## 8. Generate synthetic test video

```bash
python scripts/generate_fixture_video.py
```

Creates `tests/fixtures/videos/demo_walk.mp4`.

## 9. Run the edge agent

```bash
# With mock detector (no model file needed)
MODEL_DETECTOR=mock uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# Or
python -m src.main
```

API docs: http://localhost:8001/docs
Health:   http://localhost:8001/health/live
Metrics:  http://localhost:8001/metrics

## 10. Test RTSP camera (optional)

```bash
# Set URL via env var (never paste credentials in shell history)
$env:RTSP_URL="rtsp://user:pass@192.168.1.100:554/stream"
python scripts/test_rtsp.py --frames 50
```

## 11. Run benchmark

```bash
python scripts/benchmark_detector.py --device cpu --frames 100
```

Results saved to `docs/benchmarks/`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No module named ultralytics` | `pip install -U ultralytics` |
| `No module named torch` | Install PyTorch per step 2 |
| `CUDA available: False` | Expected for CPU-only setup. Check `nvidia-smi` if GPU expected. |
| `No module named ibvap_contracts` | `pip install -e ../../packages/contracts` |
| `yolo26n.pt not found` | Run `python scripts/verify_yolo26.py` to auto-download |
| RTSP fails to open | Run `ffprobe $RTSP_URL` to diagnose independently of OpenCV |
| Track IDs reset | Expected on stream reconnect — per-session reset is by design |
