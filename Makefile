# CartIQ developer entrypoints. `make help` lists everything.
SHELL := /bin/bash
PY := apps/api/.venv/bin/python
PIP := apps/api/.venv/bin/pip
PYTHON_BASE ?= $(shell command -v python3.11 || command -v python3)

.DEFAULT_GOAL := help
.PHONY: help env install db-up db-down db-reset migrate generate dev dev-web dev-api \
        seed simulate metrics test test-web test-api test-e2e lint typecheck format ci clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  \033[33m%-14s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "created .env")
	@# Next.js and the Prisma CLI both read .env relative to apps/web, so the
	@# single root .env is linked in rather than duplicated.
	@test -L apps/web/.env || ln -sf ../../.env apps/web/.env

install: env ## Install JS + Python dependencies
	pnpm install
	pnpm --filter @cartiq/web exec prisma generate
	$(PYTHON_BASE) -m venv apps/api/.venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "apps/api[dev]"
	$(PIP) install -q -r requirements.txt

db-up: ## Start Postgres (pgvector) in Docker and wait for health
	docker compose up -d db
	@until docker compose exec -T db pg_isready -U cartiq -d cartiq >/dev/null 2>&1; \
	 do printf '.'; sleep 1; done; echo " db ready"

db-down: ## Stop Postgres
	docker compose down

db-reset: ## Drop and recreate the database (destroys local data)
	docker compose down -v
	$(MAKE) db-up
	$(MAKE) migrate

migrate: ## Apply Prisma migrations and build SQL models
	pnpm --filter @cartiq/web exec prisma migrate deploy
	$(PY) scripts/build_models.py

generate: ## Regenerate the Prisma client
	pnpm --filter @cartiq/web exec prisma generate

dev: db-up ## Start storefront (:3000), console (:8501) and api (:8000)
	@trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-console & $(MAKE) dev-web & wait

dev-web: ## Start the Next.js app on :3000
	pnpm --filter @cartiq/web dev

dev-api: ## Start the FastAPI service on :8000
	$(PY) -m uvicorn cartiq_api.main:app --reload --port 8000 --app-dir apps/api/src

dev-console: ## Start the Streamlit console on :8501
	$(PY) -m streamlit run streamlit_app.py --server.port 8501

seed: ## Load the committed seed sample into Postgres
	$(PY) scripts/seed.py

simulate: ## Generate reproducible simulated sessions (see docs/SIMULATION.md)
	$(PY) scripts/simulate.py

metrics: ## Recompute every number quoted in the README -> reports/metrics.json
	$(PY) scripts/metrics.py

test: test-web test-api ## Run all unit/integration tests

test-web: ## Vitest (web + packages)
	pnpm -r test

test-api: ## pytest with coverage gate
	$(PY) -m pytest apps/api -q

test-e2e: ## Playwright smoke tests
	pnpm --filter @cartiq/web exec playwright test

lint: ## ESLint + Ruff
	pnpm -r lint
	$(PY) -m ruff check apps/api apps/console scripts streamlit_app.py

typecheck: ## tsc + mypy
	pnpm -r typecheck
	$(PY) -m mypy apps/api/src apps/console/cartiq_console

format: ## Prettier + Ruff format
	pnpm format
	$(PY) -m ruff format apps/api apps/console scripts streamlit_app.py

ci: lint typecheck test ## Everything CI runs

clean: ## Remove build artefacts and virtualenvs
	rm -rf node_modules apps/*/node_modules packages/*/node_modules \
	       apps/web/.next apps/api/.venv packages/*/dist
