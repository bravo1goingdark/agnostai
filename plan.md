# Agnost Track A - Conversation Intelligence Engine

## Summary

Build a Python-only service that ingests AI-agent conversations, extracts sentiment and embeddings, batches the data into topics, and exposes PM-ready insights through APIs plus a small report artifact.

The goal is to show:
- backend judgment
- system design thinking
- practical ML pipeline choices
- clean tradeoff reasoning in `REASONING.md`

## Product Goal

Answer one question well: what are users asking for, complaining about, or repeatedly getting blocked on right now?

The system should:
- ingest conversation payloads
- normalize messages into analysis units
- compute embeddings and sentiment
- cluster recurring themes
- surface growing topics and representative examples
- keep the pipeline reproducible from raw data

## Stack

- Python 3.13
- FastAPI
- PostgreSQL
- pgvector
- Redis + ARQ
- `sentence-transformers/all-MiniLM-L6-v2`
- HDBSCAN
- c-TF-IDF for topic labels

Why this stack:
- best fit for embeddings, clustering, and NLP utilities
- fast to ship in a weekend
- easy to explain in `REASONING.md`
- strong enough to look like real production engineering

## Scope Lock

### In scope
- conversation ingestion API
- async processing pipeline
- raw + derived storage separation
- embeddings and sentiment scoring
- batch clustering
- topic labeling
- insight APIs
- small report output
- docs and tests

### Out of scope
- training custom models
- streaming architecture
- full dashboard/UI
- auth beyond a project API key
- multi-tenant billing or org management

## User Experience

The reviewer should be able to:
1. clone the repo
2. run the app locally
3. ingest sample conversations
4. trigger processing
5. query topics and insights
6. read `REASONING.md` and understand every major choice

## System Architecture

```text
Client / seed script / CSV import
        |
        v
FastAPI ingestion API
        |
        v
Redis queue
        |
        v
ARQ workers
  - normalize
  - redact obvious PII
  - build analysis chunks
  - embed
  - score sentiment
  - persist derived data
        |
        v
PostgreSQL + pgvector
        |
        v
Batch clustering job
  - optional UMAP
  - HDBSCAN
  - c-TF-IDF topic labels
  - growth and sentiment metrics
        |
        v
Query API + report export
```

## Data Model

Keep raw and derived data separate so the pipeline can be recomputed.

### Core tables
- `projects`: project identity and API key hash
- `conversations`: raw conversation metadata
- `messages`: message text, role, timestamp, sentiment
- `message_embeddings`: embedding vector and model name
- `cluster_runs`: clustering window and parameters
- `topics`: cluster label, summary, growth, sentiment, terms
- `topic_memberships`: message-to-topic links with similarity

### Key rules
- raw records are immutable
- derived tables can be rebuilt from raw data
- dedupe by external ID and normalized text hash
- store model names and run parameters for reproducibility

## API Contract

### `POST /v1/conversations`
Ingest a conversation payload.

Expected fields:
- `project_id`
- `conversation_id`
- `messages[]`
- `metadata`

Behavior:
- validate payload
- dedupe safely
- enqueue async processing
- return quickly without waiting for clustering

### `GET /v1/insights?project_id=...`
Return:
- top topics
- sentiment distribution
- emerging topics
- topic growth over the selected window

### `GET /v1/topics?project_id=...`
Return:
- topic label
- member count
- growth rate
- sentiment mean
- representative examples

### `GET /v1/topics/{topic_id}`
Return:
- topic summary
- representative messages
- cluster terms
- source conversations
- history for the topic

### `GET /healthz`
Return simple liveness status.

## Processing Pipeline

### Step 1: Normalize
- convert raw conversation payloads into canonical message rows
- trim obvious noise
- redact obvious PII patterns where practical

### Step 2: Chunk
- cluster analysis should use message-level or short-context chunks
- prefer user message as the primary signal
- include minimal assistant context only when it changes meaning

### Step 3: Embed
- use a small local sentence embedding model
- embed only the text needed for topic discovery
- store embedding dimension and model name

### Step 4: Sentiment
- score user text only
- keep sentiment separate from topic assignment

### Step 5: Cluster
- run clustering in batch windows, not per request
- use HDBSCAN because cluster count is unknown and noise is expected
- use c-TF-IDF to label topics

### Step 6: Compute insights
- topic volume
- growth over 24h and 7d windows
- sentiment mean
- negative sentiment share
- first seen / last seen
- representative examples

## Design Decisions

### PostgreSQL + pgvector
Chosen as the source of truth to keep operations simple and the demo reproducible.

Rejected:
- separate vector DB for MVP
- multiple persistence systems

### HDBSCAN over k-means
Chosen because the number of topics is unknown and conversational noise is real.

Rejected:
- k-means because it requires K
- LDA because it is weaker on short conversational text

### Batch clustering over streaming
Chosen because topic discovery does not need millisecond latency.

Rejected:
- full streaming clustering because it adds complexity without improving the demo

### LLM usage
Use an LLM only for topic naming if available.

Rejected:
- letting the LLM do clustering or be the source of truth

## Error Handling and Reliability

- ingestion must be idempotent
- worker jobs must retry safely
- failed jobs should be visible in logs
- derived data must be recomputable
- API responses should fail cleanly if a cluster run is missing

## Observability

Ship basic operational visibility:
- request logs
- worker logs
- queue depth
- job duration
- cluster run duration
- error count

This matters because the product itself is observability for AI conversations.

## Implementation Plan

### Day 1
- scaffold FastAPI app
- define schemas
- create PostgreSQL schema
- implement ingest endpoint

### Day 2
- add ARQ worker pipeline
- normalize and chunk messages
- compute embeddings
- score sentiment
- persist derived records

### Day 3
- implement batch clustering
- add c-TF-IDF labeling
- store topics and memberships
- expose topics and insights endpoints

### Day 4
- add sample dataset and seed script
- add recompute job
- add integration tests
- add observability hooks

### Day 5
- write `REASONING.md`
- write README quickstart
- add report export
- verify full ingest-to-insights flow

## Test Plan

### Unit tests
- payload validation
- message normalization
- embedding shape and metadata
- sentiment scoring
- clustering output mapping

### Integration tests
- ingest -> queue -> worker -> store -> query
- dedupe behavior
- recompute from raw records
- topic query responses

### End-to-end checks
- sample conversations produce topics
- insights endpoint returns growth metrics
- report export is generated from stored data

## Acceptance Criteria

The repo is complete only if:
- a fresh clone can run locally
- sample data can be ingested
- embeddings and sentiment are persisted
- clustering produces readable topics
- APIs return useful insights
- `REASONING.md` explains the major tradeoffs clearly

## Month-Long Upgrade Path

If given a month, add:
- incremental clustering
- topic stability across windows
- better evaluation data
- PII retention controls
- a small read-only dashboard

## Deliverables

- source code in `/home/bravo1goingdark/PythonProjects/agnostai`
- `plan.md`
- `REASONING.md`
- README with quickstart
- tests
- sample data
- small report artifact

## Final Principle

Every choice should support one outcome: a reviewer can see real engineering judgment, clear architecture, and a product that turns messy conversations into decision-ready signals.
