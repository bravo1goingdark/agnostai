.PHONY: install install-ml lint type test check run-api run-worker

install:
	python -m pip install -e ".[dev]"

install-ml:
	python -m pip install -e ".[dev,ml]"

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

