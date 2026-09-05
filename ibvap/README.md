# IBVAP — Intelligent Border Video Analytics Platform

**SIH 2026 | Problem Statement #187 | Ministry of Home Affairs**

> IBVAP makes existing CCTV intelligent. It detects, tracks, and understands objects locally at the edge, calculates explainable risk scores, triggers immediate alerts, stores evidence locally, and synchronizes securely with a central command center — even when the network is unavailable.

---

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard:   http://localhost:5173
- Central API: http://localhost:8000/docs
- Edge Agent:  http://localhost:8001/docs

## Quick Start (Local Dev)

```bash
# Python services
make install
make migrate

# Start services (two terminals)
make dev-central
make dev-edge

# Frontend (third terminal)
make dev-dashboard
```

## Demo

```bash
make demo
```

See [docs/demo/DEMO.md](docs/demo/DEMO.md) for the full judge demo runbook.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system diagrams and data flows.

## Project Structure

```
ibvap/
├── apps/
│   ├── edge-agent/      Python FastAPI — video AI, local detection, events
│   ├── central-api/     Python FastAPI — HQ aggregation, auth, dashboard API
│   └── dashboard/       React + TypeScript — command center UI
├── packages/
│   └── contracts/       Canonical Pydantic models, enums, JSON schemas
├── simulator/           Sample videos, synthetic scenarios
├── infra/               Docker, Postgres init, monitoring
├── scripts/             Bootstrap, demo, schema export
└── docs/                Architecture, API, deployment, demo
```

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0     | ✅ Done | Repository scaffold |
| 1     | ✅ Done | Foundation: config, health, DB, migrations |
| 2     | ⏳      | Camera + video pipeline |
| 3     | ⏳      | Tracking + zones |
| 4     | ⏳      | Event + risk engine |
| 5     | ⏳      | Evidence + local response |
| 6     | ⏳      | Offline + sync |
| 7     | ⏳      | Command dashboard |
| 8     | ⏳      | Security hardening |
| 9     | ⏳      | Optional AI modules (ANPR, face) |
| 10    | ⏳      | Benchmarks + demo hardening |

## Technology Stack

- **Edge AI:** Python 3.12, FastAPI, OpenCV, Ultralytics YOLO, ByteTrack, SQLite
- **Central:** Python 3.12, FastAPI, PostgreSQL 17, Alembic
- **Dashboard:** React 19, TypeScript, Vite, Tailwind CSS, Leaflet
- **Infra:** Docker Compose, Nginx

## License

See [LICENSE](LICENSE). Model licenses: see [models/README.md](models/README.md).
