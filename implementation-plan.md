# Implementation Plan: Agnost Audit Fixes (19 Items)

## Overview

5 implementation phases covering all 19 findings from `audit-findings.md`. Phases are ordered by impact: fix the product-breaking algorithmic gaps first, then bugs, then dead code, then test coverage, then architecture polish.

Each phase is independently verifiable — tests pass and the demo flow still works after each one.

---

## Phase 1: Algorithmic Core — Sentiment, Embeddings, Growth Rate

Covers audit items: #2, #3, #11, #12 — the blockers that make the system non-functional for the product goal.

### 1a. Real Embedding Model

**File:** `app/services/embeddings.py`

```python
from typing import TypedDict
from app.config import get_settings

class EmbeddingMetadata(TypedDict):
    model_name: str
    dimension: int

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(get_settings().embedding_model_name)
        except Exception:
            _embedding_model = False
    return _embedding_model if _embedding_model is not False else None

def embedding_metadata() -> EmbeddingMetadata:
    settings = get_settings()
    return {"model_name": settings.embedding_model_name, "dimension": settings.embedding_dimension}

def embed_text(text: str, dimension: int) -> list[float]:
    model = _get_embedding_model()
    if model is not None:
        return model.encode([text])[0].tolist()
    return embed_text_stub(text, dimension)

def embed_text_stub(text: str, dimension: int) -> list[float]:
    seed = sum(ord(char) for char in text) or 1
    return [((seed + index) % 997) / 997.0 for index in range(dimension)]
```

**Change in workers/jobs.py:** Replace `embed_text_stub` import with `embed_text` — one import change, everything else stays the same.

**Verification:** Install `[ml]` extras, run `test_demo_flow.py` — embeddings should now be real vectors. Test behavior is unchanged since the fallback is deterministic.

### 1b. Real Sentiment Scoring

**File:** `app/services/sentiment.py`

Replace the 4-word keyword stub with VADER (no ML deps, tiny, fast):

```python
from typing import Literal

SentimentLabel = Literal["negative", "neutral", "positive"]

_vader_analyzer = None

def _get_vader():
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader_analyzer = SentimentIntensityAnalyzer()
        except Exception:
            _vader_analyzer = False
    return _vader_analyzer if _vader_analyzer is not False else None

def score_sentiment(text: str) -> tuple[float, SentimentLabel]:
    analyzer = _get_vader()
    if analyzer is not None:
        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]
        if compound >= 0.05:
            return compound, "positive"
        elif compound <= -0.05:
            return compound, "negative"
        return compound, "neutral"
    return score_sentiment_stub(text)

def score_sentiment_stub(text: str) -> tuple[float, SentimentLabel]:
    lowered = text.lower()
    if any(token in lowered for token in ("broken", "blocked", "angry", "bad")):
        return -0.5, "negative"
    if any(token in lowered for token in ("great", "thanks", "love", "good")):
        return 0.5, "positive"
    return 0.0, "neutral"

def is_user_message(role: str) -> bool:
    return role == "user"
```

**Add to pyproject.toml dependencies:**
```toml
"vaderSentiment>=3.3.2",
```

**Change in workers/jobs.py:** Replace `score_sentiment_stub` import with `score_sentiment`.

**Verification:** Run `test_worker_utils.py` — all sentiment tests still pass (VADER classifies "broken" messages as negative with stronger scores than the stub's -0.5). Run `test_demo_flow.py` — sentiment distribution should be more nuanced.

### 1c. Fix Growth Rate Logic

**File:** `app/services/clustering.py` — replace `_growth_rate` function:

```python
def _growth_rate(messages: list[dict[str, Any]], *, hours: int) -> float | None:
    if len(messages) < 2:
        return None

    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=hours)
    older_cutoff = now - timedelta(hours=hours * 2)

    recent = sum(
        1
        for message in messages
        if (created_at := _ensure_aware_datetime(message.get("created_at")))
        and created_at >= recent_cutoff
    )
    older = sum(
        1
        for message in messages
        if (created_at := _ensure_aware_datetime(message.get("created_at")))
        and older_cutoff <= created_at < recent_cutoff
    )

    if older == 0:
        return None
    return (recent - older) / older
```

**Verification:** Write a targeted test in `test_clustering.py`:

```python
def test_growth_rate_equal_windows():
    from app.services.clustering import _growth_rate
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    messages = [
        {"created_at": now - timedelta(hours=1)},   # recent
        {"created_at": now - timedelta(hours=5)},   # recent
        {"created_at": now - timedelta(hours=13)},  # older (24h window: older is 24-48h)
        {"created_at": now - timedelta(hours=30)},  # older
        {"created_at": now - timedelta(hours=50)},  # too old
    ]
    rate = _growth_rate(messages, hours=24)
    # recent = 2, older = 2 → (2-2)/2 = 0.0 (stable)
    assert rate is not None
    assert rate == 0.0
```

**Verification demo flow:** Messages in `sample_data.py` use `base_time - timedelta(hours=(theme_index * 8) + item_index)` — spans 0 to 20 hours. The 7d window should show growth, the 24h window will show `None` (no messages older than 24h). This is correct behavior.

---

## Phase 2: Bug Fixes — Export + Frontend State

Covers audit items: #1, #4

### 2a. Fix export_report.py Exit Code

**File:** `app/scripts/export_report.py`

```python
async def _export(project_id: str) -> int:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project {project_id!r} does not exist")
        report_file = await write_current_topic_report(
            session, project_id, output_dir=Path("reports"),
        )
        print(report_file.read_text(encoding="utf-8"))
        return 0
```

Return type changes from `str` to `int`. Main stays the same — `SystemExit(asyncio.run(...))` now gets `0` (success) instead of a string.

**Verification:** `make check` + `agnost-export-report project-1; echo $?` returns `0`.

### 2b. Fix loadTopic() Frontend State Race

**File:** `frontend/assets/app.js` — `loadTopic()` function:

```javascript
async function loadTopic(topicId) {
    state.topicDetail = null;
    renderTopicDetail();
    try {
        const detail = await fetchJson(`/v1/topics/${encodeURIComponent(topicId)}`);
        state.selectedTopicId = topicId;
        state.topicDetail = detail;
        renderTopics();
        renderTopicDetail();
    } catch (error) {
        state.selectedTopicId = null;
        setStatus(error.message, "error");
        renderTopics();
    }
}
```

**Verification:** Manually — click a topic with the API stopped, verify the detail pane resets and the topic deselects.

---

## Phase 3: Dead Code Removal

Covers audit items: #5, #6, #7, #8, #9, #19

### 3a. Remove `loadTopicsOnly()` from frontend

**File:** `frontend/assets/app.js` — delete the entire function (it's ~12 lines). No callers exist.

### 3b. Remove `summarize_queue_metrics()` from backend

**File:** `app/services/insights.py` — delete the function. Only called in `test_reports_and_insights.py`.

**File:** `tests/test_reports_and_insights.py` — remove the test for `summarize_queue_metrics` or replace with a todo comment.

### 3c. Remove `raw_payload_for_storage()`

**File:** `app/services/ingestion.py` — delete the function (it's 1 line).

### 3d. Remove/reduce `render_empty_report()`

**File:** `app/services/reports.py` — delete `render_empty_report`. It's only called in tests.

**File:** `tests/test_reports_and_insights.py` — inline the expected output string or use `render_topic_report(..., topics=[], cluster_run_id=None)` instead.

### 3e. Wire up or remove `RequestIdFilter`

**File:** `app/logging.py` — delete the `RequestIdFilter` class. The `request_id` is already interpolated directly into log messages via `%s`. The filter is unused complexity.

### 3f. Remove unused DuckDB import

**File:** `app/services/ingestion.py` — remove `from duckdb import connect` line. It was imported for `raw_payload_for_storage()` which is now dead.

**Verification after all 3a-3f:** `make check` — ruff, mypy, pytest all pass clean. No import errors.

---

## Phase 4: Test Coverage

Covers audit items: #13, #14, #15

### 4a. Move FakeRedis/FakeJob to conftest.py

**File:** `tests/conftest.py` — create:

```python
from unittest.mock import AsyncMock, MagicMock

class FakeJob:
    job_id = "fake-job-id"

class FakeRedis:
    async def enqueue_job(self, *args, **kwargs):
        return FakeJob()
    async def aclose(self):
        pass

class FakeQueue:
    async def enqueue_job(self, *args, **kwargs):
        return FakeJob()
```

**Files to update:** `test_ingestion.py`, `test_worker_flow.py` — remove local `FakeRedis`/`FakeJob` classes, import from `conftest`.

**Verification:** Tests still pass with shared fixtures.

### 4b. Add ClusterRun Failure Path Test

**File:** `tests/test_clustering.py` — new test:

```python
@pytest.mark.asyncio
async def test_run_cluster_batch_failure_path():
    from unittest.mock import patch
    from app.services.clustering import run_cluster_batch, _cluster_messages

    # ... setup session with project + messages ...

    with patch(
        "app.services.clustering._cluster_messages",
        side_effect=ValueError("simulated clustering failure"),
    ):
        with pytest.raises(ValueError):
            await run_cluster_batch(session, project_id)

    # Verify ClusterRun marked as failed
    runs = await session.execute(
        select(ClusterRun).where(ClusterRun.project_id == project_id)
    )
    failed_run = runs.scalar_one()
    assert failed_run.status == "failed"
    assert "simulated clustering failure" in (failed_run.error_message or "")
```

**Verification:** `pytest tests/test_clustering.py -k failure` — passes.

### 4c. Add API Route Integration Tests

**File:** `tests/test_api_routes.py` — new file using TestClient:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# ... similar for each route ...
```

**Verification:** All route tests pass. Tests cover parameter validation, empty state responses, and 404 cases.

---

## Phase 5: Architecture Polish

Covers audit items: #10, #16, #17, #18

### 5a. Fix `representative_examples` to Return Actual Messages

**File:** `app/services/clustering.py` — update `topic_to_summary()` and related functions:

In `compute_insights()` and `load_topic_detail()`, when building `TopicSummary`, include the representative message content. The cleanest approach: add `representative_examples` population to `compute_insights()` by querying the `TopicMembership` table for `is_representative=True` rows and joining to `Message.content`.

Simpler approach for `topic_to_summary()`: accept an optional `representative_texts` parameter:

```python
def topic_to_summary(
    topic: Topic,
    representative_texts: list[str] | None = None,
) -> dict[str, Any]:
    if representative_texts is not None:
        examples = [text[:160] for text in representative_texts[:3]]
    else:
        examples = list(topic.terms or [])[:3]
    return {
        # ... existing fields ...
        "representative_examples": examples,
    }
```

In `compute_insights()`, fetch representative messages per topic and pass to `topic_to_summary()`.

**Verification:** `test_clustering.py` — verify `representative_examples` contain actual message content, not terms.

### 5b. API Key Middleware

**File:** `app/api/deps.py` — new file:

```python
from fastapi import Depends, Header, HTTPException

async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    return x_api_key  # placeholder — hash and compare against Project.api_key_hash
```

**File:** `app/api/router.py` — add `dependencies=[Depends(verify_api_key)]` to the router.

**Verification:** Requests without `X-API-Key` header get 422. With header, they pass through. Demo bootstrap still works (frontend adds header).

### 5c. Consistent Extra Validation on Schemas

**File:** `app/models/schemas.py` — change `ConversationMessage`:

```python
class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # ... rest stays the same
```

**Verification:** `test_ingestion.py` — test that extra fields on messages are rejected. All existing tests still pass (no tests currently send extra fields on messages).

### 5d. Lazy Engine Creation (Low Priority, Document Only)

**Decision:** Do NOT change `db.py` or `jobs.py` engine creation for now — the `REASONING.md` already notes the demo tradeoff. Add a comment in both files:

```python
# Engine created at module level for simplicity. In production, move to
# a lazy factory or FastAPI lifespan to avoid import-time crashes when
# the database is unavailable.
```

---

## Implementation Order & Dependency Graph

```
Phase 1 (algorithmic core)
├── 1a: Real embeddings ──────────────┐
├── 1b: Real sentiment ───────────────┤ independent, can parallelize
└── 1c: Growth rate fix ──────────────┘

Phase 2 (bugs)
├── 2a: Export exit code ─────────────┐
└── 2b: Frontend state ───────────────┤ independent, can parallelize

Phase 3 (dead code) ───── depends on nothing, can run anytime
├── 3a-f: All removals

Phase 4 (test coverage) ─── depends on Phase 1-3 being correct
├── 4a: conftest refactor
├── 4b: failure path test
└── 4c: API route tests

Phase 5 (architecture polish) ─ depends on nothing, purely additive
├── 5a: Representative examples
├── 5b: API key middleware
├── 5c: Schema validation
└── 5d: Documentation only
```

## Clean Verification Checklist

After each phase, run:

```bash
make check        # ruff + mypy + pytest
```

After all 5 phases:

```bash
make demo         # full end-to-end with Docker
curl http://localhost:8000/healthz
curl "http://localhost:8000/v1/insights?project_id=project-1" | jq
curl "http://localhost:8000/v1/topics?project_id=project-1" | jq
curl "http://localhost:8000/v1/reports/current?project_id=project-1" | jq
agnost-export-report project-1; echo $?
```

Open `http://localhost:8000` — dashboard loads, topic growth rates show `None` for window gaps and real rates when enough history exists. Sentiment distribution has nuanced 3-way split. Representative examples show actual user quotes.
