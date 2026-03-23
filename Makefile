.PHONY: install test dashboard check run-api

# Prefer project venv when present (PEP 517 editable install needs a recent pip).
PY ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || command -v python3)

# Sync Python deps (includes json-repair for response_parser).
install:
	"$(PY)" -m pip install -U pip
	"$(PY)" -m pip install -e ".[dev]"

test:
	"$(PY)" -m pytest -q

dashboard:
	cd dashboard && npm ci && npm run build

# Full local verification: deps, backend tests, frontend build.
check: install test dashboard
	@echo "check: OK"

# Example: API on port 8000 (match dashboard Vite proxy default).
run-api:
	"$(PY)" -m uvicorn aeco.main:app --host 127.0.0.1 --port 8000 --reload
