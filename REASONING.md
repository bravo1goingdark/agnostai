# REASONING

## Summary

Agnost ingests AI-agent conversations, extracts sentiment and semantic embeddings,
clusters recurring user themes, and exposes PM-ready insights — topic labels with
growth rates, sentiment skew, negativity share, and representative message
examples. A single question drives the design: what are users asking for,
complaining about, or repeatedly blocked on right now?

## Architecture

```mermaid
flowchart TB
    subgraph Ingestion["Ingestion Layer"]
        API["POST /v1/conversations<br/>FastAPI"]
        Seed["Seed script<br/>agnost-seed-sample-data"]
    end

    subgraph Queue["Async Processing"]
        Redis["Redis queue<br/>(ARQ)"]
        Worker["ARQ worker<br/>process_conversation"]
    end

    subgraph Pipeline["Processing Pipeline"]
        Norm["Normalize<br/>+ redact PII"]
        Embed["Embed<br/>sentence-transformers<br/>all-MiniLM-L6-v2"]
        Sentiment["Score sentiment<br/>VADER compound"]
        Persist["Persist to<br/>messages + embeddings"]
    end

    subgraph Storage["Storage Layer"]
        PG["PostgreSQL + pgvector<br/>raw payloads · embeddings<br/>topics · cluster runs"]
    end

    subgraph Clustering["Batch Clustering"]
        HDB["HDBSCAN<br/>min_cluster_size"]
        CTFIDF["c-TF-IDF<br/>topic labels"]
        FAISS["FAISS IndexFlatIP<br/>cosine similarity"]
    end

    subgraph Query["Query Layer"]
        Insights["GET /v1/insights<br/>topics · sentiment · growth"]
        Topics["GET /v1/topics<br/>detail · examples"]
        Report["GET /v1/reports<br/>markdown export"]
        Observe["GET /v1/observability<br/>queue · failures · timing"]
    end

    subgraph UI["Presentation"]
        Dashboard["Dashboard SPA<br/>summary · topic cards<br/>detail pane · metrics"]
    end

    Ingestion --> Redis
    Seed --> Redis
    Redis --> Worker
    Worker --> Norm --> Embed --> Sentiment --> Persist --> PG
    PG --> HDB --> CTFIDF --> FAISS --> PG
    PG --> Insights --> Dashboard
    PG --> Topics --> Dashboard
    PG --> Report --> Dashboard
    PG --> Observe --> Dashboard
```

### Data Flow

```mermaid
sequenceDiagram
    participant Client as Client / Dashboard
    participant API as FastAPI Ingest
    participant Redis as Redis Queue
    participant Worker as ARQ Worker
    participant DB as PostgreSQL
    participant Cluster as Batch Clustering

    Client->>API: POST /v1/conversations
    API->>DB: Store raw conversation
    API->>Redis: Enqueue processing job
    API-->>Client: 202 accepted

    Redis->>Worker: process_conversation
    Worker->>DB: Load raw payload
    Worker->>Worker: Normalize + redact PII
    Worker->>Worker: Embed (MiniLM-L6-v2)
    Worker->>Worker: Score sentiment (VADER)
    Worker->>DB: Store messages + embeddings

    Cluster->>DB: Load user messages with embeddings
    Cluster->>Cluster: HDBSCAN clustering
    Cluster->>Cluster: c-TF-IDF topic labels
    Cluster->>Cluster: FAISS similarity assignment
    Cluster->>DB: Store topics + memberships

    Client->>API: GET /v1/insights
    API->>DB: Query topics + sentiment
    API-->>Client: Topic cards with growth rates

    Client->>API: GET /v1/topics/{id}
    API->>DB: Query messages + examples
    API-->>Client: Representative conversations
```

### Schema

```mermaid
erDiagram
    projects {
        varchar id PK
        varchar api_key_hash
        jsonb metadata
        timestamp created_at
    }

    conversations {
        uuid id PK
        varchar project_id FK
        varchar external_id
        varchar content_hash
        jsonb raw_payload
        timestamp created_at
    }

    messages {
        uuid id PK
        varchar project_id FK
        uuid conversation_id FK
        int sequence_index
        varchar role
        text content
        varchar normalized_text_hash
        float sentiment_score
        varchar sentiment_label
        timestamp created_at
    }

    message_embeddings {
        uuid id PK
        varchar project_id FK
        uuid message_id FK
        varchar model_name
        int dimension
        vector embedding
    }

    cluster_runs {
        uuid id PK
        varchar project_id FK
        varchar status
        timestamp window_start
        timestamp window_end
        jsonb parameters
        text error_message
    }

    topics {
        uuid id PK
        varchar project_id FK
        uuid cluster_run_id FK
        int cluster_label
        varchar label
        text summary
        jsonb terms
        int member_count
        float growth_24h
        float growth_7d
        float sentiment_mean
        float negative_sentiment_share
    }

    topic_memberships {
        uuid id PK
        varchar project_id FK
        uuid topic_id FK
        uuid message_id FK
        float similarity
        bool is_representative
    }

    processing_jobs {
        uuid id PK
        varchar project_id FK
        uuid conversation_id FK
        varchar job_type
        varchar status
        int attempt_count
        text last_error
        timestamp enqueued_at
        timestamp started_at
        timestamp completed_at
    }

    projects ||--o{ conversations : "has"
    projects ||--o{ messages : "has"
    projects ||--o{ cluster_runs : "has"
    projects ||--o{ topics : "has"
    projects ||--o{ processing_jobs : "has"
    conversations ||--o{ messages : "contains"
    conversations ||--o{ processing_jobs : "tracks"
    messages ||--o{ message_embeddings : "has"
    messages ||--o{ topic_memberships : "belongs to"
    cluster_runs ||--o{ topics : "produces"
    topics ||--o{ topic_memberships : "includes"
```

## Major Choices

### PostgreSQL + pgvector

A single database holds raw payloads, derived messages, embedding vectors, topic
assignments, and cluster run metadata. No separate vector store — pgvector indexes
the embeddings in the same transactions as the application data, which keeps
recomputation and inspection straightforward.

**Rejected:** Dedicated vector DBs (Pinecone, Weaviate, Milvus) add operational
overhead without benefit at demo scale. SQLite-only would skip pgvector's IVFFlat
index. The schema uses `Vector(384).with_variant(JSON(), "sqlite")` so integration
tests run against in-memory SQLite while production uses PostgreSQL.

### ARQ for background work

Ingestion returns immediately after enqueueing. Each conversation is processed
asynchronously by an ARQ worker: messages are normalized, obvious PII (email,
phone) is redacted, user-text-only sentiment is scored with VADER, and embeddings
are generated via sentence-transformers/all-MiniLM-L6-v2. Processing jobs track
attempt count, status, timing, and last error. After 3 failed attempts the job is
skipped permanently.

**Rejected:** Celery (too heavy for a demo — broker config, result backends,
flower monitoring). Dramatiq (similar weight to ARQ but less Redis-native).
BackgroundTasks/FastAPI's built-in (no persistence, no retry). ARQ is ~200 lines of
Redis-backed reliability with zero ceremony.

### HDBSCAN with deterministic fallback

HDBSCAN is the primary clustering algorithm because topic counts are unknown and
conversational noise is expected. The fallback path groups messages by
co-occurring significant tokens using a TF-IDF-like bucketing approach — no ML
dependencies required. When numpy and HDBSCAN are available, embeddings are loaded
as float32 arrays and clustered with `min_cluster_size` from configuration. c-TF-IDF
labels topics from the most frequent cluster terms.

**Rejected:** K-means (requires pre-specifying K — impossible for unknown topic
counts). LDA (weaker on short conversational text; needs document-length context).
Agglomerative clustering (O(n²) memory, no native noise handling). The HDBSCAN +
c-TF-IDF combo needs no hyperparameter tuning and naturally separates signal from
noise.

### FAISS spatial index (optional)

When faiss-cpu is installed alongside numpy, `_build_memberships` normalizes all
query embeddings and cluster centroids to unit vectors, builds a `faiss.IndexFlatIP`
(inner product = cosine similarity for normalized vectors), and batch-searches all
message-centroid pairs in one GPU/CPU-optimized call. Without FAISS, similarity is
computed per-message via explicit cosine distance — correct but O(n·k·d).

**Rejected:** scikit-learn's `cosine_similarity` (same O(n·k·d) as the manual
loop, no index acceleration). Annoy/NMSLIB (require building a persistent index;
FAISS in-memory is simpler for batch jobs that rebuild clusters each run).

### Real embeddings and sentiment

The `sentence-transformers/all-MiniLM-L6-v2` model is lazy-loaded at first use.
When the ML extras are not installed, the system falls back to a deterministic
character-sum hash that preserves text identity (identical texts produce identical
vectors). Sentiment uses VADER's compound score with ±0.05 thresholds for
positive/negative classification; the keyword-based stub is preserved as a
fallback.

**Rejected:** OpenAI embeddings API (network latency, cost per call, no offline
demo). Larger sentence-transformers like `all-mpnet-base-v2` (2x memory, marginal
gain on short text). TextBlob for sentiment (slower, same lexicon-based approach
as VADER). Both modules follow the same pattern: try the real model, silently
degrade to the stub if unavailable.

### Raw / derived separation

Raw conversation payloads in the `conversations` table are immutable. All derived
data — `messages`, `message_embeddings`, `topics`, `topic_memberships` — can be
deleted and rebuilt from raw records. The `agnost-recompute` CLI does exactly this:
it wipes derived rows for a project, reprocesses every raw conversation through the
worker, then re-runs clustering. Cluster runs are parameterized and versioned so
different runs can be compared.

### Batch clustering over streaming

Topic discovery does not need request latency. Clustering runs as a batch job,
creating a `ClusterRun` record with window parameters, then replacing previous
topics and memberships atomically. A failed run marks the `ClusterRun` as failed
with an error message and rolls back derived data. Growth rates compare consecutive
equal-length time windows (e.g., most recent 24h vs. prior 24h), returning `None`
when insufficient history exists.

## Reliability

- Ingest dedupes by external ID and normalized content hash.
- Worker jobs track attempt count, status, timing, and last error; max 3 retries.
- Recompute from raw data: `agnost-recompute project-1` rebuilds all derived tables.
- ClusterRun failures are recorded with error messages; previous topics survive.
- Logs carry request IDs and worker timing for traceability.

## Observability

`GET /v1/observability?project_id=...` exposes queue depth, failed job count, and
latest cluster run duration in milliseconds. The dashboard displays these alongside
topic summaries and a live-updating footer.

## Tradeoffs

- **Batch, not streaming.** Topic signals are coarse-grained by design. A PM checks
  weekly trends, not per-second updates. Streaming adds complexity without changing
  the output.
- **No custom model training.** The goal is clarity and reproducibility. Pre-trained
  sentence-transformers and VADER provide strong-enough signals with zero tuning.
- **Dashboard is read-only and single-project.** Hardcoded to `project-1`, no auth.
  Sufficient for the demo reviewer workflow; a production system would add
  project-scoped views and API-key middleware (the schema and dependency skeleton
  already exist).

## Production Path

The repo is a working demo that scales along a clear path:

1. **More data.** pgvector's IVFFlat index handles millions of embeddings. Add
   incremental clustering with topic stability tracking across windows.
2. **Better models.** Swap sentence-transformers for a domain-fine-tuned variant.
   Replace VADER with a transformer-based sentiment classifier.
3. **Multi-tenancy.** The `projects` table supports multiple projects. Add API-key
   middleware (skeleton at `app/api/deps.py`) and per-project dashboards.
4. **Streaming ingestion.** Replace the request/response ingest with a Kafka or
   Redis Streams pipeline for high-throughput production traffic.
5. **Evaluation.** Add held-out topic labeling, inter-annotator agreement metrics,
   and drift detection to quantify cluster quality over time.

Every design choice supports one outcome: a reviewer can see real engineering
judgment, clear architecture tradeoffs, and a product that turns messy
conversations into decision-ready signals.
