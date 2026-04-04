# Phase 3: Batch Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 03-batch-pipeline
**Areas discussed:** Leakage prevention logic, Training data format, Stratified split strategy, Output schema, Data source strategy, Version folder structure, TextCleaner fallback, Data quality gate

---

## Leakage prevention logic

| Option | Description | Selected |
|--------|-------------|----------|
| Join only (messages WITH moderation) | Inner join — only export messages that have a moderation.decided_at | ✓ |
| Left join, include all | Include ALL messages from messages table, use labels directly | |

**User's choice:** Join only (messages WITH moderation)
**Notes:** Clean dataset, no leakage risk. Messages without moderation excluded.

---

## Training data format

| Option | Description | Selected |
|--------|-------------|----------|
| CSV (Recommended) | Matches existing pipeline pattern, simple, browsable | ✓ |
| Parquet | Columnar, smaller, requires pyarrow dependency | |
| Both (CSV primary) | Upload both formats, doubles storage | |

**User's choice:** CSV
**Notes:** Matches ingest_and_expand.py pattern. Dataset under 5GB — CSV is fine.

---

## Stratified split strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 80/10/10, stratify on combined label | Standard ML split, 4-class stratification | |
| 70/15/15, stratify on combined label | More evaluation data, same stratification | ✓ |
| 80/10/10, stratify on is_toxicity only | Simpler 2-class stratification | |

**User's choice:** 70/15/15, stratify on combined label
**Notes:** Better for evaluation robustness. Combined is_suicide × is_toxicity = 4 classes.

---

## Output schema

| Option | Description | Selected |
|--------|-------------|----------|
| cleaned_text + labels + source (Recommended) | Export: cleaned_text, is_suicide, is_toxicity, source | |
| cleaned_text + labels only | Most minimal export | |
| cleaned_text + labels + source + message_id | Full traceability with UUID | ✓ |

**User's choice:** cleaned_text + labels + source + message_id
**Notes:** Full traceability — ML team can cross-reference back to PostgreSQL for debugging.

---

## Data source strategy

| Option | Description | Selected |
|--------|-------------|----------|
| PostgreSQL only | Query messages + moderation directly | |
| PostgreSQL + MinIO CSVs | Read from both sources | |
| Two-phase: CSV first, then PostgreSQL incremental | Initial run from MinIO, incremental from PG | ✓ |

**User's choice:** Two-phase approach (clarified via free text)
**Notes:** Initial run: read CSV from MinIO → clean text → load to PostgreSQL → split → upload. Incremental runs: query PostgreSQL for new moderated data. PG becomes single source of truth after initial load.

---

## Version folder structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single folder with 3 CSVs | v20260403-142301/train.csv, val.csv, test.csv | ✓ |
| Split-first, version-second | train/v20260403-142301.csv, etc. | |

**User's choice:** Single folder with 3 CSVs
**Notes:** One version = one folder. ML team grabs one folder for complete dataset.

---

## TextCleaner fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Run TextCleaner on NULL rows (Recommended) | Use cleaned_text when available, TextCleaner fallback for NULLs | ✓ |
| Skip NULL rows | Only export rows with non-null cleaned_text | |

**User's choice:** Run TextCleaner on NULL rows
**Notes:** Ensures no data is lost. Batch pipeline imports TextCleaner from src/data/text_cleaner.py.

---

## Data quality gate

| Option | Description | Selected |
|--------|-------------|----------|
| Batch pipeline as quality gate (Recommended) | Filter duplicates, cap text lengths, log removals in compile_training_data.py | ✓ |
| TextCleaner extended | Add quality checks to TextCleaner | |
| Separate quality module | New src/data/quality_checker.py | |

**User's choice:** Batch pipeline as quality gate
**Notes:** TextCleaner focused on text normalization. Batch pipeline handles data curation (remove #ERROR! duplicates, filter <10 chars, cap >5000 chars). References DATA_ISSUES.md for specific issues.

---

## Agent's Discretion

Areas left to implementation:
- SQL query implementation (cursor-based vs pandas read_sql)
- Chunk size for PostgreSQL reads
- Error handling for MinIO upload failures
- CLI argument parsing approach
- Manifest/metadata file per version
- Logging format for quality gate results

---

## Deferred Ideas

- Parquet format — future addition
- Class imbalance mitigation (SMOTE) — ML training team responsibility
- Text length normalization — model-level concern
- Quality metrics report — v2 requirement
- Deterministic seeds — v2 requirement
