# Agnost Conversation Intelligence

A Python service for ingesting AI-agent conversations and turning repeated user
requests, complaints, and blockers into queryable product insights.

## Quickstart

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For the full topic pipeline:

```bash
pip install -e ".[dev,ml]"
```

## Run

API:

```bash
uvicorn app.main:app --reload
```

Worker:

```bash
arq app.workers.arq_worker.WorkerSettings
```

Seed sample data:

```bash
agnost-seed-sample-data project-1
```

Run clustering:

```bash
agnost-run-clustering project-1
```

Export a report:

```bash
agnost-export-report project-1
```

## API

```http
GET /healthz
POST /v1/conversations
GET /v1/insights?project_id=...
GET /v1/topics?project_id=...
GET /v1/topics/{topic_id}
```

## Notes

- `POST /v1/conversations` persists raw payloads and queues processing.
- The worker normalizes messages, redacts obvious PII, scores sentiment, and
  stores embeddings.
- Batch clustering builds topics and memberships from stored messages.
- `REASONING.md` covers the main tradeoffs.

## Checks

```bash
ruff check .
mypy app
pytest
```
