# Phase 2: Real-time Processing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 02-real-time-processing
**Areas discussed:** Traffic Generator Dispatch, text_cleaner.py Interface, Preprocessing Integration Point, Cleaned Text Storage

---

## Traffic Generator Dispatch

| Option | Description | Selected |
|--------|-------------|----------|
| Sustained stream | Steady 15-20 RPS matching production load spec — realistic for demo | ✓ |
| Burst dump | Dump N messages as fast as possible, then stop | |
| Ramped load | Starts slow, ramps up over time | |

**User's choice:** Sustained stream

| Option | Description | Selected |
|--------|-------------|----------|
| Async (asyncio + aiohttp) | Matches FastAPI's async nature, lightweight | ✓ |
| Threaded | threading.Thread with requests — simpler but heavier | |
| Sequential loop | Single-threaded sequential — won't hit 15-20 RPS | |

**User's choice:** Async (asyncio + aiohttp)

| Option | Description | Selected |
|--------|-------------|----------|
| Mix real + synthetic | Reads CSV rows + generates synthetic via HF API | ✓ |
| Synthetic only | Only generates via HF API | |
| Real CSV only | Only replays combined_dataset.csv rows | |

**User's choice:** Mix real + synthetic

**Notes:** Traffic generator is `synthetic_traffic_generator.py`, sends to POST /messages and POST /flags.

---

## text_cleaner.py Interface

| Option | Description | Selected |
|--------|-------------|----------|
| Pipeline class | TextCleaner class with configurable ordered steps | ✓ |
| Composable functions | Individual functions (strip_markdown, normalize_emoji, etc.) | |
| Single function | Single clean_text() doing everything internally | |

**User's choice:** Pipeline class

| Option | Description | Selected |
|--------|-------------|----------|
| Unicode-first | ftfy → Markdown → URL → Emoji → PII | ✓ |
| Content-first | Markdown → Emoji → URL → PII → Unicode | |
| Configurable order | Make step order configurable via constructor/YAML | |

**User's choice:** Unicode-first (ftfy → Markdown → URL → Emoji → PII)

| Option | Description | Selected |
|--------|-------------|----------|
| Replace with placeholder | Replace URLs with [URL] placeholder | ✓ |
| Strip completely | Remove URLs entirely | |
| Extract to side channel | Extract URLs to separate return field | |

**User's choice:** Replace with placeholder

| Option | Description | Selected |
|--------|-------------|----------|
| Regex-based | Regex patterns for email, phone, username | ✓ |
| NER-based | Use presidio or similar NER library | |
| Regex + allowlist | Regex + configurable allowlist | |

**User's choice:** Regex-based

**Notes:** Module at `src/data/text_cleaner.py`, shared by online and batch paths.

---

## Preprocessing Integration Point

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware | FastAPI middleware intercepts all requests, cleans before routing | ✓ |
| Route-level call | Clean text directly in create_message handler | |
| Dependency injection | FastAPI Depends() injection | |

**User's choice:** Middleware

| Option | Description | Selected |
|--------|-------------|----------|
| Return both | API response includes raw_text and cleaned_text | ✓ |
| Status only | Only return status/message_id | |

**User's choice:** Return both raw_text and cleaned_text

| Option | Description | Selected |
|--------|-------------|----------|
| Write on ingest | Middleware writes to PostgreSQL on ingestion | ✓ |
| Clean only, no write | Clean but don't write to PG | |

**User's choice:** Write on ingest

| Option | Description | Selected |
|--------|-------------|----------|
| Messages only | Only POST /messages gets cleaning middleware | |
| Both endpoints | Both /messages and /flags | ✓ |

**User's choice:** Both endpoints

**Notes:** Middleware applies to both /messages (text field) and /flags (reason field).

---

## Cleaned Text Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Separate column | Add cleaned_text column to messages table | ✓ |
| Overwrite text | Overwrite text column with cleaned version | |
| MinIO only | Store cleaned text only in MinIO | |

**User's choice:** Separate column (cleaned_text)

| Option | Description | Selected |
|--------|-------------|----------|
| Store URLs in JSONB | Store extracted URLs as JSONB column | |
| Placeholder only | Only store cleaned_text, URLs in [URL] placeholder | ✓ |

**User's choice:** Placeholder only (no separate URL storage)

| Option | Description | Selected |
|--------|-------------|----------|
| Update init SQL | Update existing init SQL in docker setup | |
| Migration script | Write separate ALTER TABLE migration | ✓ |

**User's choice:** Migration script

| Option | Description | Selected |
|--------|-------------|----------|
| Upload to MinIO | Also upload cleaned CSVs to MinIO zulip-raw-messages/cleaned/ | ✓ |
| PG only | PostgreSQL only | |

**User's choice:** Upload to MinIO

| Option | Description | Selected |
|--------|-------------|----------|
| 50K rows | Same 50K-row chunks as Phase 1 | |
| 10K rows | Smaller batches for faster MinIO availability | ✓ |
| Configurable | Via pipeline config | |

**User's choice:** 10K rows

**Notes:** Cleaned data uploaded to MinIO in batches of 10K rows.

---

## Agent's Discretion

- Regex patterns for PII detection (email, phone, username)
- Markdown stripping library choice
- Emoji library choice
- Middleware error handling behavior
- Traffic generator message templates and Zulip-style formatting

## Deferred Ideas

- Parquet format for MinIO uploads
- Real-time feature store (Redis) — v2 requirement
- Redpanda event streaming — v2 requirement
- Configurable cleaning step order via YAML — deferred to Phase 4
