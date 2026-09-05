# IBVAP — Core Surveillance Phase
## Extremely Detailed Installation + Implementation Runbook
### RTSP → YOLO26n → ByteTrack → Virtual Fence → Intrusion → Evidence → Local Alert

> **Purpose:** This document is the implementation contract for the first working surveillance slice of IBVAP. It is intentionally more detailed than a normal setup guide: an agentic coding system should be able to execute it sequentially, verify each step, and stop at a failing gate instead of jumping ahead.

---

# 0. Scope

## 0.1 What we are building

The first production-style prototype loop is:

```text
RTSP Camera
   ↓
RTSP connection/reconnect manager
   ↓
bounded frame buffer
   ↓
YOLO26n detection
   ↓
ByteTrack tracking
   ↓
per-track state
   ↓
virtual polygon fence
   ↓
outside → inside transition
   ↓
temporal confirmation
   ↓
canonical intrusion event
   ├── evidence snapshot
   ├── local alert
   └── SQLite event persistence
   ↓
metrics + structured logs + health state
```

## 0.2 Core outcome

A person visible in an RTSP stream must be detectable, receive a stable track ID, cross a configured restricted polygon, remain inside long enough to satisfy confirmation rules, and produce exactly one confirmed intrusion event and one initial alert during the configured cooldown.

## 0.3 Explicit non-goals

Do **not** implement these during this phase:

- face recognition
- face watchlists
- production ANPR
- weapon classification/training
- crowd anomaly ML
- cross-camera identity correlation
- cloud synchronization
- Kafka
- Kubernetes
- multi-region deployment
- production mobile application
- central dashboard
- ML-based risk scoring
- federated learning

---

# 1. Agent Operating Contract

The coding agent MUST follow this order:

```text
AUDIT
→ INSTALL
→ VERIFY
→ IMPLEMENT
→ UNIT TEST
→ RUN
→ INSPECT
→ FIX
→ DOCUMENT
→ UPDATE PROGRESS
→ COMMIT
```

Never implement five components and test only at the end.

After every numbered step:

1. run the requested command;
2. inspect the output;
3. fix the first failure;
4. do not hide warnings;
5. record versions/results;
6. update `PROGRESS.md`;
7. commit when the repository is in a stable state.

## 1.1 Stop conditions

Stop and report instead of guessing when:

- Python cannot create/activate the environment;
- PyTorch cannot import;
- CUDA is expected but unavailable;
- YOLO26n cannot load;
- OpenCV cannot open the required source;
- RTSP credentials are missing;
- tracker IDs are absent;
- polygon configuration is invalid;
- tests fail;
- evidence cannot be written;
- SQLite cannot write;
- a dependency requires an incompatible version.

---

# 2. Prerequisites

## 2.1 Recommended baseline

For this ML-heavy edge prototype, use:

- Windows 11 or Linux for development
- Python 3.12 baseline unless the existing repository already standardizes another compatible version
- Git
- virtual environment
- FFmpeg available on PATH for troubleshooting/stream inspection
- NVIDIA GPU + compatible PyTorch/CUDA if GPU inference is available
- CPU fallback must remain possible for development
- enough disk space for model weights, video fixtures, evidence, and logs

Do not assume that having an NVIDIA GPU means PyTorch is using it.

## 2.2 Verify Git

```powershell
git --version
```

Expected:

```text
git version ...
```

If missing, install Git before proceeding.

## 2.3 Verify Python

```powershell
py --version
python --version
```

Choose the repository-supported Python version.

For a clean prototype environment, prefer Python 3.12 unless dependency testing proves another version is better.

## 2.4 Verify pip

```powershell
python -m pip --version
```

Upgrade packaging tools:

```powershell
python -m pip install --upgrade pip setuptools wheel
```

Verify:

```powershell
python -m pip --version
```

## 2.5 Verify FFmpeg

```powershell
ffmpeg -version
ffprobe -version
```

FFmpeg is useful for RTSP diagnostics even if OpenCV performs the actual frame capture.

If FFmpeg is unavailable, document it as a setup failure rather than silently replacing RTSP behavior with a different transport.

---

# 3. Repository Audit Before Installation

Do not immediately create duplicate folders.

From the repository root:

```powershell
git status
Get-ChildItem
```

Inspect:

```powershell
Get-ChildItem -Recurse -Depth 2
```

Look specifically for:

```text
apps/
packages/
src/
tests/
configs/
models/
scripts/
docs/
requirements.txt
pyproject.toml
uv.lock
poetry.lock
package.json
README.md
.env.example
docker-compose.yml
```

## 3.1 Search existing Python configuration

```powershell
Get-ChildItem -Recurse -File |
  Select-String -Pattern "ultralytics|torch|opencv|fastapi|pydantic|pytest"
```

Do not create a second dependency system if one already exists.

## 3.2 Identify the actual edge-agent location

The preferred target structure is:

```text
apps/
  edge-agent/
    src/
    tests/
```

But adapt to the existing repository.

The agent must record:

```text
Repository root:
Python project root:
Existing package manager:
Existing test runner:
Existing application entry point:
Existing configuration mechanism:
Existing logging mechanism:
Existing model directory:
Existing test directory:
```

---

# 4. Create the Python Virtual Environment

## 4.1 Windows PowerShell

From the Python project root:

```powershell
py -3.12 -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, do not permanently weaken machine security. Use the documented user-level execution-policy approach approved by the development machine, or invoke the environment's Python directly.

Verify:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

The executable must point inside:

```text
.venv
```

## 4.2 Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

## 4.3 Never commit the environment

Add to `.gitignore`:

```gitignore
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.env.*
!.env.example
data/evidence/
data/logs/
*.sqlite3
*.db
runs/
```

Do not ignore source configuration files merely to make Git clean.

---

# 5. Install the Base Repository Dependencies

## 5.1 First inspect the existing dependency file

If `pyproject.toml` exists, use the project's declared dependency workflow.

If `requirements.txt` exists:

```powershell
python -m pip install -r requirements.txt
```

Do not overwrite it without auditing it.

## 5.2 Required core packages

The implementation needs, at minimum:

```text
ultralytics
opencv-python
numpy
pydantic
pydantic-settings
PyYAML
pytest
pytest-cov
```

Recommended development tooling:

```text
ruff
mypy
```

Install:

```powershell
python -m pip install -U ultralytics opencv-python numpy pydantic pydantic-settings PyYAML pytest pytest-cov ruff mypy
```

### Headless environments

If the application runs on a server without a display, use the headless Ultralytics/OpenCV option rather than installing GUI dependencies unnecessarily.

Do not mix `opencv-python` and `opencv-python-headless` in the same environment without a specific reason.

---

# 6. PyTorch Installation — Do This Before Debugging YOLO

Ultralytics uses PyTorch. The correct PyTorch build depends on OS, Python, CPU/GPU, and CUDA requirements.

## 6.1 Inspect the machine

Windows:

```powershell
nvidia-smi
```

If this succeeds, record:

```text
GPU:
Driver:
CUDA reported by driver:
```

If it fails, continue with CPU unless GPU is a required acceptance target.

## 6.2 Install PyTorch

Use the official PyTorch installation selector for the target platform and CUDA combination.

Do not copy an old CUDA command from a random tutorial.

After installation:

```powershell
python -c "import torch; print('torch=', torch.__version__); print('cuda_available=', torch.cuda.is_available()); print('cuda=', torch.version.cuda)"
```

If GPU is available:

```powershell
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

## 6.3 PyTorch acceptance gate

CPU target:

```text
torch imports: PASS
cuda_available: False is acceptable
```

GPU target:

```text
torch imports: PASS
cuda_available: True
GPU name prints successfully
```

If GPU was expected but `cuda_available=False`, stop and fix PyTorch/driver compatibility before continuing.

---

# 7. Install and Verify Ultralytics

Ultralytics' current documentation provides the standard installation path:

```powershell
python -m pip install -U ultralytics
```

Verify:

```powershell
python -c "import ultralytics; print(ultralytics.__version__)"
```

Verify the CLI:

```powershell
yolo checks
```

If `yolo` is not found:

```powershell
python -m ultralytics
```

or inspect:

```powershell
python -m pip show ultralytics
```

Do not switch to a GitHub development build unless the project explicitly requires it.

---

# 8. Download and Verify YOLO26n

## 8.1 Model choice

Use:

```text
yolo26n.pt
```

The `n` model is the nano model and is the baseline for this edge prototype.

The model should be obtained through the Ultralytics package/model loader unless the repository has a controlled model-artifact workflow.

## 8.2 First model load

Create:

```text
scripts/verify_yolo26.py
```

Use:

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")

print("model loaded")
print("model task:", model.task)
print("model names:", model.names)
```

Run:

```powershell
python scripts/verify_yolo26.py
```

The first run may download the pretrained weights.

## 8.3 Confirm the weight file

Find it:

```powershell
Get-ChildItem -Recurse -Filter "yolo26n.pt"
```

Do not move model weights into arbitrary directories after the application is already configured.

Preferred repository layout:

```text
models/
  yolo26n.pt
```

If weights are downloaded into a cache, explicitly configure a stable model path or add a model acquisition step.

## 8.4 Model-loading gate

Must pass:

```text
Ultralytics import       PASS
YOLO26n weight load       PASS
task = detect             PASS
class names available     PASS
```

Record:

```text
Ultralytics version:
PyTorch version:
YOLO26n path:
Device:
```

---

# 9. First YOLO26n Image Inference

Before touching RTSP, prove the detector works on a single image.

Use a known test image or repository fixture.

Example CLI:

```powershell
yolo predict model=models/yolo26n.pt source=path/to/test.jpg
```

Or Python:

```python
from ultralytics import YOLO

model = YOLO("models/yolo26n.pt")
results = model("path/to/test.jpg")

for result in results:
    print(result.boxes)
```

## 9.1 Detector acceptance

Confirm:

- process exits normally;
- model loads;
- image is processed;
- detections are returned;
- bounding boxes can be read;
- confidence values exist;
- class IDs exist.

Do not proceed to tracking until this passes.

---

# 10. YOLO26n Detector Contract

Create a repository-owned abstraction.

Do not allow the entire application to call Ultralytics directly.

Preferred:

```text
inference/
  detector.py
  yolo26.py
```

## 10.1 Data model

```python
class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
```

Validation:

```text
x1 < x2
y1 < y2
0 <= confidence <= 1
```

## 10.2 Initial classes

Start with:

```yaml
classes:
  - person
  - car
  - motorcycle
  - truck
```

This is a prototype filter, not the final IBVAP taxonomy.

## 10.3 Detector configuration

Example:

```yaml
model:
  path: models/yolo26n.pt
  device: auto
  confidence_threshold: 0.35
  iou_threshold: 0.50
  image_size: 640

classes:
  - person
  - car
  - motorcycle
  - truck
```

Do not hardcode thresholds in Python.

---

# 11. Detector Implementation

Implement:

```python
class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]:
        ...
```

Then:

```python
class YOLO26Detector:
    ...
```

Responsibilities:

- load model once;
- never reload model per frame;
- convert model output into repository-owned `Detection` objects;
- filter configured classes;
- validate confidence;
- record inference latency;
- raise controlled domain errors when inference fails.

The detector must not:

- save evidence;
- send alerts;
- write SQLite;
- know about zones;
- know about RTSP;
- create intrusion events.

---

# 12. Detector Unit Tests

Test:

```text
valid detection conversion
invalid bbox rejection
confidence range
class filtering
empty detection result
model initialization failure
```

Use mocked Ultralytics results for deterministic unit tests.

Do not require a GPU for unit tests.

---

# 13. Detector Benchmark

Create a small benchmark script.

Measure:

```text
frames processed
total inference time
mean inference latency
p50 latency
p95 latency
effective inference FPS
device
image size
model
```

Do not claim real-time performance until measured.

Run both:

```text
CPU benchmark
GPU benchmark, if available
```

Keep benchmark output in:

```text
docs/benchmarks/
```

Do not commit huge raw video outputs.

---

# 14. OpenCV Installation and Verification

Verify:

```powershell
python -c "import cv2; print(cv2.__version__)"
```

Verify camera/video support:

```powershell
python -c "import cv2; print('FFMPEG:', 'FFMPEG' in cv2.getBuildInformation())"
```

If RTSP is a hard requirement, inspect the OpenCV build information and test an actual RTSP URL.

---

# 15. RTSP Camera Configuration

Never hardcode credentials.

Use environment variables or a secrets/config mechanism.

Example `.env.example`:

```env
CAMERA_ID=demo-camera-01
CAMERA_NAME=Demo Perimeter Camera
RTSP_URL=rtsp://username:password@example-camera/stream
TARGET_FPS=10
RTSP_TRANSPORT=tcp

MODEL_PATH=models/yolo26n.pt
DEVICE=auto
CONF_THRESHOLD=0.35
IOU_THRESHOLD=0.50

ALERT_COOLDOWN_SECONDS=10
EVIDENCE_DIR=data/evidence
DATABASE_PATH=data/events.sqlite3
```

The real `.env` must never be committed.

---

# 16. Camera Contract

Create:

```text
camera/models.py
```

Example:

```python
class CameraConfig(BaseModel):
    camera_id: str
    name: str
    rtsp_url: SecretStr
    enabled: bool = True
    target_fps: int = Field(default=10, ge=1, le=30)
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 30.0
    transport: Literal["tcp", "udp"] = "tcp"
```

Requirements:

- camera ID required;
- URL secret;
- target FPS bounded;
- reconnect parameters bounded;
- transport explicit.

Never print `rtsp_url` directly.

---

# 17. RTSP Connectivity Test — Before Application Integration

Create:

```text
scripts/test_rtsp.py
```

Its only job is:

```text
load URL
→ connect
→ read N frames
→ measure FPS
→ release
→ exit
```

Example behavior:

```text
Connecting camera=demo-camera-01
Connected
Frame 1
Frame 2
...
Frame 100
Average FPS: ...
Disconnect: clean
```

If connection fails, show:

```text
camera_id
failure category
retry count
elapsed time
```

Never show the password.

---

# 18. RTSP Reconnect Manager

Implement a separate component.

State:

```text
DISCONNECTED
CONNECTING
CONNECTED
DEGRADED
BACKOFF
STOPPING
```

Reconnect sequence:

```text
initial delay = 1s
2s
4s
8s
...
maximum = 30s
```

Use bounded exponential backoff.

Reset the backoff after a healthy connection.

Do not reconnect in a tight infinite loop.

---

# 19. RTSP Failure Semantics

Handle:

- unavailable URL;
- authentication failure;
- connection timeout;
- stream disconnect;
- empty frame;
- malformed frame;
- delayed frame;
- camera restart.

Expected:

```text
failure
→ log structured error
→ health = DEGRADED/OFFLINE
→ release resources
→ backoff
→ reconnect
```

No crash loop.

---

# 20. Bounded Frame Buffer

Do not allow an unbounded queue.

Example conceptual contract:

```text
capacity = 2–4 frames
```

For real-time surveillance, stale frames are often worse than dropped frames.

Policy:

```text
new frame arrives
→ if buffer full
   drop oldest frame
→ enqueue newest
```

Track:

```text
frames_received_total
frames_dropped_total
```

Never silently drop frames without a metric.

---

# 21. Frame Metadata

Create a repository-owned frame object:

```python
class FramePacket(BaseModel):
    camera_id: str
    frame_index: int
    captured_at: datetime
    width: int
    height: int
```

The image array itself can remain a runtime object rather than being serialized through Pydantic.

Record:

```text
camera_id
frame_index
capture timestamp
dimensions
```

---

# 22. Target Processing FPS

Camera FPS and processing FPS are different.

Example:

```text
camera produces 25 FPS
application processes target 10 FPS
```

Do not process every frame merely because the camera provides them.

Use frame pacing:

```text
timestamp
→ determine whether enough time passed
→ process
→ otherwise skip/drop
```

The selected policy must be documented.

---

# 23. ByteTrack

Ultralytics provides ByteTrack through:

```text
tracker="bytetrack.yaml"
```

Do not implement a separate tracker from scratch for this phase.

## 23.1 Important tracker rule

Persistent tracking state is valid only for consecutive frames from the **same stream**.

Never share tracker state across cameras.

On stream session restart:

```text
old stream session
→ stop tracker
→ discard old tracker state
→ new stream session
→ initialize new tracker state
```

---

# 24. Tracker Abstraction

Create:

```text
tracking/
  tracker.py
  bytetrack.py
```

Repository interface:

```python
class Track(BaseModel):
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
```

Tracker interface:

```python
class Tracker(Protocol):
    def update(self, frame: np.ndarray) -> list[Track]:
        ...
```

The implementation may internally use:

```python
model.track(frame, persist=True, tracker="bytetrack.yaml")
```

but callers must not depend on Ultralytics result internals.

---

# 25. Tracker Test

Use a deterministic video fixture.

Verify:

```text
same object across consecutive frames
→ same track ID as expected
```

Do not demand perfect ID persistence through severe occlusion during the first acceptance gate.

Measure:

```text
active tracks
ID changes
track creation count
track termination count
```

---

# 26. Tracking Visualization

Before adding geometry, produce a visual debug mode:

```text
bounding box
class
confidence
track ID
```

Example:

```text
person  conf=0.82  ID=17
```

Add FPS and frame number.

This mode is critical for visually proving that the detector and tracker are actually working.

---

# 27. Virtual Fence Configuration

Create:

```text
configs/zones/demo-camera-01.yaml
```

Example:

```yaml
camera_id: demo-camera-01

zones:
  - zone_id: perimeter-01
    name: Outer Perimeter
    type: restricted
    polygon:
      - [0.05, 0.20]
      - [0.95, 0.20]
      - [0.95, 0.90]
      - [0.05, 0.90]
```

Coordinates are normalized:

```text
x ∈ [0, 1]
y ∈ [0, 1]
```

This allows the same configuration to work across different resolutions.

---

# 28. Polygon Validation

Reject:

- fewer than 3 points;
- coordinates outside [0,1];
- malformed coordinate pairs;
- NaN;
- infinite values.

Recommended minimum:

```text
3 vertices
```

For the prototype, use a simple polygon.

Do not silently repair invalid configurations.

---

# 29. Pixel Conversion

For frame width `W` and height `H`:

```python
pixel_x = normalized_x * W
pixel_y = normalized_y * H
```

Keep conversion in one geometry module.

Never scatter this math through the detector/tracker code.

---

# 30. Intrusion Point

For a person bounding box:

```python
foot_x = (x1 + x2) / 2
foot_y = y2
```

This is the bottom-center/foot point.

Reason:

```text
bbox center ≠ ground contact
```

The foot point is the default point used for ground-plane fence logic.

Make the point strategy configurable in the future, but use bottom-center now.

---

# 31. Point-in-Polygon Engine

Create:

```text
geometry/
  point.py
  polygon.py
  zone.py
```

Required function:

```python
point_in_polygon(point, polygon) -> bool
```

Define boundary behavior explicitly.

Recommended:

```text
boundary counts as inside
```

Test:

```text
clearly outside
clearly inside
on edge
on vertex
concave polygon
```

---

# 32. Zone State Per Track

Maintain:

```text
camera_id
zone_id
track_id
previous_state
current_state
consecutive_inside_frames
last_seen
```

State:

```text
OUTSIDE
INSIDE
UNKNOWN
```

Do not infer an intrusion from a single inside observation if temporal confirmation is enabled.

---

# 33. Intrusion Transition

The canonical transition is:

```text
OUTSIDE → INSIDE
```

This is an intrusion candidate.

No event for:

```text
INSIDE → INSIDE
```

unless a future periodic-alert policy explicitly enables it.

Exiting:

```text
INSIDE → OUTSIDE
```

is useful state information but is not an intrusion event.

---

# 34. Temporal Confirmation

Initial configuration:

```yaml
intrusion:
  confirmation_frames: 3
```

Meaning:

```text
frame 1: inside
frame 2: inside
frame 3: inside
→ confirmed intrusion
```

If the track becomes outside before confirmation:

```text
inside count resets
candidate discarded
```

This reduces one-frame false positives from noisy detections.

---

# 35. Track State Lifecycle

A track state must expire.

If:

```text
last_seen > configured timeout
```

remove the state.

Do not let memory grow forever.

On camera restart:

```text
clear all track states for that camera
```

Track IDs are not globally meaningful.

---

# 36. Canonical Event

Create:

```text
events/event.py
events/intrusion.py
```

Example:

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "site_id": "demo-site",
  "camera_id": "demo-camera-01",
  "event_type": "PERIMETER_INTRUSION",
  "status": "OPEN",
  "timestamp_start": "2026-09-04T15:30:00Z",
  "timestamp_end": null,
  "zone_id": "perimeter-01",
  "track_ids": [12],
  "risk": null,
  "evidence_ids": [],
  "model_versions": {
    "detector": "yolo26n",
    "tracker": "bytetrack"
  },
  "metadata": {
    "class_name": "person"
  }
}
```

Use UTC timestamps.

Do not calculate final risk in this phase.

---

# 37. Event ID

Use a UUID or repository-approved unique identifier.

Never use:

```text
camera + timestamp only
```

as the sole identifier.

The event ID must remain stable across:

```text
event
→ evidence
→ database
→ alert
```

---

# 38. Evidence Snapshot

Directory:

```text
data/evidence/
  YYYY/
    MM/
      DD/
        <event-id>/
          snapshot.jpg
          metadata.json
```

Snapshot must be the annotated frame whenever practical.

Annotation should show:

```text
camera
event type
zone
track ID
bbox
timestamp
```

Do not put secrets into the image.

---

# 39. Evidence Metadata

Example:

```json
{
  "event_id": "uuid",
  "camera_id": "demo-camera-01",
  "zone_id": "perimeter-01",
  "track_id": 12,
  "timestamp": "2026-09-04T15:30:00Z",
  "file": "snapshot.jpg",
  "sha256": "..."
}
```

Compute SHA-256 after the final file is written.

Use atomic write strategy where practical:

```text
write temp
→ flush/close
→ hash final bytes
→ rename to final path
```

---

# 40. Local Alert

First implementation:

```text
ConsoleAlertSink
```

Example:

```text
[ALERT] PERIMETER_INTRUSION
camera=demo-camera-01
zone=perimeter-01
track=12
event=...
```

Keep alerting separate from event creation.

Later sinks can include:

```text
desktop notification
webhook
central API
email/SMS
```

Do not add them now.

---

# 41. Alert Cooldown

Initial:

```yaml
alerts:
  cooldown_seconds: 10
```

Cooldown key:

```text
camera_id + zone_id + track_id + event_type
```

Important distinction:

```text
event suppression != alert suppression
```

The system may store events while suppressing duplicate user-facing alerts.

For the initial intrusion flow, avoid generating repeated events while the same track remains continuously inside.

---

# 42. SQLite Event Store

Use SQLite for the edge prototype unless the existing repository already provides an appropriate embedded store.

Minimum fields:

```text
event_id
camera_id
event_type
status
created_at
zone_id
track_ids
evidence_path
schema_version
```

Store JSON fields as JSON text if no richer embedded type is needed.

Create indexes for:

```text
camera_id
created_at
event_type
```

Do not store raw video blobs in SQLite.

---

# 43. Event Store Failure Semantics

If SQLite fails:

```text
log structured error
→ increment metric
→ do not crash the entire video loop unnecessarily
→ retain enough context to diagnose
```

However, if persistence is a hard safety requirement in a later deployment profile, that profile must define a stricter fail-closed policy.

For this prototype, the camera pipeline should remain observable even if a non-critical sink fails.

---

# 44. Structured Logging

Every log should have machine-readable context where possible.

Example fields:

```text
timestamp
level
component
camera_id
event_id
track_id
zone_id
message
```

Never log:

```text
RTSP password
API keys
tokens
.env contents
```

Bad:

```text
Connecting to rtsp://admin:supersecret@camera...
```

Good:

```text
Connecting camera=demo-camera-01
```

---

# 45. Metrics

Implement at minimum:

```text
camera_connected
camera_reconnect_total
frames_received_total
frames_dropped_total
frames_processed_total
inference_latency_ms
pipeline_latency_ms
active_tracks
intrusions_total
alerts_sent_total
alerts_suppressed_total
evidence_write_failures_total
```

The implementation can initially use an in-process metrics registry if the repository has no observability framework.

Do not fabricate metrics.

---

# 46. Health State

Use:

```text
HEALTHY
DEGRADED
OFFLINE
```

Suggested semantics:

### HEALTHY

- stream connected;
- frames are fresh;
- processing heartbeat is active.

### DEGRADED

- reconnecting;
- frame rate is below target;
- processing latency is high;
- non-critical sink failing.

### OFFLINE

- stream unavailable beyond configured threshold;
- no successful frame received.

Health state must be observable through logs and an internal status object.

---

# 47. Graceful Shutdown

Handle:

```text
Ctrl+C
SIGTERM where supported
application stop
```

Shutdown sequence:

```text
stop accepting new frames
→ stop inference loop
→ stop tracker
→ release RTSP capture
→ flush event/evidence work
→ close SQLite
→ emit shutdown log
→ exit
```

Never leave OpenCV windows or camera handles hanging.

---

# 48. Deterministic Video Fixture

Create:

```text
tests/fixtures/videos/
```

The ideal fixture:

```text
person starts outside
→ approaches fence
→ crosses fence
→ remains inside
→ exits
```

The expected result:

```text
1 confirmed intrusion
1 initial alert
0 alert spam while continuously inside
```

If a real security video cannot be committed due to licensing/privacy, generate a synthetic fixture or use an appropriately licensed test asset.

Maintain an asset manifest:

```text
filename
source
license
date acquired
purpose
hash
```

---

# 49. Unit Test Matrix

## Camera

```text
valid config
invalid URL
invalid target FPS
secret not exposed
```

## Geometry

```text
inside
outside
edge
vertex
invalid polygon
normalized coordinate validation
```

## Detector

```text
valid output
empty output
invalid bbox
confidence validation
class filtering
```

## Tracker

```text
track ID extraction
empty tracks
state reset
camera isolation
```

## Intrusion

```text
outside → inside
inside → inside
inside → outside
confirmation not reached
confirmation reached
track timeout
```

## Alert

```text
first alert sent
cooldown suppression
different track allowed
different zone allowed
```

## Evidence

```text
directory creation
snapshot write
metadata write
hash correctness
atomic/partial-write handling
```

## Store

```text
insert
query
duplicate ID handling
database error handling
```

---

# 50. Integration Test Without Physical RTSP

Do not make the entire test suite depend on a physical camera.

Build an integration pipeline using:

```text
video fixture
→ frame reader
→ detector
→ tracker
→ geometry
→ intrusion
→ event
→ evidence
→ SQLite
→ alert sink
```

The source can be an MP4 fixture.

This is the deterministic CI gate.

---

# 51. Real RTSP Acceptance Test

Only after the fixture integration test passes.

Checklist:

```text
[ ] connect
[ ] receive frames
[ ] measured FPS
[ ] YOLO26n detections
[ ] ByteTrack IDs
[ ] fence visible
[ ] crossing detected
[ ] temporal confirmation
[ ] event created
[ ] evidence written
[ ] alert emitted
[ ] no alert spam
[ ] camera disconnect detected
[ ] reconnect succeeds
[ ] shutdown clean
```

Record the test result in:

```text
docs/acceptance/core-surveillance-YYYY-MM-DD.md
```

---

# 52. Failure Injection

Explicitly test:

```text
RTSP unavailable
RTSP disconnect
slow stream
empty frame
detector exception
evidence disk failure
SQLite failure
alert failure
invalid zone
malformed config
```

Expected generic behavior:

```text
failure
→ structured log
→ metric
→ health update
→ controlled recovery or safe shutdown
```

Never silently swallow exceptions.

---

# 53. Performance Benchmark

Measure the complete loop, not only model inference.

Record:

```text
camera FPS
target processing FPS
actual processing FPS
detector latency p50
detector latency p95
end-to-end latency p50
end-to-end latency p95
CPU usage
RAM usage
GPU usage if available
GPU memory if available
frame drop count
```

Benchmark:

```text
CPU
GPU if available
```

At least one representative resolution must be documented.

Do not state:

```text
"real time"
"production ready"
"99% accurate"
```

unless measured and supported by evidence.

---

# 54. Debug Visualization Mode

Provide a local development mode that shows:

```text
live/fixture frame
detections
track IDs
zone polygon
foot point
intrusion state
FPS
health
```

Example overlay:

```text
CAMERA: demo-camera-01
FPS: 9.8
HEALTH: HEALTHY

ID 12 person 0.84
ZONE perimeter-01: INSIDE
```

This mode is for development/demo and should not be required for headless operation.

---

# 55. Configuration Hierarchy

Recommended:

```text
defaults
  ↓
config YAML
  ↓
environment variables
  ↓
explicit CLI overrides
```

Do not scatter configuration across source files.

Important configurable values:

```text
RTSP URL
camera ID
target FPS
model path
device
confidence threshold
IoU threshold
image size
tracker config
zone polygons
confirmation frames
alert cooldown
evidence directory
database path
log level
```

---

# 56. Device Selection

Support:

```text
auto
cpu
cuda
```

Behavior:

```text
auto:
  CUDA available → GPU
  otherwise → CPU
```

If user explicitly selects `cuda` but CUDA is unavailable:

```text
fail fast with clear error
```

Do not silently fall back from explicit GPU configuration.

---

# 57. Model Lifecycle

Load YOLO26n once at process startup:

```text
startup
→ validate model
→ load model
→ warm up if configured
→ enter frame loop
```

Do not do:

```text
for every frame:
    model = YOLO(...)
```

That is unacceptable.

---

# 58. Optional Model Warmup

After loading, optionally run one dummy frame through inference.

Record:

```text
cold-start latency
warm inference latency
```

Do not include cold-start latency in the normal steady-state FPS metric.

---

# 59. Stream Session IDs

Every RTSP connection session should have a unique internal session ID.

Example:

```text
camera=demo-camera-01
session=uuid
```

Use it for diagnostics.

On reconnect:

```text
session changes
tracker state resets
track state resets
```

This prevents stale tracking state from leaking between stream sessions.

---

# 60. Camera Isolation

Each camera must have its own:

```text
RTSP connection
frame buffer
detector runtime state if needed
tracker state
zone state
health state
metrics labels
```

Do not use one global tracker for all cameras.

---

# 61. Concurrency Model

Start simple.

Preferred prototype:

```text
one camera worker
  → capture
  → bounded buffering
  → inference
  → tracking
  → geometry
  → event sinks
```

For multiple cameras later:

```text
camera worker per stream
shared model pool only if benchmarked
central event bus
```

Do not prematurely introduce Kafka or distributed queues.

---

# 62. Backpressure

The pipeline must define what happens when inference is slower than the incoming stream.

Preferred real-time policy:

```text
capture continues
→ bounded queue
→ oldest stale frame dropped
→ newest frame processed
```

Measure dropped frames.

Do not allow:

```text
unbounded queue
```

because latency can grow indefinitely.

---

# 63. Event Ordering

For each event:

```text
event_id generated
→ evidence generated
→ event persisted
→ alert emitted
```

or another explicitly documented order.

The order must be deterministic.

If alert is emitted before persistence, document why.

For this prototype, prefer ensuring the event/evidence object exists before alerting.

---

# 64. Evidence and Event Consistency

Do not create an event referencing a nonexistent evidence path.

Recommended:

```text
create event object
→ write evidence
→ attach evidence ID/path
→ persist event
→ alert
```

If evidence fails:

```text
event remains diagnosable
evidence failure metric increments
alert policy follows configured reliability rule
```

---

# 65. No One-Event-Per-Frame Rule

This is mandatory.

Incorrect:

```text
frame 1 inside → event
frame 2 inside → event
frame 3 inside → event
...
```

Correct:

```text
outside
→ candidate
→ confirmation
→ one intrusion event
→ remain inside
→ no repeated intrusion event
→ exit
```

---

# 66. No One-Alert-Per-Frame Rule

Also mandatory.

Cooldown and state transitions must prevent alert storms.

Test specifically:

```text
person remains inside for 60 seconds
```

Expected:

```text
not 600 alerts
```

The exact number of allowed repeat alerts must be controlled by explicit policy.

---

# 67. Repository Structure

Preferred final slice:

```text
apps/
  edge-agent/
    src/
      main.py
      config/
        settings.py
      camera/
        models.py
        rtsp_client.py
        reconnect.py
      video/
        frame.py
        frame_buffer.py
        fps.py
      inference/
        detector.py
        yolo26.py
      tracking/
        tracker.py
        bytetrack.py
      geometry/
        point.py
        polygon.py
        zone.py
      events/
        event.py
        intrusion.py
        dedup.py
      alerts/
        base.py
        local.py
        cooldown.py
      evidence/
        snapshot.py
        storage.py
      observability/
        metrics.py
        logging.py
      health/
        state.py
    tests/
      unit/
      integration/
      fixtures/

packages/
  contracts/
    events/
    geometry/
    camera/
    json-schema/

configs/
  cameras/
  zones/

models/
  yolo26n.pt

scripts/
  verify_yolo26.py
  test_rtsp.py
  benchmark_detector.py

data/
  evidence/
  logs/

docs/
  benchmarks/
  acceptance/

PROGRESS.md
```

Adapt rather than duplicate.

---

# 68. Main Application Lifecycle

`main.py` should orchestrate components, not contain all implementation logic.

Conceptual:

```python
def main():
    config = load_config()

    validate_config(config)

    camera = CameraClient(config.camera)
    detector = YOLO26Detector(config.model)
    tracker = ByteTrackTracker(config.tracker)
    zones = ZoneEngine(config.zones)
    event_store = SQLiteEventStore(config.database)
    evidence = EvidenceStore(config.evidence)
    alerts = ConsoleAlertSink()
    health = HealthState()
    metrics = Metrics()

    run_pipeline(
        camera=camera,
        detector=detector,
        tracker=tracker,
        zones=zones,
        event_store=event_store,
        evidence=evidence,
        alerts=alerts,
        health=health,
        metrics=metrics,
    )
```

The real code must use proper lifecycle/context management.

---

# 69. Suggested Implementation Sequence

Execute exactly:

```text
0  repository audit
1  environment/dependencies
2  camera contract
3  RTSP client
4  bounded frame pipeline
5  YOLO26n detector
6  detector benchmark
7  ByteTrack
8  tracking visualization
9  zone configuration
10 geometry engine
11 intrusion transition
12 temporal confirmation
13 canonical event
14 evidence snapshot
15 local alert
16 cooldown/deduplication
17 SQLite store
18 metrics/logging
19 health state
20 graceful shutdown
21 deterministic fixtures
22 full integration
23 real RTSP acceptance
24 failure injection
25 performance benchmark
26 security review
27 minimal development UI
28 documentation/handoff
```

Never jump from step 5 directly to a dashboard.

---

# 70. Progress File

Create:

```text
PROGRESS.md
```

Template:

```markdown
# Core Surveillance Progress

## Current Step
0

## Environment
- OS:
- Python:
- pip:
- PyTorch:
- CUDA:
- GPU:
- Ultralytics:
- OpenCV:

## Completed
- [ ] Repository audit
- [ ] Environment
- [ ] Dependencies
- [ ] YOLO26n verification
- [ ] RTSP
- [ ] Frame pipeline
- [ ] Detector
- [ ] ByteTrack
- [ ] Geometry
- [ ] Intrusion
- [ ] Evidence
- [ ] Alert
- [ ] SQLite
- [ ] Observability
- [ ] Integration
- [ ] RTSP acceptance

## Current Blocker
None

## Last Verified Command
...

## Last Verified Result
...

## Next Action
...
```

Update it after every implementation step.

---

# 71. Definition of Done

The core phase is complete only when all are true:

- [ ] application starts using documented commands;
- [ ] one RTSP stream is configurable without source changes;
- [ ] credentials are not hardcoded;
- [ ] reconnect works after temporary failure;
- [ ] frame pipeline is bounded;
- [ ] YOLO26n loads successfully;
- [ ] detector returns validated detections;
- [ ] ByteTrack assigns per-camera IDs;
- [ ] tracking visualization works;
- [ ] virtual polygon is configurable;
- [ ] point-in-polygon tests pass;
- [ ] bottom-center foot point is used;
- [ ] outside→inside transition is detected;
- [ ] temporal confirmation works;
- [ ] canonical event is created;
- [ ] event includes camera/zone/track/timestamp/model metadata;
- [ ] annotated evidence snapshot is stored;
- [ ] SHA-256 is recorded;
- [ ] local alert works;
- [ ] cooldown prevents alert spam;
- [ ] SQLite persistence works;
- [ ] FPS/latency/health metrics work;
- [ ] structured logs work;
- [ ] secrets never appear in logs;
- [ ] graceful shutdown works;
- [ ] deterministic integration test works without a physical camera;
- [ ] real RTSP acceptance test passes;
- [ ] reconnect test passes;
- [ ] failure injection is documented;
- [ ] benchmark report exists;
- [ ] no unsupported performance/accuracy claims are made.

---

# 72. Golden Demo

The final demo should show exactly:

```text
START EDGE AGENT
       ↓
CAMERA CONNECTS
       ↓
LIVE STREAM
       ↓
YOLO26n DETECTS PERSON
       ↓
ByteTrack ASSIGNS ID
       ↓
PERSON APPROACHES FENCE
       ↓
FOOT POINT ENTERS POLYGON
       ↓
3 CONSECUTIVE INSIDE OBSERVATIONS
       ↓
PERIMETER_INTRUSION
       ↓
ANNOTATED SNAPSHOT
       ↓
LOCAL ALERT
       ↓
SQLITE EVENT
       ↓
PERSON REMAINS INSIDE
       ↓
NO ALERT SPAM
       ↓
PERSON EXITS
       ↓
CAMERA DISCONNECT
       ↓
HEALTH = DEGRADED/OFFLINE
       ↓
RECONNECT
       ↓
PIPELINE RESUMES
```

---

# 73. Troubleshooting Matrix

## `No module named ultralytics`

```powershell
python -m pip show ultralytics
```

If absent:

```powershell
python -m pip install -U ultralytics
```

Confirm the correct `.venv` is active.

---

## `No module named torch`

```powershell
python -m pip show torch
```

Install the correct PyTorch build for the platform.

---

## `CUDA available = False`

Check:

```powershell
nvidia-smi
```

Then:

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

Do not assume the installed NVIDIA driver automatically provides a usable PyTorch CUDA runtime.

---

## YOLO26n cannot load

Check:

```powershell
python -c "from ultralytics import YOLO; YOLO('yolo26n.pt'); print('OK')"
```

Then inspect:

```powershell
python -m pip show ultralytics
```

If the model was downloaded into a cache, identify the actual path and make the application configuration explicit.

---

## OpenCV imports but RTSP fails

Test:

```powershell
ffprobe "rtsp://..."
```

Do not paste the real password into logs or issue trackers.

Then test OpenCV separately.

Possible causes:

```text
URL
credentials
network
camera codec
transport
firewall
RTSP server
OpenCV/FFmpeg backend
```

---

## Track IDs are missing

Verify:

```text
model = YOLO("yolo26n.pt")
results = model.track(frame, persist=True, tracker="bytetrack.yaml")
```

Check that:

```text
result.boxes
result.boxes.id
```

are handled safely when no tracks exist.

---

## IDs reset unexpectedly

Check:

```text
persist=True
```

and verify that frames are consecutive from the same camera session.

Resetting IDs after reconnect is expected.

---

## Intrusion fires repeatedly

Check:

```text
outside→inside transition
temporal confirmation
track state
event deduplication
alert cooldown
```

Never solve it by simply hiding all alerts.

---

## Evidence file is missing

Check:

```text
directory creation
permissions
disk space
atomic write
exception logging
```

Increment:

```text
evidence_write_failures_total
```

---

# 74. Security Checklist

Before declaring completion:

```text
[ ] no RTSP password in source
[ ] no RTSP password in Git history
[ ] no API keys in source
[ ] .env ignored
[ ] logs redact secrets
[ ] evidence paths do not expose credentials
[ ] SQLite path is controlled
[ ] config validation exists
[ ] malformed zone rejected
[ ] file paths are normalized
[ ] evidence writes cannot escape evidence root
[ ] oversized/invalid input handling exists
```

For later production hardening, add:

```text
TLS
authentication
RBAC
audit logging
encrypted evidence
retention policy
secure secret storage
signed model artifacts
container hardening
network segmentation
```

These are outside the initial core implementation.

---

# 75. Model and Asset Governance

Maintain:

```text
models/manifest.yaml
```

Example:

```yaml
models:
  - name: yolo26n
    file: models/yolo26n.pt
    task: detect
    source: Ultralytics
    acquired_at: "YYYY-MM-DD"
    sha256: "..."
```

For test videos/images maintain:

```text
data/asset-manifest.yaml
```

Record:

```text
asset
source
license
purpose
acquired date
hash
```

Do not commit random internet videos without verifying their licensing.

---

# 76. Dependency Locking

Once installation succeeds:

```text
freeze/lock dependencies
```

depending on the repository's package manager.

For a simple requirements workflow:

```powershell
python -m pip freeze > requirements-lock.txt
```

Do not automatically treat `pip freeze` as the ideal long-term dependency strategy if the repository already uses Poetry, uv, or a `pyproject.toml` lock workflow.

The goal is reproducibility.

---

# 77. Reproducible Setup Test

After the environment works:

```text
delete/recreate .venv
install from repository dependency definition
load YOLO26n
run unit tests
run integration test
```

This catches accidental dependencies that existed only in the developer's original environment.

---

# 78. CI Requirements

The CI pipeline should eventually run:

```text
lint
type check
unit tests
integration tests
configuration validation
```

The CI pipeline must not require:

```text
physical RTSP camera
NVIDIA GPU
private credentials
```

A separate hardware acceptance job can run GPU/RTSP tests.

---

# 79. Minimum Test Coverage Bar

Set an explicit minimum coverage target for the core domain logic.

Recommended initial gate:

```text
>= 80% line coverage
```

Focus especially on:

```text
geometry
intrusion transitions
deduplication
configuration
event serialization
evidence metadata
```

Do not game coverage by testing trivial getters while leaving state transitions untested.

---

# 80. Final Implementation Review

Before moving to advanced analytics, ask:

### Architecture

```text
Is the main loop modular?
Are camera/tracker states isolated?
Are contracts explicit?
```

### ML

```text
Does YOLO26n load deterministically?
Are inference measurements recorded?
Are thresholds configurable?
```

### Tracking

```text
Are IDs per camera?
Does tracker state reset on reconnect?
```

### Geometry

```text
Is normalized configuration validated?
Is foot-point logic tested?
```

### Events

```text
Is OUTSIDE→INSIDE the canonical trigger?
Is confirmation temporal?
Is duplicate generation prevented?
```

### Evidence

```text
Can every event be traced to a snapshot?
Is the hash stored?
```

### Reliability

```text
Does RTSP reconnect?
Does one component failure kill the whole process?
Is health visible?
```

### Security

```text
Are credentials protected?
Are logs safe?
Are files constrained to intended directories?
```

---

# 81. What Comes Next

Only after this phase passes its Definition of Done should the project move to:

```text
Phase 2:
central API
multi-camera management
operator dashboard
```

Then:

```text
Phase 3:
advanced analytics
ANPR
face/watchlist workflows
weapon detection
crowd/vehicle anomaly
```

Then:

```text
Phase 4:
risk engine
cross-camera correlation
```

Then:

```text
Phase 5:
deployment hardening
security
retention
audit
scaling
```

The core surveillance loop is the foundation. Do not build advanced analytics on top of an unreliable RTSP/detection/tracking/event pipeline.
