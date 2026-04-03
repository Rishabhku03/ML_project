# Phase 1: Infrastructure & Ingestion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 1-infrastructure-ingestion
**Areas discussed:** PostgreSQL schema details, CSV ingestion approach, Synthetic data generation, Source tagging convention

---

## PostgreSQL Schema Details

| Option | Description | Selected |
|--------|-------------|----------|
| Full schema upfront | Full schema now — all tables, columns, foreign keys, indexes ready | ✓ |
| Minimal, evolve later | Minimal tables now, add flags/moderation later in Phase 3 | |

| Option | Description | Selected |
|--------|-------------|----------|
| JSONB for label vectors | Store full label vectors as JSONB column. Flexible, less schema churn. | |
| Individual boolean columns | One boolean column per label. Rigid but queryable with SQL operators. | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Basic indexes | Standard B-tree on timestamps, user_id, source column | |
| Full-text search index | Add GIN index on the text column for full-text search | ✓ |

**User's choices:** Full schema upfront, individual boolean columns, full-text search index.
**Notes:** User wants all tables ready from the start. Toxicity labels as individual boolean columns for direct SQL queryability. GIN index on messages.text for batch pipeline filtering needs.

---

## CSV Ingestion Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Upload as CSV | Upload raw CSV chunks as-is to MinIO | ✓ |
| Convert to Parquet | Convert to Parquet during ingestion | |

| Option | Description | Selected |
|--------|-------------|----------|
| 100K rows | ~16 chunks total. Good balance of memory vs HTTP overhead. | |
| 500K rows | ~4 chunks total. More memory per chunk (~1-2GB). | |
| 50K rows | ~32 chunks total. Safest on memory, more upload calls. | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| MinIO only | Only upload CSV chunks to MinIO | ✓ |
| MinIO + PostgreSQL | Upload to MinIO AND insert into PostgreSQL | |

| Option | Description | Selected |
|--------|-------------|----------|
| by-dataset folder | zulip-raw-messages/combined_dataset/chunk_NNN.csv | ✓ |
| date-partitioned | zulip-raw-messages/2026-04-03/chunk_NNN.csv | |

**User's choices:** CSV format, 50K chunks, MinIO only, by-dataset folder structure.
**Notes:** Conservative chunk size (50K) for KVM memory safety. Data stays in MinIO only during ingestion — PostgreSQL loading deferred.

---

## Synthetic Data Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Mistral-7B-Instruct-v0.2 | Free tier, fast, good for conversational text | ✓ |
| Llama-2-7b-chat-hf | Good for toxic content generation. May need paid tier. | |
| Configurable | Set via YAML later | |

| Option | Description | Selected |
|--------|-------------|----------|
| ~160K rows (~10%) | Enough to demonstrate source tagging without excessive API costs | |
| ~80K rows (~5%) | Minimal API usage | |
| ~400K rows (~25%) | More realistic augmentation for training | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Match real distribution | Mirror the real dataset's label distribution | |
| Oversample minority classes | Balance the dataset for the ML team | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Single-turn prompts | Simple, quick to implement | |
| Multi-turn thread prompts | Generate multi-message Zulip threads with context | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt-guided labels | Labels from prompt instructions, not model output | ✓ |
| Post-hoc classification | Generate text, then classify. Double API cost. | |

**User's choices:** Mistral-7B, ~400K rows, oversample minority classes, multi-turn threads, prompt-guided labels.
**Notes:** Larger synthetic volume (25%) to meaningfully augment minority classes. Multi-turn prompts for realistic Zulip conversation style. Labels assigned directly from prompt instructions to avoid extra API calls.

---

## Source Tagging Convention

| Option | Description | Selected |
|--------|-------------|----------|
| String enum column | Single column with values like 'real', 'synthetic_hf' | ✓ |
| Boolean + detail column | Separate 'is_synthetic' boolean + 'source_detail' text | |

| Option | Description | Selected |
|--------|-------------|----------|
| Folder split | zulip-raw-messages/real/ and zulip-raw-messages/synthetic/ | ✓ |
| Column-only tagging | Single folder, source column inside each CSV chunk | |

**User's choices:** String enum source column, folder split in MinIO.
**Notes:** Folder split makes real vs synthetic immediately visible in MinIO UI. String enum is extensible if more generation methods are added later.

---

## Agent's Discretion

- Docker Compose port mappings, volume mounts, environment variable naming
- PostgreSQL schema details for users/flags/moderation tables beyond requirements
- Error handling and retry logic for HuggingFace API calls
- Synthetic data prompt template wording

## Deferred Ideas

- Parquet conversion during ingestion (add in batch pipeline phase)
- PostgreSQL loading of ingested data (deferred to batch pipeline)
- Deterministic seeds for reproducible generation (v2 requirements)
