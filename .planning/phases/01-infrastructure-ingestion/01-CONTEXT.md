# Phase 1: Infrastructure & Ingestion - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Docker Compose stack running PostgreSQL, MinIO, and FastAPI stub on the KVM@TACC VM. PostgreSQL schema fully defined with all tables. CSV ingestion script reads `combined_dataset.csv` in chunks and uploads to MinIO. Synthetic data generated via HuggingFace API with source tagging and uploaded to MinIO. All services healthy and browsable.
</domain>

<decisions>
## Implementation Decisions

### PostgreSQL Schema
- **D-01:** Full schema upfront — all tables (users, messages, flags, moderation) created with complete columns, foreign keys, and constraints
- **D-02:** Individual boolean columns for toxicity labels: `toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate`, `is_suicide` (not JSONB)
- **D-03:** GIN full-text search index on messages.text column
- **D-04:** UUIDs for all primary keys, source tracking column, created_at timestamps

### CSV Ingestion
- **D-05:** Upload CSV chunks as-is to MinIO (no Parquet conversion during ingestion)
- **D-06:** 50,000 rows per chunk (~32 chunks total for 1.58M rows)
- **D-07:** MinIO only — ingestion uploads to object storage, does NOT load into PostgreSQL
- **D-08:** By-dataset folder structure: `zulip-raw-messages/combined_dataset/chunk_000.csv`

### Synthetic Data Generation
- **D-09:** HuggingFace model: `mistralai/Mistral-7B-Instruct-v0.2` via Inference API
- **D-10:** Target volume: ~10K synthetic rows (representative sample; full-scale generation deferred to batch pipeline phase)
- **D-11:** Oversample minority classes (toxic/suicide) to rebalance the dataset
- **D-12:** Multi-turn thread prompts to generate realistic Zulip-style conversations
- **D-13:** Prompt-guided labeling — prompt instructs model to generate toxic or benign content; labels assigned from prompt, not post-hoc classification

### Source Tagging
- **D-14:** String enum `source` column in PostgreSQL with values like `real`, `synthetic_hf`
- **D-15:** Folder split in MinIO: `zulip-raw-messages/real/` and `zulip-raw-messages/synthetic/`

### Agent's Discretion
- Docker Compose port mappings, volume mounts, and environment variable naming
- PostgreSQL schema details for users/flags/moderation tables beyond what requirements specify
- Error handling and retry logic for HuggingFace API calls
- Synthetic data prompt template wording

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Documents
- `Idea.md` — Data architecture implementation plan: MinIO setup, ingestion pipeline, online processing, batch pipeline
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: system design, team roles, data flow, deployment architecture

### Requirements
- `.planning/REQUIREMENTS.md` — Requirements INFRA-01 through INGEST-03 for this phase, with acceptance criteria

### Course Labs
- `lecture and labs.txt` — Course lab URLs for Chameleon, MLOps, data-platform-chi, PostgreSQL, MinIO

### Dataset
- `combined_dataset.csv` — ~1.58M rows, columns: `text` (string), `is_suicide` (binary), `is_toxicity` (binary). Source: Jigsaw Toxic Comment + Suicide/Depression Detection (Reddit)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing source code — this is the first implementation phase
- `Idea.md` provides the detailed implementation plan to follow
- Course labs (data-platform-chi) provide reference Docker Compose and MinIO patterns

### Established Patterns
- Docker Compose orchestration matching course lab patterns (data-platform-chi)
- Python snake_case naming, type hints on all functions
- Logging via Python logging module (no print statements)
- Black formatting, ruff/flake8 linting

### Integration Points
- Docker Compose file lives at project root or `infra/docker/`
- PostgreSQL accessible on standard port 5432 from within Docker network
- MinIO console on port 9001 (must be exposed for course staff browsing)
- FastAPI stub endpoints: POST /messages, POST /flags (accepting synthetic traffic)
- Ingestion script: `src/data/ingest_and_expand.py`
- Synthetic generator: `src/data/synthetic_traffic_generator.py` (planned for Phase 2 traffic generation)

</code_context>

<specifics>
## Specific Ideas

- Use python-chi patterns from course labs for any Chameleon provisioning (though this phase focuses on Docker Compose, not VM provisioning)
- MinIO buckets `zulip-raw-messages` and `zulip-training-data` must be created and browsable at :9001
- Ingestion script should log progress (chunk N of M) since it processes 1.58M rows
- Synthetic data should look like realistic Zulip chat messages, not generic text

</specifics>

<deferred>
## Deferred Ideas

- Parquet conversion during ingestion — can be added in batch pipeline phase
- PostgreSQL loading of ingested data — deferred to batch pipeline or a separate load step
- Deterministic seeds for reproducible synthetic generation (QUALITY-01, ADV-01 — v2 requirements)

</deferred>

---

*Phase: 01-infrastructure-ingestion*
*Context gathered: 2026-04-03*
