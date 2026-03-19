PYTHON ?= python3

.PHONY: install format lint test run migrate seed

install:
	$(PYTHON) -m pip install -e .[dev]

format:
	black .
	isort .

lint:
	ruff check .
	black --check .
	isort --check-only .

test:
	pytest

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

migrate:
	alembic upgrade head

seed:
	$(PYTHON) scripts/seed_data.py