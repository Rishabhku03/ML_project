# Phase 2: Real-time Processing — Detailed Notes

**Project:** ChatSentry Data Pipeline
**Phase:** Phase 2 — Real-time Processing
**Team Member:** Rishabh Narayan (Data Specialist)
**Date Completed:** 2026-04-04
**Status:** Complete (54/54 tests passing)

---

## Table of Contents

1. [Motivation](#motivation)
2. [Objectives & Requirements](#objectives--requirements)
3. [Design Decisions](#design-decisions)
4. [What We Built](#what-we-built)
5. [Bugs Encountered & Fixes](#bugs-encountered--fixes)
6. [Testing](#testing)
7. [Lessons Learned](#lessons-learned)
8. [Deferred Items (Future Phases)](#deferred-items-future-phases)

---

## Motivation

ChatSentry is an AI-powered content moderation system for Zulip chat. The raw messages flowing into the system contain a mix of artifacts that degrade ML model performance:

- **Markdown formatting** (`**bold**`, `_italic_`, `[link](url)`) — adds noise to tokenization
- **Unicode issues** (mojibake like `cafÃ©` instead of `café`) — common in scraped Reddit data
- **URLs** — high-cardinality tokens that don't generalize
- **Emojis** — inconsistent representation (`😀` vs `:grinning_face:`) across platforms
- **PII** (emails, phone numbers, usernames) — privacy risk if included in training data

Phase 2 solves this by creating a **real-time text preprocessing pipeline** that normalizes all incoming messages before they're stored for training or used for inference.

### Why Real-time?

The system has two data paths:
1. **Real-time (Phase 2):** Messages arrive via API, get cleaned instantly, stored in PostgreSQL for immediate moderation
2. **Batch (Phase 3):** Bulk training data compiled from PostgreSQL, also uses the same TextCleaner

Phase 2 establishes the shared `TextCleaner` module that both paths use, ensuring consistent preprocessing whether a message arrives one-at-a-time or in bulk.

---

## Objectives & Requirements

### Requirements (from REQUIREMENTS.md)

| Req ID | Description | Status |
|--------|-------------|--------|
| INGEST-04 | Synthetic HTTP traffic generator hitting FastAPI endpoints | Complete |
| ONLINE-01 | Markdown/HTML stripping | Complete |
| ONLINE-02 | Emoji standardization to `:shortcode:` format | Complete |
| ONLINE-03 | URL extraction (replace with `[URL]`) | Complete |
| ONLINE-04 | PII scrubbing (email, phone, username) | Complete |
| ONLINE-05 | Unicode normalization via ftfy | Complete |
| ONLINE-06 | Shared TextCleaner pipeline module | Complete |

### Success Criteria

1. Synthetic traffic generator sends sustained HTTP requests (~15-20 RPS) to `POST /messages` and `POST /flags`
2. Message text is cleaned: markdown stripped, emojis standardized to `:shortcode:`, URLs extracted
3. PII (emails, phone numbers, usernames) is scrubbed from message text
4. Unicode normalization fixes mojibake in scraped Reddit data via ftfy
5. `text_cleaner.py` shared module exists and is used by both online and batch processing paths

---

## Design Decisions

### D-01 to D-04: Traffic Generator
- **D-01:** Sustained stream dispatch at ~15-20 RPS (matches production load spec)
- **D-02:** Async concurrency model using `asyncio` + `aiohttp` (matches FastAPI's async nature)
- **D-03:** Mixed data source — reads from `combined_dataset.csv` rows AND generates synthetic messages via HF API
- **D-04:** Generator script at `src/data/synthetic_traffic_generator.py`

### D-05 to D-10: TextCleaner Module
- **D-05:** Pipeline class design with configurable ordered steps
- **D-06:** Step execution order: Unicode (ftfy) → Markdown strip → URL extraction → Emoji standardization → PII scrub
- **D-07:** Regex-based PII scrubbing (no external NER dependency)
- **D-08:** URLs replaced with `[URL]` placeholder (preserves position for NLP)
- **D-09:** Emoji standardization to `:shortcode:` format (e.g., `😂` → `:joy:`)
- **D-10:** Module location: `src/data/text_cleaner.py` (shared by online and batch paths)

### D-11 to D-13: Preprocessing Integration
- **D-11:** FastAPI middleware intercepts `POST /messages` and `POST /flags`
- **D-12:** Write-on-ingest — middleware persists to PostgreSQL immediately (not deferred)
- **D-13:** API response returns both `raw_text` and `cleaned_text` for demo verification

### D-14 to D-17: Cleaned Text Storage
- **D-14:** Separate `cleaned_text` column on `messages` table (raw preserved for audit)
- **D-15:** Schema change via ALTER TABLE migration
- **D-16:** Cleaned data also uploaded to MinIO `zulip-raw-messages/cleaned/`
- **D-17:** MinIO upload batched at 10K rows

---

## What We Built

### Files Created/Modified

| File | Purpose |
|------|---------|
| `src/data/text_cleaner.py` | Shared TextCleaner pipeline class with 5 cleaning steps |
| `src/api/main.py` | FastAPI app with inline middleware for text cleaning + persistence |
| `src/api/models.py` | Pydantic models: MessagePayload, MessageResponse (with raw_text/cleaned_text), FlagPayload, FlagResponse |
| `src/api/routes/messages.py` | POST /messages route handler |
| `src/api/routes/flags.py` | POST /flags route handler |
| `src/data/synthetic_traffic_generator.py` | Async traffic generator (CSV + HF synthetic, 15-20 RPS) |
| `src/utils/config.py` | Config dataclass (DB URL, MinIO creds, HF token) |
| `src/utils/db.py` | PostgreSQL connection helper |
| `src/utils/minio_client.py` | MinIO client factory |
| `docker/init_sql/00_create_tables.sql` | PostgreSQL schema with `cleaned_text` column added |
| `docker/docker-compose.yaml` | Docker Compose with PostgreSQL, MinIO, FastAPI, Adminer |
| `tests/test_text_cleaner.py` | 13 unit tests for TextCleaner pipeline |
| `tests/test_middleware.py` | 6 integration tests for middleware |
| `tests/test_traffic_generator.py` | 9 tests for traffic generator |

### Architecture

```
                    ┌─────────────────────────────────┐
                    │      TextCleaner Pipeline        │
                    │  1. fix_unicode (ftfy)            │
                    │  2. strip_markdown                │
                    │  3. extract_urls → [URL]          │
                    │  4. standardize_emojis → :code:   │
                    │  5. scrub_pii → [EMAIL]/[PHONE]   │
                    └──────────┬──────────────────────┘
                               │
    ┌──────────────┐    ┌──────┴──────┐    ┌──────────────┐
    │  CSV Rows    │───→│  FastAPI    │───→│  PostgreSQL  │
    │  (combined_  │    │  Middleware │    │  messages    │
    │  dataset.csv)│    │             │    │  (text +     │
    └──────────────┘    │  POST       │    │  cleaned_    │
    ┌──────────────┐    │  /messages  │    │  text)       │
    │  HF Synthetic│───→│  POST       │    └──────────────┘
    │  (Mistral-7B)│    │  /flags     │
    └──────────────┘    └──────┬──────┘    ┌──────────────┐
                               │           │  MinIO       │
                               └──────────→│  cleaned/    │
                                           │  batch.jsonl │
                                           └──────────────┘
```

### Data Flow

1. **Traffic generator** reads CSV rows (80%) or generates via HF API (20%)
2. Sends `POST /messages` (80%) or `POST /flags` (20%) to FastAPI
3. **Middleware** intercepts, applies TextCleaner pipeline
4. Cleaned text persisted to PostgreSQL (`messages.text` + `messages.cleaned_text`)
5. Flags persisted to PostgreSQL (`flags` table) with message FK
6. Cleaned data buffered in memory, flushed to MinIO as `.jsonl` batch (10K rows or manual flush)

---

## Bugs Encountered & Fixes

### Bug 1: HF Token Not Loading (`.env` location)

**Error:** `Illegal header value b'Bearer '` — empty HF token in API calls

**Root cause:** `load_dotenv()` in `src/utils/config.py` looks for `.env` in the current working directory (project root), but the token only existed in `docker/.env`.

**Fix:** Created `.env` in project root with `HF_TOKEN=hf_...` and updated `.gitignore` to use broad `.env` pattern.

**Commit:** `e817292`

---

### Bug 2: aiohttp Session Closed Race Condition

**Error:** `RuntimeError: Session is closed` at end of traffic generator run

**Root cause:** The `async with aiohttp.ClientSession()` block exited and closed the session while in-flight `asyncio.create_task()` requests were still trying to use it. Fire-and-forget tasks dispatched near the end of the duration hadn't completed when the context manager closed.

**Fix:** Collected all dispatched tasks in a `pending_tasks` list and added `await asyncio.gather(*pending_tasks, return_exceptions=True)` before the session context exits.

**Commit:** `e817292`

---

### Bug 3: MinIO Init Container Silently Failed

**Error:** MinIO buckets didn't exist after `docker compose up`. Tests `test_raw_messages_bucket_exists` and `test_training_data_bucket_exists` failed.

**Root cause:** The `minio/mc` Docker image is a scratch-based image with only the `mc` binary — no shell. The `command: |` block in docker-compose was passed as a single argument to `mc`, which didn't interpret it as shell commands.

**Fix:** Added `entrypoint: ["/bin/sh", "-c"]` to override the `mc` entrypoint, allowing shell command execution with `&&` chaining.

**Commit:** `e817292`

---

### Bug 4: Middleware Used Wrong Column Names for INSERT

**Error:** `psycopg2.errors.UndefinedColumn: column "raw_text" does not exist` — messages not persisting to PostgreSQL. Tests were passing because they mocked the DB.

**Root cause:** The middleware's `_persist_message()` used column names `raw_text` and `cleaned_text`, but the schema had `text` and `cleaned_text`. The column `raw_text` didn't exist.

**Fix:** Changed INSERT to use `text` for raw content. Added `cleaned_text` column to schema via ALTER TABLE.

**Commit:** `ca7b4ca`

---

### Bug 5: `source` CHECK Constraint Violation

**Error:** `psycopg2.errors.CheckViolation: new row for relation "messages" violates check constraint "messages_source_check"` — 422 errors when testing with `"source": "test"`.

**Root cause:** The PostgreSQL `messages` table has a CHECK constraint: `CHECK (source IN ('real', 'synthetic_hf'))`. Test curl commands used `"source": "test"` which isn't allowed.

**Fix:** Added normalization in `_persist_message()`: if source is not `real` or `synthetic_hf`, default to `real`.

**Commit:** `ca7b4ca`

---

### Bug 6: Flags Not Persisting to PostgreSQL

**Error:** The `/flags` endpoint returned a response but nothing appeared in the `flags` table.

**Root cause:** The `flags.py` route only returned a response — it never wrote to the database. The middleware cleaned the reason text but didn't call any persistence function for flags.

**Fix:** Added `_persist_flag()` function in `main.py` that resolves message and user foreign keys and inserts into the `flags` table. Updated middleware dispatch to call it for `/flags` requests.

**Commit:** `ca7b4ca`

---

### Bug 7: User Foreign Key Constraint

**Error:** `psycopg2.errors.NotNullViolation` when inserting messages — `user_id` references `users(id)` but incoming requests had arbitrary string user IDs.

**Root cause:** The `messages.user_id` column is `UUID NOT NULL REFERENCES users(id)`. Arbitrary strings like `"test-1"` don't exist in the `users` table.

**Fix:** Added `_get_default_user()` function that looks up the seed user `test_user`. If the incoming `user_id` doesn't match any user, fall back to the seed user.

**Commit:** `ca7b4ca`

---

### Bug 8: Empty Messages Persisted from CSV

**Error:** Empty rows appeared in PostgreSQL after running traffic generator.

**Root cause:** Some rows in `combined_dataset.csv` have whitespace-only or quote-only text. The CSV loader filtered empty strings but not whitespace-only ones.

**Fix:** Added empty/whitespace check in middleware: `raw_text = body.get("text", "").strip()` followed by `if not raw_text: skip`.

**Commit:** `91e5592`

---

### Bug 9: Traffic Generator Flags Used Random UUIDs

**Error:** Flags from traffic generator never appeared in PostgreSQL — `flag_count` was always 0.

**Root cause:** `_build_flag_payload()` generated random UUIDs for `message_id`. The middleware's `_persist_flag()` looks up the message in PostgreSQL and skips the flag if the message doesn't exist. Random UUIDs never matched existing messages.

**Fix:** Added `posted_message_ids` tracking — message IDs from successful `POST /messages` calls are collected and used for flag payloads. Added `_dispatch_and_track()` function.

**Commit:** `1012899`

---

### Bug 10: Synthetic Generator Missing Entry Point

**Error:** `python3 -m src.data.synthetic_generator` ran silently and produced no output.

**Root cause:** The file defined `generate_synthetic_data()` but had no `if __name__ == "__main__"` block — nothing ever called the function.

**Fix:** Added `main()` with argparse (`--count`, `--bucket`) and `if __name__ == "__main__"` entry point.

**Commit:** `3fc563a`

---

### Bug 11: Middleware Test Mock Patches Wrong Module

**Error:** `test_post_messages_persists_to_db` failed with `assert cursor.execute.called` — the mock wasn't intercepting calls.

**Root cause:** After refactoring middleware from `src/api/middleware.py` to inline in `src/api/main.py`, the test still patched `src.api.middleware.get_db_connection` instead of `src.api.main.get_db_connection`.

**Fix:** Updated test mock patches to target `src.api.main.get_db_connection` and `src.api.main.get_minio_client`.

**Commit:** `ca7b4ca`

---

## Testing

### Test Suite (54 tests total)

| Test File | Tests | Covers |
|-----------|-------|--------|
| `test_text_cleaner.py` | 13 | Individual steps (unicode, markdown, URL, emoji, PII) + pipeline integration |
| `test_middleware.py` | 6 | Middleware interception, persistence, cleaning, health bypass |
| `test_traffic_generator.py` | 9 | CSV loading, payload building, RPS, connection errors, empty CSV |
| `test_synthetic_gen.py` | 8 | Prompts, label distribution, text parsing, target counts |
| `test_csv_chunking.py` | 4 | CSV file existence, columns, chunking, row counts |
| `test_schema.py` | 6 | Tables, columns, GIN index, constraints |
| `test_minio_buckets.py` | 2 | Bucket existence |
| `test_minio_upload.py` | 2 | Bucket accessibility, script import |
| `test_api_health.py` | 3 | Health, messages, flags endpoints |

### End-to-End Tests Performed

| Test | Command | Expected | Result |
|------|---------|----------|--------|
| Markdown stripping | `POST /messages` with `**Bold**` | `Bold` | Pass |
| Emoji standardization | `POST /messages` with `😀👍🔥` | `:grinning_face::thumbs_up::fire:` | Pass |
| PII scrubbing | `POST /messages` with email+phone | `[EMAIL]`, `[PHONE]` | Pass |
| URL extraction | `POST /messages` with `https://...` | `[URL]` | Pass |
| Unicode fix | `POST /messages` with `cafÃ©` | `café` | Pass |
| Flags cleaning | `POST /flags` with PII in reason | PII scrubbed in reason_cleaned | Pass |
| PostgreSQL persistence | Query messages table | All test messages with cleaned_text | Pass |
| MinIO cleaned data | Flush + list `cleaned/` prefix | `.jsonl` batch file | Pass |
| Traffic generator | 30s at 3 RPS | Messages + flags persisted, 0 errors | Pass |
| Source tagging | Query messages GROUP BY source | Mix of `real` and `synthetic_hf` | Pass |
| Flag persistence | Query flags JOIN messages | Flags linked to real messages | Pass |

### Final Test Output

```
54 passed in 6.77s
```

---

## Lessons Learned

1. **Mock patches must match actual import paths.** When refactoring code from `middleware.py` to `main.py`, tests that patched `src.api.middleware.get_db_connection` broke silently — they passed because they mocked the wrong target.

2. **Docker images without shells are common.** The `minio/mc` image is scratch-based with only the `mc` binary. Always check if an image has a shell before writing multi-line command blocks.

3. **Foreign keys require data to exist first.** The `messages.user_id` FK to `users(id)` meant every message needed a valid user. Having a seed user with a fallback lookup prevented crashes.

4. **Fire-and-forget tasks need lifecycle management.** `asyncio.create_task()` without awaiting causes race conditions when the session closes. Always collect tasks and await before cleanup.

5. **Source CHECK constraints catch real bugs.** The `source IN ('real', 'synthetic_hf')` constraint prevented invalid data from being inserted, even though it caused initial test failures.

6. **Empty CSV rows are more common than expected.** Real-world datasets like `combined_dataset.csv` contain blank rows, quote-only rows, and whitespace-only rows. Always filter at ingestion time.

7. **Message ID tracking enables realistic flag generation.** Without tracking which messages were actually persisted, flag payloads referenced non-existent messages and were silently rejected.

---

## Deferred Items (Future Phases)

These were identified but explicitly deferred:

| Item | Phase | Reason |
|------|-------|--------|
| Parquet format for MinIO uploads | Phase 3 or later | CSV is sufficient for current scale |
| Real-time feature store (Redis) | v2 requirement (ADV-03) | Not needed for MVP |
| Redpanda event streaming | v2 requirement (ADV-02) | Synchronous processing sufficient |
| Configurable cleaning step order via YAML | Phase 4 (CONFIG-01) | Hardcoded order works for now |
| `/admin/flush` endpoint for MinIO | Testing only | Added for convenience, not production |
| Deterministic seeds for reproducible synthetic generation | v2 (QUALITY-01, ADV-01) | Not required for course deadline |

---

## References

- Phase context: `.planning/phases/02-real-time-processing/02-CONTEXT.md`
- Requirements: `.planning/REQUIREMENTS.md` (INGEST-04, ONLINE-01 through ONLINE-06)
- Roadmap: `.planning/ROADMAP.md`
- Git history: `git log --oneline` (commits `e817292` through `1012899`)
- Project report: `MLOps-Project-Report-TeamChatSentry.txt`

---

*Last updated: 2026-04-04*
*54/54 tests passing*
