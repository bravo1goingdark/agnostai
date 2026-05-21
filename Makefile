.PHONY: install install-ml migrate demo lint type test check run-api run-worker

install:
	python -m pip install -e ".[dev]"

install-ml:
	python -m pip install -e ".[dev,ml]"

migrate:
	alembic upgrade head

demo:
	agnost-demo-flow project-1

lint:
	ruff check .

type:
	mypy app tests

test:
	pytest

check: lint type test

run-api:
	uvicorn app.main:app --reload

run-worker:
	arq app.workers.arq_worker.WorkerSettings
