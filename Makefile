.PHONY: dev up down test lint build seed e2e openapi backup ai-prompt ai-skill ai-loadtest net-check clean-alerts

PYTHON ?= backend/.venv/bin/python
COMPOSE ?= docker compose
TRUCKS ?= 3
DEVICES ?= 2
KEEP ?= 14
CONCURRENCY ?= 3

dev:
	$(COMPOSE) up -d --build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

test:
	$(COMPOSE) -f compose.test.yml up -d --wait
	cd backend && $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
	$(COMPOSE) -f compose.test.yml down

lint:
	cd backend && $(PYTHON) -m ruff check .
	cd backend && $(PYTHON) -m ruff format --check .
	cd backend && $(PYTHON) -m mypy app
	cd frontend && npm run verify

build:
	cd frontend && npm run build

seed:
	cd backend && $(PYTHON) -m scripts.seed_demo --trucks $(TRUCKS) --devices $(DEVICES)

e2e:
	cd frontend && npx playwright test

openapi:
	cd backend && $(PYTHON) -m scripts.export_openapi

backup:
	cd backend && $(PYTHON) -m scripts.backup_db --keep $(KEEP)

ai-prompt:
	cd backend && $(PYTHON) -m scripts.agent_prompt

ai-skill:
	cd backend && $(PYTHON) -m scripts.build_agent_skill

ai-loadtest:
	cd backend && $(PYTHON) -m scripts.loadtest_ai --concurrency $(CONCURRENCY)

net-check:
	cd backend && $(PYTHON) -m scripts.network_check

clean-alerts:
	$(COMPOSE) exec -T app python -m scripts.resolve_stale_alerts $(if $(filter 1,$(APPLY)),--apply) $(if $(filter 1,$(KEEP_DEVICES)),--keep-devices)
