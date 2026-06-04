# =============================================================================
# Maquita Webmail — Makefile
# =============================================================================

.DEFAULT_GOAL := help

.PHONY: help install dev build test lint format migrate seed-demo demo \
        docker-up docker-down docker-build sbom clean gitleaks

# ---------- General -----------------------------------------------------------

## Show this help message
help:
	@echo "Maquita Webmail — available targets:"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //'
	@echo ""
	@awk '/^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, substr($$0, index($$0,"##")+3) }' $(MAKEFILE_LIST)

## Install backend + frontend dependencies
install:
	cd backend  && pip install -r requirements.txt
	cd frontend && npm ci

## Start backend (uvicorn reload) + frontend (vite dev) for local development
dev:
	@echo "Starting backend …"
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting frontend …"
	cd frontend && npm run dev

## Build frontend production bundle
build:
	cd frontend && npm run build

## Run backend test suite (pytest)
test:
	cd backend && python -m pytest -v

## Lint backend (ruff) + frontend (eslint)
lint:
	cd backend  && ruff check .
	cd frontend && npx eslint .

## Auto-format backend (ruff) + frontend (prettier)
format:
	cd backend  && ruff format .
	cd frontend && npx prettier --write src/

# ---------- Database ----------------------------------------------------------

## Run SQL migrations against DATABASE_URL
migrate:
	@for f in migrations/*.sql; do \
		echo "Applying $$f …"; \
		psql "$(DATABASE_URL)" -f "$$f"; \
	done

## Seed synthetic demo data into the database
seed-demo:
	docker compose exec -T backend python -m scripts.seed_demo_data

## Full demo environment: docker up + migrate + seed
demo: docker-up migrate seed-demo
	@echo ""
	@echo "Demo environment ready!  Open http://localhost in your browser."

# ---------- Docker ------------------------------------------------------------

## Start all services via Docker Compose
docker-up:
	docker compose up -d

## Stop all services
docker-down:
	docker compose down

## Build Docker images (no cache)
docker-build:
	docker compose build --no-cache

# ---------- Security & Quality ------------------------------------------------

## Generate Software Bill of Materials (CycloneDX)
sbom:
	cd backend  && pip install cyclonedx-bom && cyclonedx-py environment -o ../sbom-backend.json
	cd frontend && npx @cyclonedx/cyclonedx-npm --output-file ../sbom-frontend.json

## Scan repo for leaked secrets with gitleaks
gitleaks:
	gitleaks detect --source . --verbose

# ---------- Housekeeping ------------------------------------------------------

## Remove build artifacts and caches
clean:
	rm -rf frontend/dist frontend/node_modules/.cache
	find backend -type d -name __pycache__ -exec rm -rf {} +
	rm -f sbom-backend.json sbom-frontend.json
