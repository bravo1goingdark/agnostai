# REASONING

## Summary

This repo is built to turn raw AI-support conversations into topic signals a PM can
scan quickly. The design favors a small number of durable primitives: raw
conversation storage, derived message rows, embeddings, batch clustering, and
topic summaries.

## Major Choices

### PostgreSQL + pgvector
PostgreSQL is the source of truth. Keeping embeddings in the same database as the
raw and derived conversation data makes recomputation and inspection simpler than
splitting storage across multiple systems.

### ARQ for background work
Conversation processing is asynchronous because ingestion should return quickly.
ARQ fits the demo well: it is small, explicit, and easy to run locally with Redis.

### Batch clustering
Topic discovery does not need request latency. Running clustering in batches makes
it easier to recompute from raw records and to compare one clustering window with
another.

### HDBSCAN with deterministic fallback
HDBSCAN is the preferred algorithm when the dependency stack is available because
the topic count is unknown and conversational noise is normal. The code also keeps
a deterministic fallback path so the repo still works in lean environments.

### Deterministic stubs for embeddings and sentiment
The embedding and sentiment helpers are intentionally simple placeholders. They
give the system a stable shape, keep tests fast, and leave a clear insertion point
for stronger models later.

### Raw / derived separation
Raw conversations are never overwritten. Derived rows can be deleted and rebuilt
from the original payloads, which is the safest way to support recomputation.

## Reliability

- Ingest dedupes by external ID and normalized content hash.
- Worker jobs record status, attempt count, start time, completion time, and last
  error.
- Topic and report outputs are derived from stored data, not from in-memory state.
- Logs carry request IDs and worker timing so failed flows can be traced.

## Tradeoffs

- No streaming cluster pipeline. Batch is enough for the product goal.
- No custom model training. The goal is clarity and reproducibility, not model R&D.
- No dashboard. The API and report export are enough to prove the system.

## Current Limitation

The lean fallback path is not a substitute for the full ML stack. It exists so the
repo remains runnable without heavyweight extras, but the intended production path
still uses pgvector, HDBSCAN, and sentence-transformers.
