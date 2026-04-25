PYTHON ?= ./venv/bin/python
PIP ?= ./venv/bin/pip
PYTEST ?= ./venv/bin/pytest
RUFF ?= ./venv/bin/ruff

.PHONY: setup dev install install-dev run test lint frontend-build verify seed-users migrate migration-status

setup:
	python3 -m venv venv
	$(PIP) install -r requirements-dev.txt
	test -f .env || cp .env.example .env
	$(PYTHON) scripts/migrate.py apply
	$(PYTHON) scripts/manage_users.py seed-defaults
	cd frontend && npm install

dev:
	$(PYTHON) scripts/dev.py

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt

run:
	$(PYTHON) -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

test:
	$(PYTEST) -q

lint:
	$(RUFF) check .

frontend-build:
	cd frontend && npm run build

verify: lint test frontend-build

seed-users:
	$(PYTHON) scripts/manage_users.py seed-defaults

migrate:
	$(PYTHON) scripts/migrate.py apply

migration-status:
	$(PYTHON) scripts/migrate.py status
