# Phase 2: Real-time Processing - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Synthetic traffic generator sends sustained HTTP requests (~15-20 RPS) to FastAPI endpoints (`POST /messages`, `POST /flags`). Incoming message text passes through a shared `text_cleaner.py` module via FastAPI middleware that strips markdown, standardizes emojis to `:shortcode:`, replaces URLs with `[URL]` placeholder, scrubs PII via regex, and normalizes Unicode (ftfy). Cleaned text is persisted to PostgreSQL and batched to MinIO. The `text_cleaner.py` module is designed as a pipeline class reusable by both online and batch (Phase 3) paths.

Out of scope: ML inference, model serving, batch compilation, Zulip webhook integration.
</domain>

<decisions>
## Implementation Decisions

### Traffic Generator (INGEST-04)
- **D-01:** Sustained stream dispatch at ~15-20 RPS (matches production load spec from project report)
- **D-02:** Async concurrency model using `asyncio` + `aiohttp` (matches FastAPI's async nature)
- **D-03:** Mixed data source — reads from `combined_dataset.csv` rows AND generates synthetic messages via existing HF API calls
- **D-04:** Generator script: `src/data/synthetic_traffic_generator.py`

### text_cleaner.py Shared Module (ONLINE-01 through ONLINE-06)
- **D-05:** Pipeline class design — `TextCleaner` class with configurable ordered steps (not individual composable functions or single monolithic function)
- **D-06:** Step execution order: Unicode normalization (ftfy) → Markdown strip → URL extraction → Emoji standardization → PII scrub
- **D-07:** Regex-based PII scrubbing for emails, phone numbers, usernames (no external NER dependency)
- **D-08:** URLs replaced with `[URL]` placeholder (preserves position for NLP, not stored separately)
- **D-09:** Emoji standardization to `:shortcode:` format (e.g., 😂 → `:joy:`)
- **D-10:** Module location: `src/data/text_cleaner.py` (shared by online and batch paths per ONLINE-06)

### Preprocessing Integration
- **D-11:** FastAPI middleware intercepts both `POST /messages` and `POST /flags` — cleans `text`/`reason` fields before route handler
- **D-12:** Middleware persists message to PostgreSQL `messages` table on ingest (write-on-ingest, not deferred)
- **D-13:** API response returns both `raw_text` and `cleaned_text` for demo verification

### Cleaned Text Storage
- **D-14:** Separate `cleaned_text` column on `messages` table (raw text preserved for audit)
- **D-15:** Schema change via standalone migration script (ALTER TABLE), not update to init SQL
- **D-16:** Cleaned data also uploaded to MinIO `zulip-raw-messages/cleaned/` for consistency with Phase 1 pattern
- **D-17:** MinIO upload batched at 10K rows (smaller than Phase 1's 50K for faster availability)

### Agent's Discretion
- Specific regex patterns for PII detection (email, phone, username)
- Markdown stripping library choice (markdownify, mistune, or custom regex)
- Emoji library choice (emoji, demoji, or custom mapping)
- Middleware error handling behavior (log and continue vs. reject request)
- Traffic generator message template wording and Zulip-style formatting

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Documents
- `Idea.md` — Data architecture implementation plan: describes online_processor.py and synthetic_traffic_generator.py purpose and placement
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: production load spec (15-20 RPS), system design, data flow

### Requirements
- `.planning/REQUIREMENTS.md` — Requirements INGEST-04, ONLINE-01 through ONLINE-06 for this phase

### Prior Phase Context
- `.planning/phases/01-infrastructure-ingestion/01-CONTEXT.md` — Decisions D-01 through D-15 (PostgreSQL schema, MinIO buckets, synthetic data generation, source tagging)

### Existing Code (integration points)
- `src/api/main.py` — FastAPI app entry point where middleware will be added
- `src/api/routes/messages.py` — POST /messages route (currently dummy response)
- `src/api/routes/flags.py` — POST /flags route (currently dummy response)
- `src/api/models.py` — Pydantic models (MessagePayload, FlagPayload) that middleware will extend
- `src/data/synthetic_generator.py` — Existing synthetic data generator (data source for traffic generator)
- `src/utils/config.py` — Config dataclass with env vars (DB URL, MinIO creds, HF token)
- `src/utils/db.py` — PostgreSQL connection helper

### Course Reference
- `lecture and labs.txt` — Course lab URLs for relevant tools

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/synthetic_generator.py` — HF API call logic, retry pattern, text parsing can be reused by traffic generator
- `src/data/prompts.py` — Generation prompts and label distribution constants for synthetic message generation
- `src/utils/config.py` — Frozen dataclass Config pattern — extend with new env vars if needed
- `src/utils/db.py` — `get_db_connection()` — used by middleware for PG writes
- `src/utils/minio_client.py` — MinIO client helper — used for cleaned data uploads
- `src/api/models.py` — Pydantic models — extend `MessageResponse` with `cleaned_text` field

### Established Patterns
- Frozen dataclass for configuration (Config in config.py)
- Logging via `logging.getLogger(__name__)` per module
- FastAPI router pattern (separate route files in `src/api/routes/`)
- CSV chunked upload to MinIO (from ingest_and_expand.py)
- Retry with exponential backoff (from synthetic_generator.py)

### Integration Points
- `src/api/main.py` — Add middleware via `app.add_middleware()` before routers
- `src/api/models.py` — Extend `MessageResponse` with `raw_text` and `cleaned_text` fields
- PostgreSQL `messages` table — needs `cleaned_text` column (migration script)
- Docker Compose — no changes needed (middleware is app-level)

</code_context>

<specifics>
## Specific Ideas

- Traffic generator should read from combined_dataset.csv to replay real rows as HTTP POST requests, mixing with synthetic messages from the HF API
- The `TextCleaner` class should accept a list of step callables in its constructor, allowing the batch path (Phase 3) to reuse it with potentially different step configurations
- Middleware should log each cleaning operation (before/after) for the demo video
- Consider adding a `/clean` test endpoint that accepts raw text and returns cleaned output — useful for demo verification

</specifics>

<deferred>
## Deferred Ideas

- Parquet format for MinIO uploads (deferred to batch pipeline or later)
- Real-time feature store (Redis) for rolling window counts — v2 requirement (ADV-03)
- Redpanda event streaming for true real-time pipeline — v2 requirement (ADV-02)
- Configurable cleaning step order via YAML — deferred to Phase 4 (CONFIG-01)

</deferred>

---

*Phase: 02-real-time-processing*
*Context gathered: 2026-04-03*
