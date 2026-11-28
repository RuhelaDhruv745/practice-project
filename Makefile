# Architect-owned convenience targets (Linux, macOS, CI).
# Windows without make: use the equivalent commands in docs/DEVELOPMENT_GUIDE.md
# (or install make with: winget install ezwinports.make).
# run-* and compose-up work only once members create the entry points:
# backend/app/main.py (Member 1), reviewer_ui/app.py and frontend/ (Member 4),
# docker-compose.yml (Member 5).

PYTHON ?= .venv/bin/python

.PHONY: setup test lint format run-backend run-ui run-frontend compose-up

setup:
	python3.13 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .

run-backend:
	$(PYTHON) -m uvicorn backend.app.main:app --reload --port 8000

run-ui:
	$(PYTHON) -m streamlit run reviewer_ui/app.py --server.port 8501

run-frontend:
	cd frontend && npm run dev

compose-up:
	docker compose up --build
