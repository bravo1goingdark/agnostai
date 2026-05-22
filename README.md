# Agnost Conversation Intelligence

A Python service for ingesting AI-agent conversations and turning repeated user
requests, complaints, and blockers into queryable product insights.

## Quickstart

```bash
cp .env.example .env
docker compose up --build -d && docker compose run --rm demo
```

That's it. Open **http://localhost:8000** — the dashboard loads with seeded
sample data, clustered topics, and live insights.

If you have `make`:

```bash
make demo
```

The first build downloads sentence-transformers, HDBSCAN, FAISS, and VADER
(~2 GB). Subsequent runs use the cached image and start in seconds.

## Checks

```bash
ruff check .      # lint
mypy app          # type check
pytest            # 34 tests
```

Or all three: `make check`

## CLI

```bash
agnost-demo-flow project-1       # seed → process → cluster → report
agnost-recompute project-1       # rebuild derived data from raw conversations
agnost-run-clustering project-1  # cluster only
agnost-export-report project-1   # markdown report to stdout
```

## API

```http
GET  /healthz
POST /v1/conversations
GET  /v1/insights?project_id=...
GET  /v1/topics?project_id=...
GET  /v1/topics/{topic_id}
GET  /v1/reports/current?project_id=...
GET  /v1/observability?project_id=...
GET  /v1/demo/bootstrap  (POST)
```

## Architecture

`REASONING.md` covers the full design — database choices (PostgreSQL + pgvector),
algorithm selection (HDBSCAN, c-TF-IDF, FAISS), async worker pipeline (ARQ +
Redis), and the production upgrade path.
