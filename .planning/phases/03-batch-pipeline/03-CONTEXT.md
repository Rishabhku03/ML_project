# Phase 3: Batch Pipeline - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Batch pipeline compiles versioned training/evaluation datasets from production data without data leakage. Two-phase approach: (1) initial run compiles ingested CSV from MinIO into first training snapshot AND loads data into PostgreSQL, (2) incremental runs query PostgreSQL for new moderated messages to produce re-training snapshots. Pipeline acts as a quality gate — filters known data issues before training data export.

</domain>

<decisions>
## Implementation Decisions

### Data Source Strategy
- **D-01:** Two-phase pipeline — initial run reads CSV chunks from MinIO `zulip-raw-messages/`, incremental runs query PostgreSQL
- **D-02:** Initial run also bulk-loads CSV data into PostgreSQL `messages` table, establishing PostgreSQL as single source of truth for incremental runs
- **D-03:** Incremental runs query PostgreSQL with inner join on `moderation` table — only messages with a moderation decision are included

### Temporal Leakage Prevention
- **D-04:** Inner join `messages` with `moderation` — only export messages that have a `moderation.decided_at` timestamp
- **D-05:** Temporal filter: `WHERE messages.created_at < moderation.decided_at` — ensures model never trains on post-decision information
- **D-06:** Messages without moderation records are excluded (no decision to leak, but no training signal either)

### Training Data Format
- **D-07:** CSV format for versioned snapshots (matches existing pipeline pattern — `ingest_and_expand.py` uses CSV chunks)
- **D-08:** No Parquet conversion — keeps dependencies minimal, dataset is under 5GB threshold

### Versioned Snapshot Structure
- **D-09:** Timestamp-based version naming: `v20260403-142301/` format
- **D-10:** Single folder per version containing 3 CSVs: `train.csv`, `val.csv`, `test.csv`
- **D-11:** Upload to MinIO bucket `zulip-training-data` (bucket exists from Phase 1, currently empty)

### Stratified Split
- **D-12:** 70/15/15 train/test/validation split ratio
- **D-13:** Stratify on combined label: intersection of `is_suicide` × `is_toxicity` (4 classes: both, suicide-only, toxic-only, neither)
- **D-14:** Use scikit-learn `train_test_split` with `stratify` parameter for class-proportional splits

### Output Schema
- **D-15:** Export columns: `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`
- **D-16:** `source` tag (real/synthetic_hf) lets ML team filter by data origin
- **D-17:** `message_id` (UUID) provides traceability back to PostgreSQL for debugging

### TextCleaner Fallback
- **D-18:** For incremental PostgreSQL runs: use `cleaned_text` when non-null, run `TextCleaner.clean()` as fallback for NULL rows
- **D-19:** Import `TextCleaner` from `src/data/text_cleaner.py` (shared module from Phase 2)

### Data Quality Gate
- **D-20:** Batch pipeline filters known data quality issues BEFORE split/upload (acts as quality gate)
- **D-21:** Remove 262 `#ERROR!` duplicate rows (data pipeline artifact from DATA_ISSUES.md Issue 4)
- **D-22:** Filter texts below 10 chars (noise threshold from DATA_ISSUES.md Issue 5)
- **D-23:** Cap texts above 5,000 chars (outlier threshold from DATA_ISSUES.md Issue 5)
- **D-24:** Log quality filtering results (rows removed, reasons) for audit trail

### Label Derivation
- **D-25:** For PostgreSQL rows: derive `is_toxicity` from `messages.toxic OR messages.severe_toxic OR messages.obscene OR messages.threat OR messages.insult OR messages.identity_hate`
- **D-26:** For CSV rows: use `is_toxicity` column directly (already a single boolean in combined_dataset.csv)

### Agent's Discretion
- SQL query implementation (cursor-based vs pandas `read_sql`)
- Chunk size for PostgreSQL reads
- Error handling for MinIO upload failures
- Manifest/metadata file generation per version (optional)
- CLI argument parsing (argparse) for specifying initial vs incremental mode
- Logging format and detail level for quality gate results

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Documents
- `Idea.md` — Data architecture implementation plan: describes `compile_training_data.py` purpose, batch pipeline placement, MinIO/PostgreSQL integration
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: system design, data flow, batch pipeline role in the architecture

### Data Quality Analysis
- `data/DATA_ISSUES.md` — 7 data quality issues identified in combined_dataset.csv: #ERROR! duplicates, extreme text lengths, class imbalance, label mutual exclusivity. Quality gate decisions (D-20 through D-24) reference specific issues.

### Requirements
- `.planning/REQUIREMENTS.md` — Requirements BATCH-01 through BATCH-05 for this phase, with acceptance criteria

### Prior Phase Context
- `.planning/phases/01-infrastructure-ingestion/01-CONTEXT.md` — Decisions D-01 through D-15 (PostgreSQL schema, MinIO buckets, source tagging, synthetic data generation)
- `.planning/phases/02-real-time-processing/02-CONTEXT.md` — Decisions D-01 through D-17 (TextCleaner pipeline, cleaned_text column, middleware integration)

### Existing Code (integration points)
- `src/data/text_cleaner.py` — Shared TextCleaner pipeline class with 5 configurable steps (ftfy → markdown → URLs → emoji → PII). Reused for NULL cleaned_text fallback.
- `src/utils/config.py` — Frozen dataclass Config with env vars. Has `BUCKET_TRAINING = "zulip-training-data"` for output.
- `src/utils/minio_client.py` — MinIO client factory via `get_minio_client()`. Used for reading CSV chunks and uploading snapshots.
- `src/utils/db.py` — PostgreSQL connection helper via `get_db_connection()`. Used for querying messages + moderation.
- `docker/init_sql/00_create_tables.sql` — PostgreSQL schema: messages table (cleaned_text, toxicity booleans, is_suicide, source, created_at), moderation table (decided_at, action, confidence).

### Course Reference
- `lecture and labs.txt` — Course lab URLs for PostgreSQL, MinIO, batch pipeline patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/text_cleaner.py` — `TextCleaner` class: stateless, composable pipeline. Call `cleaner.clean(text)` for any string. Default steps cover ftfy, markdown, URLs, emoji, PII.
- `src/utils/config.py` — `config.BUCKET_TRAINING` ("zulip-training-data") — target bucket for versioned snapshots
- `src/utils/minio_client.py` — `get_minio_client()` factory — used by ingest_and_expand.py for CSV upload pattern (put_object with io.BytesIO)
- `src/utils/db.py` — `get_db_connection()` — psycopg2 connection, used by middleware for PostgreSQL writes

### Established Patterns
- Frozen dataclass for configuration (Config in config.py)
- Logging via `logging.getLogger(__name__)` per module
- CSV chunked processing: `pd.read_csv(chunksize=50_000)` + upload via MinIO client
- Module-level `__main__` entry point with argparse (from ingest_and_expand.py, synthetic_generator.py)

### Integration Points
- `src/data/compile_training_data.py` — New file to create (core of Phase 3)
- PostgreSQL `messages` table — source for incremental runs (has cleaned_text, toxicity booleans, is_suicide, source, created_at)
- PostgreSQL `moderation` table — join target for temporal leakage prevention (has decided_at)
- MinIO `zulip-raw-messages/` — source for initial run (CSV chunks from Phase 1 ingestion)
- MinIO `zulip-training-data/` — destination for versioned snapshots
- `pyproject.toml` — needs `scikit-learn` dependency added for `train_test_split`

</code_context>

<specifics>
## Specific Ideas

- Two-phase pipeline mode: `--mode initial` reads from MinIO CSVs + loads to PostgreSQL, `--mode incremental` queries PostgreSQL for new data
- Quality gate should log a summary: "Removed 262 #ERROR! duplicates, filtered 47 texts < 10 chars, capped 12 texts > 5000 chars" — useful for demo video
- Combined stratification label: create temporary column `label_combo = f"{is_suicide}_{is_toxicity}"` for sklearn stratify parameter
- Version timestamp should use UTC to avoid timezone ambiguity across team members' VMs
- Consider adding a `manifest.json` or `manifest.csv` per version with row counts, label distributions, and generation timestamp — helps ML team understand dataset composition

</specifics>

<deferred>
## Deferred Ideas

- Parquet format conversion — can be added later if ML team needs it
- Class imbalance mitigation (SMOTE, oversampling) — ML training team responsibility (Aadarsh)
- Text length normalization for leakage prevention — model-level concern, not data pipeline
- Automated quality metrics report (null rates, duplicate rates) — v2 requirement (QUALITY-01)
- Deterministic seeds for reproducible splits — v2 requirement (ADV-01)

</deferred>

---

*Phase: 03-batch-pipeline*
*Context gathered: 2026-04-04*
