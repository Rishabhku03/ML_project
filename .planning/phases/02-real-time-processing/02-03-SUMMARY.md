---
phase: 02-real-time-processing
plan: "02-03"
name: FastAPI Middleware Integration
completed: 2026-04-04
duration: ~15m
tasks_completed: 3
tasks_total: 3
dependencies:
  requires: [02-02 (TextCleaner)]
  provides: [middleware-integration, cleaned-text-persistence]
  affects: [api-routes, messages-table]
tech_stack:
  added: [Starlette BaseHTTPMiddleware]
  patterns: [request.state data passing, MinIO batch buffering]
key_files:
  created:
    - src/api/middleware.py
  modified:
    - src/api/models.py
    - src/api/main.py
    - src/api/routes/messages.py
    - src/api/routes/flags.py
  pre_existing:
    - scripts/add_cleaned_text_column.py
    - tests/test_middleware.py
---

# Phase 02 Plan 03: FastAPI Middleware Integration Summary

Wired the TextCleaner module (from Plan 02-02) into the FastAPI application as middleware that intercepts incoming message and flag requests, cleans text, persists to PostgreSQL, and returns both raw and cleaned text in API responses.

## Tasks Completed

### Task 1: Migration Script ✅
`scripts/add_cleaned_text_column.py` — pre-existing standalone migration script. Executes `ALTER TABLE messages ADD COLUMN IF NOT EXISTS cleaned_text TEXT;` using `get_db_connection()`. Idempotent and safe to re-run.

### Task 2: TextCleaningMiddleware + Models + Routes ✅
Created/modified 5 files:

- **`src/api/middleware.py`** (NEW) — `TextCleaningMiddleware` extending `BaseHTTPMiddleware`. Intercepts POST `/messages` and POST `/flags`, reads request body once, applies `TextCleaner` to text fields, persists to PostgreSQL with `cleaned_text`, buffers for MinIO batch upload (10K rows), stores cleaned body on `request.state.cleaned_body`.

- **`src/api/models.py`** (MODIFIED) — Added `raw_text` and `cleaned_text` optional fields to `MessageResponse`. Added `reason_cleaned` to `FlagResponse`.

- **`src/api/main.py`** (MODIFIED) — Registered `TextCleaningMiddleware` before routers via `app.add_middleware(TextCleaningMiddleware)`.

- **`src/api/routes/messages.py`** (MODIFIED) — Reads `request.state.cleaned_body`, returns `raw_text` + `cleaned_text` in response (D-13). Uses `_message_id` from middleware persistence.

- **`src/api/routes/flags.py`** (MODIFIED) — Reads `request.state.cleaned_body`, returns `reason_cleaned` in response.

### Task 3: Integration Tests ✅
`tests/test_middleware.py` — 6 tests, all passing:
1. `test_post_messages_returns_raw_and_cleaned` — verifies raw_text and cleaned_text in response
2. `test_post_messages_persists_to_db` — verifies PostgreSQL INSERT with cleaned_text column
3. `test_post_flags_cleans_reason` — verifies PII scrubbed from flag reason
4. `test_get_health_not_intercepted` — GET /health passes through cleanly
5. `test_cleaning_in_middleware` — markdown, URLs, PII all cleaned in one request
6. `test_cleaned_differs_from_raw` — cleaned_text ≠ raw_text for dirty input

## Key Design Decisions

- **Request body read once**: Starlette's `Request.body()` can only be read once. Used `request.state.cleaned_body` to pass cleaned data to route handlers — this is the correct Starlette pattern.
- **Failure pass-through**: If middleware fails (DB error, cleaning error), it logs the exception and passes the original body through so routes can still respond. API availability > correctness.
- **MinIO upload fire-and-forget**: MinIO batch flush failures are logged but not raised — a MinIO outage should not block API responses.
- **Middleware-only persistence**: The middleware handles all PostgreSQL writes. Routes only read from `request.state` and format responses.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

| Check | Result |
|---|---|
| `pytest tests/test_middleware.py -x -v` | ✅ 6 passed |
| `pytest tests/test_text_cleaner.py -x -v` | ✅ 14 passed (no regressions) |
| `python3 -c "from src.api.middleware import TextCleaningMiddleware"` | ✅ OK |
| `python3 -c "from src.api.main import app"` | ✅ OK |
| `python3 -c "import ast; ast.parse(open('scripts/...').read())"` | ✅ OK |
