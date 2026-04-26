PYTHON ?= ./venv/bin/python
PIP ?= ./venv/bin/pip
PYTEST ?= ./venv/bin/pytest
RUFF ?= ./venv/bin/ruff

.PHONY: setup dev install install-dev update run test lint frontend-lint frontend-build script-check ui-smoke update-locks verify seed-users migrate migration-status

setup:
	python3 -m venv venv
	@if [ -f requirements-dev.lock ]; then \
		$(PIP) install -r requirements-dev.txt -c requirements-dev.lock; \
	else \
		$(PIP) install -r requirements-dev.txt; \
	fi
	$(PYTHON) scripts/ensure_runtime_config.py
	$(PYTHON) scripts/migrate.py apply
	$(PYTHON) scripts/manage_users.py seed-defaults
	cd frontend && npm install

dev:
	$(PYTHON) scripts/dev.py

install:
	@if [ -f requirements.lock ]; then \
		$(PIP) install -r requirements.txt -c requirements.lock; \
	else \
		$(PIP) install -r requirements.txt; \
	fi

install-dev:
	@if [ -f requirements-dev.lock ]; then \
		$(PIP) install -r requirements-dev.txt -c requirements-dev.lock; \
	else \
		$(PIP) install -r requirements-dev.txt; \
	fi

update:
	bash scripts/update.sh

run:
	$(PYTHON) -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

test:
	$(PYTEST) -q

lint:
	$(RUFF) check .

frontend-lint:
	cd frontend && npm run lint

frontend-build:
	cd frontend && npm run build

script-check:
	bash -n scripts/install.sh
	bash -n scripts/uninstall.sh
	bash -n scripts/update.sh
	bash -n scripts/ui_smoke.sh
	bash -n scripts/update_locks.sh
	bash -n devsynapse.sh
	$(PYTHON) -m py_compile scripts/dev.py scripts/ensure_runtime_config.py scripts/migrate.py scripts/manage_users.py
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck scripts/install.sh scripts/uninstall.sh scripts/update.sh scripts/ui_smoke.sh scripts/update_locks.sh devsynapse.sh; \
	else \
		echo "shellcheck not installed; skipping shell script lint"; \
	fi

ui-smoke:
	bash scripts/ui_smoke.sh

update-locks:
	bash scripts/update_locks.sh

verify: lint test script-check frontend-lint frontend-build

seed-users:
	$(PYTHON) scripts/manage_users.py seed-defaults

migrate:
	$(PYTHON) scripts/migrate.py apply

migration-status:
	$(PYTHON) scripts/migrate.py status
