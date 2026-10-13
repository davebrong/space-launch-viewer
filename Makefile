PYTHON ?= python
.PHONY: spec-check acceptance integration release start references dev test-app lint migrate backup restore-drill load
spec-check:
	$(PYTHON) tools/check_spec.py
acceptance:
	uv run --frozen python -m implementation.checks full-release
integration:
	$(PYTHON) tests/acceptance/live.py
release:
	$(PYTHON) tools/release_gate.py
start:
	$(PYTHON) tools/start_implementation.py
references:
	$(PYTHON) tools/derive_references.py
dev:
	$(PYTHON) tools/dev.py
test-app:
	uv run --frozen pytest
lint:
	uv run --frozen ruff check packages services implementation tests/application tools/dev.py
	npm run lint
migrate:
	uv run --frozen python -m implementation.manage migrate
backup:
	uv run --frozen python -m ops.backup backup
restore-drill:
	uv run --frozen python -m ops.backup drill
load:
	uv run --frozen python -m implementation.checks load-100
