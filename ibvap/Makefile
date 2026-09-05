.PHONY: help install install-edge install-central install-dashboard \
        dev dev-edge dev-central dev-dashboard \
        migrate migrate-edge migrate-central \
        test test-contracts test-edge test-central test-dashboard \
        lint lint-edge lint-central lint-dashboard \
        typecheck typecheck-edge typecheck-central typecheck-dashboard \
        format format-edge format-central \
        build docker-up docker-down docker-build docker-logs \
        demo clean

# Default target
help:
	@echo ""
	@echo "IBVAP — Intelligent Border Video Analytics Platform"
	@echo "===================================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install           Install all dependencies"
	@echo "  make migrate           Run all database migrations"
	@echo ""
	@echo "Development:"
	@echo "  make dev-edge          Start edge-agent (hot reload)"
	@echo "  make dev-central       Start central-api (hot reload)"
	@echo "  make dev-dashboard     Start dashboard (Vite dev server)"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all tests"
	@echo "  make test-contracts    Run contracts package tests"
	@echo "  make test-edge         Run edge-agent tests"
	@echo "  make test-central      Run central-api tests"
	@echo "  make test-dashboard    Run dashboard tests"
	@echo ""
	@echo "Quality:"
	@echo "  make lint              Lint all Python services"
	@echo "  make typecheck         Type-check all Python services"
	@echo "  make format            Format all Python services"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up         Start all services in Docker"
	@echo "  make docker-down       Stop all services"
	@echo "  make docker-build      Build all Docker images"
	@echo "  make docker-logs       Tail Docker logs"
	@echo ""
	@echo "Demo:"
	@echo "  make demo              Run primary demo scenario"
	@echo ""

# =============================================================================
# Installation
# =============================================================================

install: install-edge install-central install-dashboard
	@echo "✓ All dependencies installed"

install-edge:
	cd apps/edge-agent && pip install -e ".[dev]"

install-central:
	cd apps/central-api && pip install -e ".[dev]"

install-dashboard:
	cd apps/dashboard && npm install

install-contracts:
	cd packages/contracts && pip install -e ".[dev]"

# =============================================================================
# Database migrations
# =============================================================================

migrate: migrate-edge migrate-central
	@echo "✓ All migrations complete"

migrate-edge:
	cd apps/edge-agent && alembic upgrade head

migrate-central:
	cd apps/central-api && alembic upgrade head

migrate-edge-new:
	@read -p "Migration name: " name; \
	cd apps/edge-agent && alembic revision --autogenerate -m "$$name"

migrate-central-new:
	@read -p "Migration name: " name; \
	cd apps/central-api && alembic revision --autogenerate -m "$$name"

# =============================================================================
# Development servers
# =============================================================================

dev-edge:
	cd apps/edge-agent && uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

dev-central:
	cd apps/central-api && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

dev-dashboard:
	cd apps/dashboard && npm run dev

# =============================================================================
# Testing
# =============================================================================

test: test-contracts test-edge test-central test-dashboard
	@echo "✓ All tests complete"

test-contracts:
	cd packages/contracts && pytest tests/ -v --tb=short

test-edge:
	cd apps/edge-agent && pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

test-central:
	cd apps/central-api && pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

test-dashboard:
	cd apps/dashboard && npm run test

test-e2e:
	cd apps/dashboard && npx playwright test

# =============================================================================
# Linting and type checking
# =============================================================================

lint: lint-edge lint-central
	@echo "✓ Lint complete"

lint-edge:
	cd apps/edge-agent && ruff check src/ tests/

lint-central:
	cd apps/central-api && ruff check src/ tests/

lint-contracts:
	cd packages/contracts && ruff check src/ tests/

typecheck: typecheck-edge typecheck-central
	@echo "✓ Type check complete"

typecheck-edge:
	cd apps/edge-agent && mypy src/

typecheck-central:
	cd apps/central-api && mypy src/

format: format-edge format-central
	@echo "✓ Format complete"

format-edge:
	cd apps/edge-agent && ruff format src/ tests/ && ruff check --fix src/ tests/

format-central:
	cd apps/central-api && ruff format src/ tests/ && ruff check --fix src/ tests/

# =============================================================================
# JSON schema export
# =============================================================================

export-schemas:
	python scripts/contracts/export_json_schema.py
	@echo "✓ JSON schemas exported to packages/contracts/json-schema/"

# =============================================================================
# Docker
# =============================================================================

docker-up:
	docker compose up -d

docker-up-build:
	docker compose up -d --build

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

docker-ps:
	docker compose ps

# Start only infrastructure (DB) for local dev
docker-infra:
	docker compose up -d postgres

docker-infra-down:
	docker compose stop postgres

# =============================================================================
# Demo
# =============================================================================

demo:
	@echo "Starting IBVAP demo scenario..."
	bash scripts/demo/run_demo.sh

# =============================================================================
# Cleanup
# =============================================================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "✓ Clean complete"
