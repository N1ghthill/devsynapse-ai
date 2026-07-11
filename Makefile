PYTHON ?= $(shell if [ -x ./venv/bin/python ]; then printf './venv/bin/python'; else command -v python3 || command -v python; fi)
PIP ?= $(shell if [ -x ./venv/bin/pip ]; then printf './venv/bin/pip'; else command -v pip3 || command -v pip; fi)
PYTEST ?= $(shell if [ -x ./venv/bin/pytest ]; then printf './venv/bin/pytest'; else command -v pytest; fi)
RUFF ?= $(shell if [ -x ./venv/bin/ruff ]; then printf './venv/bin/ruff'; else command -v ruff; fi)

.PHONY: setup install install-dev test lint frontend-install frontend-lint frontend-typecheck frontend-build desktop-check desktop-smoke script-check verify migrate migration-status run tui-smoke

setup:
	python3 -m venv venv
	@if [ -f requirements.lock ]; then \
		$(PIP) install -r requirements.txt -c requirements.lock; \
	else \
		$(PIP) install -r requirements.txt; \
	fi
	$(PYTHON) scripts/migrate.py apply

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

test:
	$(PYTEST) -q --cov=core --cov=devsynapse --cov-report=term-missing

lint:
	$(RUFF) check .

frontend-install:
	cd frontend && if [ -f package-lock.json ]; then npm ci; else npm install; fi

frontend-lint:
	cd frontend && npm run lint

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-build:
	cd frontend && npm run build

desktop-check:
	cd frontend/src-tauri && cargo check

desktop-smoke:
	bash scripts/desktop-smoke.sh

script-check:
	bash -n scripts/install.sh
	bash -n scripts/uninstall.sh
	bash -n scripts/update.sh
	bash -n scripts/build-backend.sh
	bash -n scripts/desktop-smoke.sh
	$(PYTHON) -m py_compile backend-entry.py core/desktop_conversation.py core/desktop_sidecar.py core/github_auth.py core/operations.py devsynapse/cli.py devsynapse/tui.py scripts/migrate.py scripts/eval_agent.py
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck scripts/install.sh scripts/uninstall.sh scripts/update.sh scripts/desktop-smoke.sh; \
	else \
		echo "shellcheck not installed; skipping shell script lint"; \
	fi

eval-agent:
	$(PYTHON) scripts/eval_agent.py $(EVAL_AGENT_ARGS)

run:
	$(PYTHON) -m devsynapse.cli

tui-smoke:
	$(PYTHON) -m devsynapse.cli --help
	$(PYTEST) -q tests/unit/test_tui_smoke.py

verify: lint frontend-lint frontend-build desktop-check test script-check tui-smoke desktop-smoke

migrate:
	$(PYTHON) scripts/migrate.py apply

migration-status:
	$(PYTHON) scripts/migrate.py status
