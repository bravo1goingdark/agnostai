.PHONY: install install-ml migrate demo lint type test check run-api run-worker up

install:
	python -m pip install -e ".[dev]"

install-ml:
	python -m pip install -e ".[dev,ml]"

migrate:
	alembic upgrade head

demo:
	docker compose up --build -d && docker compose run --rm demo && echo && echo "Dashboard: http://localhost:8000"

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

up:
	docker compose up --build -d && echo && echo "Dashboard: http://localhost:8000"
