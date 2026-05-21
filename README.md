# Agnost Conversation Intelligence

A Python service for ingesting AI-agent conversations and turning repeated user
requests, complaints, and blockers into queryable product insights.

This repository is currently scaffolded through Phase 1: the FastAPI service,
worker entrypoint, configuration, Docker runtime, tooling, and placeholder API
contracts are in place. Persistence, clustering, and report generation are
implemented in later phases from `plan.md`.

## Requirements

- Python 3.13
- Docker and Docker Compose

## Local Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Install the heavier embedding and clustering dependencies only when working on
the ML pipeline:

```bash
pip install -e ".[dev,ml]"
```

## Run With Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/healthz
```

API docs are available in local mode at:

```text
http://localhost:8000/docs
```

## Service Entrypoints

API:

```bash
uvicorn app.main:app --reload
```

Worker:

```bash
arq app.workers.arq_worker.WorkerSettings
```

## Current API Contracts

```http
GET /healthz
POST /v1/conversations
GET /v1/insights?project_id=...
GET /v1/topics?project_id=...
GET /v1/topics/{topic_id}
```

`POST /v1/conversations` currently validates the payload and returns an
accepted job stub. The next phase persists raw conversations and enqueues ARQ
jobs.

## Development

```bash
make check
```

Equivalent direct commands:

```bash
ruff check .
mypy app tests
pytest
```

## Project Plan

See `plan.md` for the full product and system implementation plan.
