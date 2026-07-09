SHELL := /bin/bash

TOX := uv run --group dev tox
PYTHON ?= python3
CHARMCRAFT_ARGS ?=
CONTROLLER ?= local
INTEGRATION_MODEL_PREFIX ?= polkadot-integration
INTEGRATION_PLATFORM ?= ubuntu@24.04:amd64
INTEGRATION_LOGGING_CONFIG ?= <root>=DEBUG

.PHONY: charm-venv lock fmt-test lint-test unit-test integration-test integration-test-clean charm-test build-charm clean clean-local clean-uv-cache clean-all

charm-venv:
	uv sync --group dev --group lint --group unit --group integration

lock:
	uv lock

fmt-test:
	$(TOX) -e format

lint-test:
	$(TOX) -e lint

unit-test:
	$(TOX) -e unit

integration-test:
	$(TOX) -e integration

integration-test-clean:
	@set -euo pipefail; \
	model="$(INTEGRATION_MODEL_PREFIX)-$$(date +%Y%m%d-%H%M%S)"; \
	cleanup() { \
		echo "Destroying model $(CONTROLLER):$$model"; \
		juju destroy-model --no-prompt --destroy-storage "$(CONTROLLER):$$model" || \
			echo "Warning: failed to destroy model $(CONTROLLER):$$model"; \
	}; \
	trap cleanup EXIT; \
	echo "Creating model $(CONTROLLER):$$model"; \
	juju add-model "$$model" --controller "$(CONTROLLER)"; \
	juju model-config -m "$(CONTROLLER):$$model" logging-config="$(INTEGRATION_LOGGING_CONFIG)"; \
	$(TOX) -e integration -- --controller "$(CONTROLLER)" --model "$$model" --charmcraft-args=--platform=$(INTEGRATION_PLATFORM) -v

charm-test: fmt-test lint-test unit-test

build-charm:
	charmcraft pack $(CHARMCRAFT_ARGS)

clean: clean-local

clean-local:
	charmcraft clean
	$(PYTHON) -c 'import pathlib, shutil; root = pathlib.Path("."); [shutil.rmtree(root / name, ignore_errors=True) for name in (".craft", ".tox", ".venv", ".venv-charm", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".hypothesis", ".nox", "build", "dist", "htmlcov", "parts", "prime", "stage", ".cache")]; [path.unlink(missing_ok=True) for pattern in (".coverage", ".coverage.*", "*.charm") for path in root.glob(pattern) if path.is_file() or path.is_symlink()]; [shutil.rmtree(path, ignore_errors=True) for path in root.rglob("__pycache__") if path.is_dir()]; [path.unlink(missing_ok=True) for pattern in ("*.pyc", "*.pyo") for path in root.rglob(pattern) if path.is_file() or path.is_symlink()]'

clean-uv-cache:
	uv cache clean

clean-all: clean-local clean-uv-cache
