# IBVAP — Project Progress

## Current Phase
**Phase 1 — Foundation** (IN PROGRESS)

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Repository scaffold | ✅ Complete | Monorepo structure created |
| 1 — Foundation | ✅ Complete | Config, health, DB, migrations, contracts |
| 2 — Camera + video pipeline | ⏳ Pending | |
| 3 — Tracking + zones | ⏳ Pending | |
| 4 — Event + risk engine | ⏳ Pending | |
| 5 — Evidence + local response | ⏳ Pending | |
| 6 — Offline + sync | ⏳ Pending | |
| 7 — Command dashboard | ⏳ Pending | |
| 8 — Security hardening | ⏳ Pending | |
| 9 — Optional AI modules | ⏳ Pending | |
| 10 — Benchmarks + demo hardening | ⏳ Pending | |

## Active Task
Phase 1 complete — awaiting Phase 2 start.

## Completed Tasks
- [x] Monorepo root scaffold
- [x] `.env.example`, `.gitignore`, `Makefile`, `docker-compose.yml`
- [x] `packages/contracts` — canonical Pydantic models, enums, all domain types
- [x] `apps/edge-agent` — FastAPI app, config, health endpoints, SQLite + Alembic
- [x] `apps/central-api` — FastAPI app, config, health endpoints, PostgreSQL + Alembic, auth skeleton
- [x] `apps/dashboard` — Vite + React + TypeScript + Tailwind scaffold
- [x] Docker Compose (postgres, edge-agent, central-api, dashboard)
- [x] Simulator scaffold + scenario stubs
- [x] Unit tests: contracts validation, enum coverage
- [x] Health endpoint tests: edge-agent, central-api

## Blocked Tasks
None.

## Known Issues
None at this phase.

## Architecture Decisions Made
- **Package manager:** pip + pyproject.toml (uv-compatible). Virtual envs per service.
- **Edge DB:** SQLite with aiosqlite for async. Alembic for migrations.
- **Central DB:** PostgreSQL 17.11 via asyncpg. Alembic for migrations.
- **ORM:** SQLAlchemy 2.x async with mapped dataclass style.
- **Contracts:** `packages/contracts` is the single source of truth for all cross-service types.
- **Logging:** structlog with JSON renderer in production, console in development.
- **Frontend bundler:** Vite 6.x.
- **Map library:** Leaflet (no API key required for demo).
- **Auth:** JWT (python-jose) + bcrypt. RBAC enforced server-side.
- **Detector Phase 1:** MockDetector only (no model weights needed until Phase 2).

## Last Successful Test Command
```
# contracts
cd packages/contracts && pytest tests/ -v

# edge-agent
cd apps/edge-agent && pytest tests/ -v

# central-api
cd apps/central-api && pytest tests/ -v
```

## Last Successful Demo Command
N/A — Phase 2+ required.

## Pending Decisions
- Redis: defer until Phase 6 (sync) — evaluate if needed.
- YOLO version: confirm YOLO11n vs YOLO26n once Phase 2 begins (verify Ultralytics availability).
- Frontend E2E: Playwright setup in Phase 7.
