PYTHON ?= $(shell if [ -x ./venv/bin/python ]; then printf './venv/bin/python'; else command -v python3 || command -v python; fi)
PIP ?= $(shell if [ -x ./venv/bin/pip ]; then printf './venv/bin/pip'; else command -v pip3 || command -v pip; fi)
PYTEST ?= $(shell if [ -x ./venv/bin/pytest ]; then printf './venv/bin/pytest'; else command -v pytest; fi)
RUFF ?= $(shell if [ -x ./venv/bin/ruff ]; then printf './venv/bin/ruff'; else command -v ruff; fi)

.PHONY: setup install install-dev test lint script-check verify migrate migration-status run tui-smoke

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

script-check:
	bash -n scripts/install.sh
	bash -n scripts/uninstall.sh
	bash -n scripts/update.sh
	$(PYTHON) -m py_compile devsynapse/cli.py devsynapse/tui.py scripts/migrate.py scripts/eval_agent.py
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck scripts/install.sh scripts/uninstall.sh scripts/update.sh; \
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

verify: lint test script-check tui-smoke

migrate:
	$(PYTHON) scripts/migrate.py apply

migration-status:
	$(PYTHON) scripts/migrate.py status
