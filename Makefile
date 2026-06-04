# =============================================================================
# Maquita Webmail — Makefile (instalación NATIVA, sin Docker)
# =============================================================================
# El webmail, el correo (Postfix/Dovecot), PostgreSQL y Redis corren de forma
# NATIVA directo sobre el sistema operativo (Debian 13 o similar).
# Docker se usa ÚNICAMENTE para Z-Push (ActiveSync) — ver deploy/z-push/.
# Forma más fácil de instalar todo:  sudo bash deploy/webmail/instalar.sh
# =============================================================================

.DEFAULT_GOAL := help

.PHONY: help instalar install dev build test lint format migrate seed-demo \
        sbom clean gitleaks

# ---------- General -----------------------------------------------------------

## Muestra esta ayuda
help:
	@echo "Maquita Webmail — objetivos disponibles:"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //'
	@echo ""
	@awk '/^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, substr($$0, index($$0,"##")+3) }' $(MAKEFILE_LIST)

## Instalación nativa completa (Debian 13) — ejecutar como root
instalar:
	bash deploy/webmail/instalar.sh

## Instala dependencias de backend + frontend
install:
	cd backend  && pip install -r requirements.txt
	cd frontend && npm ci

## Arranca backend (uvicorn reload) + frontend (vite dev) para desarrollo local
dev:
	@echo "Arrancando backend …"
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Arrancando frontend …"
	cd frontend && npm run dev

## Compila el frontend de producción
build:
	cd frontend && npm run build

## Ejecuta las pruebas del backend (pytest)
test:
	cd backend && python -m pytest -v

## Lint del backend (ruff) + frontend (eslint)
lint:
	cd backend  && ruff check .
	cd frontend && npx eslint .

## Formatea el backend (ruff) + frontend (prettier)
format:
	cd backend  && ruff format .
	cd frontend && npx prettier --write src/

# ---------- Base de datos -----------------------------------------------------

## Aplica las migraciones SQL contra DATABASE_URL
migrate:
	@for f in migrations/*.sql; do \
		echo "Aplicando $$f …"; \
		psql "$(DATABASE_URL)" -f "$$f"; \
	done

## Carga datos de demostración en la base de datos (ejecutar con el venv activo)
seed-demo:
	cd backend && python ../scripts/seed_demo_data.py

# ---------- Seguridad y calidad -----------------------------------------------

## Genera el inventario de software (SBOM, CycloneDX)
sbom:
	cd backend  && pip install cyclonedx-bom && cyclonedx-py environment -o ../sbom-backend.json
	cd frontend && npx @cyclonedx/cyclonedx-npm --output-file ../sbom-frontend.json

## Busca secretos filtrados en el repo (gitleaks)
gitleaks:
	gitleaks detect --source . --verbose

# ---------- Limpieza ----------------------------------------------------------

## Elimina artefactos de compilación y cachés
clean:
	rm -rf frontend/dist frontend/node_modules/.cache
	find backend -type d -name __pycache__ -exec rm -rf {} +
	rm -f sbom-backend.json sbom-frontend.json
