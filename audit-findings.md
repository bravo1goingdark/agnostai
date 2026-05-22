# Agnost Codebase Audit — Issues & Fixes

## Summary

Thorough audit of the full-stack Agnost Conversation Intelligence Engine (Python backend + vanilla JS frontend). Found **1 definite bug**, **6 issues**, and several dead code / completeness gaps. Overall code quality is high — clean architecture, well-organized modules, comprehensive test coverage at the service/utility level.

---

## 🐛 Confirmed Bugs

### 1. `export_report.py` — `SystemExit` with string (always exits code 1)
**File:** `app/scripts/export_report.py` line 33  
**Problem:** `_export()` returns `report_file.read_text(...)` (a string), which is passed to `SystemExit()`. Python treats string args to `SystemExit` as error messages and exits with code 1.  
**Fix:** Change `_export()` to print the report text and return `0`:
```python
async def _export(project_id: str) -> int:
    ...
    print(report_file.read_text(encoding="utf-8"))
    return 0
```
**Verification:** Run `agnost-export-report project-1; echo $?` — should print `0`.

---

## ⚠️ Design / Logic Issues

### 2. `_growth_rate()` logic is broken — uses wrong time window boundaries
**File:** `app/services/clustering.py` lines ~597-617  
**Problem:** The function counts messages as "recent" if `created_at >= cutoff + timedelta(hours=hours / 2)`, and "older" if `created_at >= cutoff` but before that midpoint. This means:
- For `growth_24h`: messages from 12-24h ago are "older", 0-12h are "recent"
- Messages older than 24h are ignored entirely (skipped via `created_at < cutoff`)
- If all messages in a topic are < 12h old, `older == 0` and the function returns the raw `recent` count (not a growth rate at all)

**Fix:** The growth rate should compare two equal consecutive time windows:
```python
def _growth_rate(messages, *, hours: int) -> float | None:
    if len(messages) < 2:
        return None
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=hours)
    older_cutoff = now - timedelta(hours=hours * 2)
    
    recent = sum(1 for m in messages 
                 if _ensure_aware_datetime(m.get("created_at")) 
                 and m["created_at"] >= recent_cutoff)
    older = sum(1 for m in messages 
                if _ensure_aware_datetime(m.get("created_at")) 
                and older_cutoff <= m["created_at"] < recent_cutoff)
    
    if older == 0:
        return None  # Not enough history to compute growth rate
    return (recent - older) / older
```
**Verification:** Test with messages that have `created_at` values spanning multiple days — confirm growth rates are in [-1.0, +inf) range, not raw counts.

### 3. `_growth_rate` returns `float(recent)` when `older == 0` — semantically wrong
**File:** `app/services/clustering.py` line ~617  
**Problem:** `return float(recent) if recent else None` returns a raw count, not a growth rate. This gets stored in the DB as `topic.growth_24h` and surfaced in the API. The frontend's `renderTopicDetail()` shows this value as "24h growth" — but it's a count, not a rate. This is a semantic bug that pollutes the data.  
**Fix:** Return `None` when there's no older window to compare against (no growth rate can be computed).

### 4. `loadTopic()` sets `selectedTopicId` before fetch resolves — stale state on error
**File:** `frontend/assets/app.js` (in `loadTopic` function)  
**Problem:** `state.selectedTopicId = topicId` is set before the async fetch completes. If the fetch fails, the topic appears selected but the detail pane shows stale/empty data. The user has no indication the fetch failed except the status bar error.  
**Fix:** Move `state.selectedTopicId = topicId` into the `.then()` block, and reset to `null` in `.catch()`:
```javascript
function loadTopic(topicId) {
    state.topicDetail = null;
    renderTopicDetail();
    fetchJson(`/v1/topics/${topicId}`)
        .then((detail) => {
            state.selectedTopicId = topicId;
            state.topicDetail = detail;
            renderTopicDetail();
        })
        .catch((error) => {
            state.selectedTopicId = null;
            setStatus(error.message, "error");
        });
}
```

---

## 🧹 Dead Code

### 5. `loadTopicsOnly()` — defined but never called
**File:** `frontend/assets/app.js`  
**Fix:** Remove the function or wire it to a UI element.

### 6. `summarize_queue_metrics()` — never called
**File:** `app/services/insights.py`  
**Fix:** Remove or add to an observability endpoint. If it's planned for future use, add a comment.

### 7. `raw_payload_for_storage()` — never called
**File:** `app/services/ingestion.py`  
**Fix:** Remove it. The inline `payload.model_dump(mode="json")` is used instead.

### 8. `render_empty_report()` — only called in tests
**File:** `app/services/reports.py`  
**Fix:** Leave it if tests depend on it, but mark as test-utility or remove and inline into the test.

### 9. `RequestIdFilter` — defined but never attached to any logger
**File:** `app/logging.py`  
**Fix:** Either attach it to the root logger via `logging.getLogger().addFilter(RequestIdFilter())` or remove it. The `request_id` is interpolated directly into log messages currently.

---

## 🔧 Incomplete Features

### 10. API key validation not implemented
**File:** `app/config.py` (defines `api_key_header`), `app/models/tables.py` (has `api_key_hash` column)  
**Problem:** The `X-API-Key` header check (with hashed comparison against `project.api_key_hash`) is never wired up. No middleware, no dependency, no route decorator.  
**Fix:** Add a `Depends()` callable:
```python
# app/api/deps.py
from fastapi import Header, HTTPException

async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    if not x_api_key:
        raise HTTPException(401, "Missing API key")
    # hash and compare against project
```
Wire into the router or individual routes.  
**Priority:** Low per plan.md scope ("auth beyond a project API key is out of scope"), but the schema supports it and the field exists.

### 11. Real embedding model never loaded — sentence-transformers is listed but never used
**File:** `app/services/embeddings.py`  
**Problem:** The `pyproject.toml` lists `sentence-transformers` in `[ml]` extras, the plan.md says "use sentence-transformers/all-MiniLM-L6-v2", but `embed_text_stub` is always called. No code path loads or uses the real model.  
**Fix:** Add a `load_real_model()` function that's called when ML deps are available, and swap it in:
```python
_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(get_settings().embedding_model_name)
        except Exception:
            _model = None
    return _model

def embed_text(text: str, dimension: int) -> list[float]:
    model = _get_model()
    if model is not None:
        return model.encode(text).tolist()
    return embed_text_stub(text, dimension)
```

### 12. Sentiment is stub-only — no VADER/TextBlob fallback
**File:** `app/services/sentiment.py`  
**Problem:** Only keyword-based stub. REASONING.md acknowledges this as intentional, but a lightweight model (VADER) would be a meaningful upgrade with minimal complexity.  
**Priority:** Low — explicitly scoped as placeholder.

---

## 🧪 Test Coverage Gaps

### 13. No API route integration tests
**Problem:** Routes like `POST /v1/conversations`, `GET /v1/topics`, `GET /v1/insights`, `GET /v1/reports/current`, `POST /v1/demo/bootstrap` are never tested through the ASGI transport (`TestClient`).  
**Impact:** Route wiring errors, parameter parsing bugs, and error response formatting are untested.  
**Fix:** Add tests using `httpx.AsyncClient` with `httpx.ASGITransport`:
```python
from httpx import ASGITransport, AsyncClient

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

### 14. No `ClusterRun` failure path test
**Problem:** The exception handler in `run_cluster_batch()` (rollback + mark failed) is untested.  
**Fix:** Mock `_cluster_messages` to raise, verify `ClusterRun.status == "failed"` and `error_message` is set.

### 15. `FakeRedis` / `FakeJob` duplicated across test files
**Problem:** Both `test_ingestion.py` and `test_worker_flow.py` define identical fake classes.  
**Fix:** Move to `tests/conftest.py`.

---

## 🏗️ Architecture Observations (non-blocking)

### 16. Engine created at module import time in `db.py` and `jobs.py`
**Files:** `app/db.py` line 40, `app/workers/jobs.py` line 32  
**Problem:** If `DATABASE_URL` is wrong, the import crashes before FastAPI can serve a health check.  
**Priority:** Low for demo, high for production. Fix by moving engine creation to a lazy function or app lifespan.

### 17. `ConversationMessage` schema accepts extra fields silently
**File:** `app/models/schemas.py`  
**Problem:** `model_config = ConfigDict(extra="allow")` on `ConversationMessage` but `extra="forbid"` on `ConversationIngestRequest`. Inconsistent.  
**Fix:** Either make both `extra="forbid"` or add a comment explaining why.

### 18. `TopicSummary.representative_examples` returns topic terms, not actual messages
**File:** `app/services/clustering.py` line ~658  
**Problem:** `representative_examples = list(topic.terms or [])[:3]` — plan.md says "representative examples" should be actual message snippets. The cluster has a `representative_message_id` via `TopicMembership.is_representative`, but it's not fetched here.  
**Fix:** Query the representative message's content and use the first 160 characters as the example.

### 19. DuckDB import is loaded but never used
**File:** `app/services/ingestion.py` line 16  
**Problem:** `from duckdb import connect` is imported at module level. The function that used it (`raw_payload_for_storage`) is dead code. DuckDB is loaded into memory unnecessarily.  
**Fix:** Remove the DuckDB import and the dead function.

---

## Frontend Issues Summary

| # | Issue | Severity |
|---|-------|----------|
| 4 | `loadTopic()` state inconsistency on error | Medium |
| 5 | Dead code: `loadTopicsOnly()` | Low |
| — | No loading skeleton for initial data load | UX (Low) |
| — | No `prefers-reduced-motion` for spinner | Accessibility (Low) |
| — | No retry logic / timeout on fetch | Resilience (Low) |
| — | `escapeHtml()` covers standard chars — safe | ✅ |
| — | All API call shapes match backend responses | ✅ |
| — | All user content goes through `escapeHtml()` | ✅ |

---

## Items Confirmed Correct

- **Migration ↔ ORM models:** Perfect match across all 8 tables (projects, conversations, messages, message_embeddings, cluster_runs, topics, topic_memberships, processing_jobs)
- **All Makefile targets:** `install`, `migrate`, `demo`, `lint`, `type`, `test`, `check`, `run-api`, `run-worker` — all correct
- **All `.env.example` variables:** Complete coverage of every setting in `app/config.py`
- **All CLI scripts:** Correct (except `export_report.py` exit code bug)
- **All 7 test files:** No skipped or broken tests; 82 tests total; good quality
- **Docker setup:** Correct dev config with proper health checks and dependency ordering
- **REASONING.md:** Covers all plan.md design decisions
- **`data/` and `reports/`:** Exist with proper `.gitkeep` files

---

## Verification Steps

After fixes are applied, verify:

1. **Bug #1:** `agnost-export-report project-1; echo $?` → prints `0`
2. **Bug #2-3:** Write a test with messages spanning 72h, verify growth rates are -1.0 to +inf, not raw counts
3. **Bug #4:** Trigger a topic fetch failure (use invalid UUID, stop the API), verify `selectedTopicId` resets
4. **Dead code:** `grep` for removed function names — zero matches outside the file they belong to
5. **All existing tests pass:** `make check` (ruff + mypy + pytest)
6. **Full demo flow still works:** `make demo` with Docker running
7. **Frontend dashboard loads:** Open `http://localhost:8000`, click Bootstrap, verify topics render
