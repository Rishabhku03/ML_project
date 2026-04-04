# Phase 3: Batch Pipeline - Research

**Researched:** 2026-04-04
**Domain:** Data pipeline — stratified train/test split, temporal leakage prevention, versioned data snapshots
**Confidence:** HIGH

## Summary

Phase 3 builds `src/data/compile_training_data.py` — a batch pipeline that compiles versioned training/evaluation datasets from production data. Two modes: `--mode initial` reads CSV chunks from MinIO and bulk-loads into PostgreSQL; `--mode incremental` queries PostgreSQL for new moderated messages. The pipeline applies quality gates (remove #ERROR! duplicates, filter extreme text lengths), prevents temporal leakage (inner join with `WHERE created_at < decided_at`), stratified 70/15/15 splits using scikit-learn, and uploads versioned snapshots (train.csv, val.csv, test.csv) to MinIO.

All dependencies except scikit-learn are already installed. The project follows established patterns: frozen dataclass Config, `logging.getLogger(__name__)`, CSV chunked processing with MinIO upload, argparse CLI entry points.

**Primary recommendation:** Use scikit-learn `train_test_split` with `stratify` parameter for class-proportional splits, pandas `read_sql` for PostgreSQL queries, and the existing MinIO upload pattern from `ingest_and_expand.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Two-phase pipeline — initial run reads CSV chunks from MinIO `zulip-raw-messages/`, incremental runs query PostgreSQL
- **D-02:** Initial run also bulk-loads CSV data into PostgreSQL `messages` table, establishing PostgreSQL as single source of truth for incremental runs
- **D-03:** Incremental runs query PostgreSQL with inner join on `moderation` table — only messages with a moderation decision are included
- **D-04:** Inner join `messages` with `moderation` — only export messages that have a `moderation.decided_at` timestamp
- **D-05:** Temporal filter: `WHERE messages.created_at < moderation.decided_at` — ensures model never trains on post-decision information
- **D-06:** Messages without moderation records are excluded (no decision to leak, but no training signal either)
- **D-07:** CSV format for versioned snapshots (matches existing pipeline pattern — `ingest_and_expand.py` uses CSV chunks)
- **D-08:** No Parquet conversion — keeps dependencies minimal, dataset is under 5GB threshold
- **D-09:** Timestamp-based version naming: `v20260403-142301/` format
- **D-10:** Single folder per version containing 3 CSVs: `train.csv`, `val.csv`, `test.csv`
- **D-11:** Upload to MinIO bucket `zulip-training-data` (bucket exists from Phase 1, currently empty)
- **D-12:** 70/15/15 train/test/validation split ratio
- **D-13:** Stratify on combined label: intersection of `is_suicide` × `is_toxicity` (4 classes: both, suicide-only, toxic-only, neither)
- **D-14:** Use scikit-learn `train_test_split` with `stratify` parameter for class-proportional splits
- **D-15:** Export columns: `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`
- **D-16:** `source` tag (real/synthetic_hf) lets ML team filter by data origin
- **D-17:** `message_id` (UUID) provides traceability back to PostgreSQL for debugging
- **D-18:** For incremental PostgreSQL runs: use `cleaned_text` when non-null, run `TextCleaner.clean()` as fallback for NULL rows
- **D-19:** Import `TextCleaner` from `src/data/text_cleaner.py` (shared module from Phase 2)
- **D-20:** Batch pipeline filters known data quality issues BEFORE split/upload (acts as quality gate)
- **D-21:** Remove 262 `#ERROR!` duplicate rows (data pipeline artifact from DATA_ISSUES.md Issue 4)
- **D-22:** Filter texts below 10 chars (noise threshold from DATA_ISSUES.md Issue 5)
- **D-23:** Cap texts above 5,000 chars (outlier threshold from DATA_ISSUES.md Issue 5)
- **D-24:** Log quality filtering results (rows removed, reasons) for audit trail
- **D-25:** For PostgreSQL rows: derive `is_toxicity` from `messages.toxic OR messages.severe_toxic OR messages.obscene OR messages.threat OR messages.insult OR messages.identity_hate`
- **D-26:** For CSV rows: use `is_toxicity` column directly (already a single boolean in combined_dataset.csv)

### Agent's Discretion
- SQL query implementation (cursor-based vs pandas `read_sql`)
- Chunk size for PostgreSQL reads
- Error handling for MinIO upload failures
- Manifest/metadata file generation per version (optional)
- CLI argument parsing (argparse) for specifying initial vs incremental mode
- Logging format and detail level for quality gate results

### Deferred Ideas (OUT OF SCOPE)
- Parquet format conversion — can be added later if ML team needs it
- Class imbalance mitigation (SMOTE, oversampling) — ML training team responsibility (Aadarsh)
- Text length normalization for leakage prevention — model-level concern, not data pipeline
- Automated quality metrics report (null rates, duplicate rates) — v2 requirement (QUALITY-01)
- Deterministic seeds for reproducible splits — v2 requirement (ADV-01)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BATCH-01 | Batch pipeline compiles versioned training/evaluation datasets from PostgreSQL "production" data | Two-phase pipeline: initial CSV from MinIO + bulk-load to PostgreSQL, incremental queries PostgreSQL. See Standard Stack and Architecture Patterns. |
| BATCH-02 | Temporal data leakage prevention (WHERE created_at < decided_at on all training queries) | Inner join messages with moderation table, filter by `messages.created_at < moderation.decided_at`. See Architecture Patterns — Temporal Leakage Prevention Query. |
| BATCH-03 | Versioned snapshots in MinIO (immutable, timestamp-tagged: v20260403-142301/) | UTC timestamp naming, upload via `put_object` with `io.BytesIO`. See Architecture Patterns — Versioned Snapshot Upload. |
| BATCH-04 | Post-submission metadata stripped before training data export | Output schema exports only 5 columns: `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`. All PostgreSQL metadata (user_id, timestamps, moderation details) excluded. |
| BATCH-05 | Dataset split into train/test/validation sets (stratified by is_suicide and is_toxicity labels) | scikit-learn `train_test_split` with `stratify` parameter on combined 4-class label. See Standard Stack and Code Examples. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.8.0 | Stratified train/test/validation split | Industry standard for ML data splitting; `train_test_split` with `stratify` param handles class-proportional splits. Verified available via pip. |
| pandas | ≥3.0.0 | CSV reading, DataFrame operations, SQL queries | Already installed; used throughout project for chunked CSV processing. `pd.read_sql()` for PostgreSQL queries. |
| psycopg2-binary | ≥2.9.0 | PostgreSQL connection | Already installed; used by `src/utils/db.py` `get_db_connection()` helper. |
| minio | ≥7.2.0 | MinIO object storage client | Already installed; used by `src/utils/minio_client.py` `get_minio_client()` factory. |
| ftfy | ≥6.3.1 | Unicode normalization | Already installed; used by `TextCleaner` pipeline for cleaning fallback. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI argument parsing | Always — `--mode initial|incremental` per established project pattern |
| logging | stdlib | Structured logging | Always — `logging.getLogger(__name__)` per project convention |
| io | stdlib | BytesIO for MinIO upload | MinIO upload — `io.BytesIO(csv_bytes.encode('utf-8'))` |
| datetime | stdlib | UTC timestamp for version naming | Version naming — `datetime.utcnow().strftime('v%Y%m%d-%H%M%S')` |
| uuid | stdlib | Traceability message_id | Output schema — already in CSV data |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas `read_sql` | psycopg2 cursor fetchall + manual DataFrame | `read_sql` is simpler, returns DataFrame directly; cursor approach only needed for memory-critical streaming (not needed here — 391K rows fits in memory) |
| sklearn `train_test_split` × 2 | Manual index-based split | sklearn handles stratification, edge cases, random state; manual split risks imbalanced classes in small test/val sets |
| CSV output | Parquet output | CSV matches existing pipeline pattern (D-07); Parquet deferred per D-08 |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | `now(timezone.utc)` is preferred in Python 3.12+ but `utcnow()` works fine for version strings; either produces valid UTC timestamps |

**Installation:**
```bash
pip install scikit-learn>=1.8.0
```

**Version verification:** scikit-learn 1.8.0 verified available via `pip3 index versions scikit-learn` (2026-04-04). All other dependencies already installed per `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure

```
src/data/
├── compile_training_data.py   # NEW — batch pipeline (Phase 3)
├── text_cleaner.py            # EXISTING — TextCleaner for NULL cleaned_text fallback
├── ingest_and_expand.py       # EXISTING — pattern reference for CLI/MinIO/chunked CSV
└── ...
```

### Pattern 1: Two-Phase Pipeline Mode

**What:** Single script with `--mode initial` and `--mode incremental` flags. Initial mode reads CSV from MinIO, cleans, loads into PostgreSQL, then queries PostgreSQL for compiled dataset. Incremental mode skips CSV read, queries PostgreSQL directly for new moderated messages.

**When to use:** When the same pipeline has fundamentally different data sources depending on whether it's the first run or a subsequent run.

**Example:**
```python
# Source: Established pattern from ingest_and_expand.py + synthetic_traffic_generator.py
import argparse
import logging

logger = logging.getLogger(__name__)

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Batch training data compiler")
    parser.add_argument(
        "--mode",
        choices=["initial", "incremental"],
        default="incremental",
        help="Pipeline mode: 'initial' reads CSV from MinIO, 'incremental' queries PostgreSQL",
    )
    args = parser.parse_args()

    if args.mode == "initial":
        compile_initial()
    else:
        compile_incremental()
```

### Pattern 2: Quality Gate Before Split

**What:** Apply data quality filters to the full DataFrame BEFORE performing train/test/validation splits. This ensures no corrupted data leaks into any split.

**When to use:** When the dataset has known quality issues (duplicates, extreme values, artifacts) that must be excluded from all splits.

**Example:**
```python
def apply_quality_gate(df: pd.DataFrame) -> pd.DataFrame:
    """Filter known data quality issues before split (D-20 through D-24)."""
    initial_count = len(df)

    # Remove #ERROR! duplicates (DATA_ISSUES.md Issue 4)
    df = df[~df["cleaned_text"].str.contains("#ERROR!", na=False)]

    # Filter texts below 10 chars (noise threshold)
    df = df[df["cleaned_text"].str.len() >= 10]

    # Cap texts above 5000 chars (outlier threshold)
    df["cleaned_text"] = df["cleaned_text"].str[:5000]

    removed = initial_count - len(df)
    logger.info("Quality gate: removed %d rows (%.2f%%)", removed, removed / initial_count * 100)
    return df
```

### Pattern 3: Two-Step Stratified Split (70/15/15)

**What:** Use `train_test_split` twice with the `stratify` parameter. First split: 85% (train+val) / 15% (test). Second split on the 85% portion: 70/15 (train/val). This preserves class proportions across all three sets.

**When to use:** When you need exactly 3 splits (train/test/validation) with class-proportional representation, especially with imbalanced labels.

**Example:**
```python
# Source: scikit-learn docs — train_test_split with stratify
from sklearn.model_selection import train_test_split

# Create combined stratification label (4 classes per D-13)
df["label_combo"] = df["is_suicide"].astype(str) + "_" + df["is_toxicity"].astype(str)

# Step 1: 85% train+val, 15% test
train_val_df, test_df = train_test_split(
    df, test_size=0.15, stratify=df["label_combo"], random_state=42
)

# Step 2: split 85% into 70% train and 15% val
# val_size = 0.15 / 0.85 ≈ 0.1765
train_df, val_df = train_test_split(
    train_val_df, test_size=0.1765, stratify=train_val_df["label_combo"], random_state=42
)
```

**Pitfall:** The second `test_size` is NOT 0.15 — it's `0.15 / 0.85 ≈ 0.1765` to get 15% of the ORIGINAL dataset. Using 0.15 again would give ~12.75% of the original.

### Pattern 4: Versioned Snapshot Upload to MinIO

**What:** Generate a UTC timestamp folder name, create 3 CSVs (train/val/test), upload each to MinIO under the versioned path.

**When to use:** Producing immutable, timestamped data artifacts for downstream consumers.

**Example:**
```python
# Source: Adapted from ingest_and_upload MinIO pattern
import io
from datetime import datetime, timezone

def upload_snapshot(
    client, bucket: str, train_df, val_df, test_df
) -> str:
    """Upload versioned training data snapshot to MinIO."""
    version = datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S")

    splits = {"train": train_df, "val": val_df, "test": test_df}
    for split_name, split_df in splits.items():
        csv_bytes = split_df.to_csv(index=False).encode("utf-8")
        object_name = f"{version}/{split_name}.csv"

        client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=io.BytesIO(csv_bytes),
            length=len(csv_bytes),
            content_type="text/csv",
        )
        logger.info("Uploaded %s (%d rows) to %s/%s", split_name, len(split_df), bucket, object_name)

    return version
```

### Pattern 5: Incremental PostgreSQL Query with Temporal Leakage Prevention

**What:** Inner join `messages` with `moderation` on `message_id`, filtering only rows where `created_at < decided_at`. This ensures no post-decision information leaks into training data.

**When to use:** When querying production data for training — decisions must happen AFTER the message was created.

**Example:**
```python
INCREMENTAL_QUERY = """
    SELECT
        m.id AS message_id,
        COALESCE(m.cleaned_text, m.text) AS cleaned_text,
        m.is_suicide,
        m.toxic OR m.severe_toxic OR m.obscene OR m.threat
            OR m.insult OR m.identity_hate AS is_toxicity,
        m.source
    FROM messages m
    INNER JOIN moderation mod ON m.id = mod.message_id
    WHERE m.created_at < mod.decided_at
      AND (mod.decided_at > %s OR %s IS NULL)
    ORDER BY m.created_at
"""

def query_incremental(conn, last_run_timestamp=None):
    """Query PostgreSQL for new moderated messages with temporal leakage prevention."""
    df = pd.read_sql(INCREMENTAL_QUERY, conn, params=[last_run_timestamp, last_run_timestamp])
    return df
```

**Note:** The `COALESCE(m.cleaned_text, m.text)` handles the fallback for D-18 — use cleaned_text when available, raw text as fallback. TextCleaner is only needed if BOTH are null (unlikely but defensive).

### Anti-Patterns to Avoid

- **Splitting before quality filtering:** Quality gate must run on the FULL dataset before splits. Filtering after split risks different quality thresholds across splits.
- **Using `random_state=None`:** Without a fixed random state, splits are non-reproducible. Use `random_state=42` for deterministic splits (even though ADV-01 is deferred, it's free).
- **Stratifying on individual labels separately:** Must use the COMBINED 4-class label (`is_suicide × is_toxicity`) to preserve the joint distribution. Stratifying on each independently doesn't guarantee proportional representation of the intersection.
- **Forgetting the combined label column in output:** The `label_combo` column is temporary — drop it before export. Output should only have the 5 columns from D-15.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stratified train/test split | Custom random sampling with class tracking | scikit-learn `train_test_split(stratify=...)` | Handles edge cases (very small classes, rounding), battle-tested, one-line call |
| Text cleaning for NULL cleaned_text | Inline regex/text processing | `TextCleaner` from `src/data/text_cleaner.py` | Already implements 5-step pipeline (ftfy → markdown → URLs → emoji → PII); reusing avoids duplication |
| MinIO object upload | Custom HTTP requests to MinIO API | `client.put_object()` from `minio` Python SDK | Handles multipart, retries, content-type; already used by `ingest_and_expand.py` |
| PostgreSQL connection management | Raw `psycopg2.connect()` with manual error handling | `get_db_connection()` from `src/utils/db.py` | Consistent connection string from Config, logging included |
| CSV reading | Manual file I/O with csv module | `pd.read_csv()` / `pd.read_sql()` | Pandas handles encoding, type inference, null values; consistent with rest of codebase |
| Timestamp generation | `time.time()` or custom formatting | `datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S")` | UTC avoids timezone ambiguity, format matches D-09 naming convention |

**Key insight:** The project already has reusable utilities for every external integration (MinIO, PostgreSQL, text cleaning). The batch pipeline is primarily orchestration — connecting existing pieces with quality filtering and splitting logic.

## Common Pitfalls

### Pitfall 1: Incorrect Second Split Ratio

**What goes wrong:** Using `test_size=0.15` in the second `train_test_split` call, resulting in 15% of the 85% remainder (~12.75% of original) instead of 15% of the original dataset.

**Why it happens:** The second split operates on the 85% train+val portion, not the original 100%. The ratio must be recalculated.

**How to avoid:** Use `test_size=0.15/0.85 ≈ 0.1765` in the second split. Or: first split 70%/30%, then split the 30% evenly into test/val (each 15% of original).

**Warning signs:** Final split sizes don't sum to 100%, or test+val ≠ 30% of original.

### Pitfall 2: Stratify Fails with Very Small Classes

**What goes wrong:** `train_test_split` raises `ValueError: The least populated class has only 1 member` when a stratification class has too few samples for the requested split.

**Why it happens:** The combined 4-class label (is_suicide × is_toxicity) creates classes where "both=1" may have 0 rows (DATA_ISSUES.md Issue 2 confirms mutual exclusivity — 0 rows where is_suicide=1 AND is_toxicity=1). This means effectively 3 classes, not 4.

**How to avoid:** Check the combined label distribution before splitting. If a class has < 3 samples, either skip stratification for that class or add a minimum sample check. Since we know from DATA_ISSUES.md that the "both" class has 0 rows, the effective stratification is on 3 classes.

**Warning signs:** `ValueError` from sklearn, or class distribution is wildly different across splits.

### Pitfall 3: Memory Exhaustion on Initial Load

**What goes wrong:** Loading all 391K CSV rows into memory at once causes OOM on the 16GB VM.

**Why it happens:** The CSV is ~235MB on disk but pandas DataFrames can use 3-5× that in memory with string columns.

**How to avoid:** For the initial mode, process CSV in chunks (50K rows, matching `ingest_and_expand.py` CHUNK_SIZE), accumulate into PostgreSQL, then query back. Or: load the full CSV in one shot — 391K rows × 3 columns at ~235MB should fit comfortably in 16GB RAM with pandas overhead (~1-2GB). The `ingest_and_expand.py` uses chunks because it was designed for the assumed 1.58M row dataset.

**Warning signs:** RSS memory climbing above 10GB during load, system swapping.

### Pitfall 4: Timezone-Aware vs Naive Datetime Comparison

**What goes wrong:** PostgreSQL `TIMESTAMPTZ` returns timezone-aware datetimes, but Python `datetime.utcnow()` is naive. Comparing them causes errors or incorrect filtering in the temporal leakage query.

**Why it happens:** Mixing timezone-aware and naive datetimes in Python raises `TypeError` in Python 3.12+.

**How to avoid:** Use `datetime.now(timezone.utc)` (timezone-aware) instead of `datetime.utcnow()` (naive). For the incremental query timestamp parameter, pass a timezone-aware datetime.

**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes`.

### Pitfall 5: cleaned_text Column NULL Handling

**What goes wrong:** Assuming all rows have `cleaned_text` populated (from Phase 2 online processing). Initial CSV data has no `cleaned_text` column at all (CSV schema: text, is_suicide, is_toxicity).

**Why it happens:** The initial mode reads from the raw CSV which only has `text`, `is_suicide`, `is_toxicity`. The `cleaned_text` column only exists in PostgreSQL after the online processing middleware populates it.

**How to avoid:** For initial mode: run TextCleaner on all rows to generate `cleaned_text`. For incremental mode: use `COALESCE(m.cleaned_text, m.text)` in SQL, then run TextCleaner on the fallback raw text.

**Warning signs:** NaN values in `cleaned_text` column, TextCleaner receiving None instead of str.

## Code Examples

Verified patterns from project codebase and official sources:

### Reading CSV Chunks from MinIO (existing pattern)

```python
# Source: src/data/ingest_and_expand.py (lines 48-53)
import io
import pandas as pd
from src.utils.minio_client import get_minio_client

client = get_minio_client()

# List all chunk objects in the raw bucket
objects = client.list_objects("zulip-raw-messages", prefix="real/combined_dataset/", recursive=True)

chunks = []
for obj in objects:
    response = client.get_object("zulip-raw-messages", obj.object_name)
    chunk_df = pd.read_csv(io.BytesIO(response.read()))
    chunks.append(chunk_df)
    response.close()
    response.release_conn()

df = pd.concat(chunks, ignore_index=True)
```

### Stratified Two-Step Split (70/15/15)

```python
# Source: scikit-learn docs — train_test_split
from sklearn.model_selection import train_test_split

def stratified_split(df: pd.DataFrame, random_state: int = 42):
    """Split DataFrame into train (70%), val (15%), test (15%), stratified by label_combo."""
    # Step 1: split off test set (15%)
    train_val, test = train_test_split(
        df, test_size=0.15, stratify=df["label_combo"], random_state=random_state
    )
    # Step 2: split train+val into train (70%) and val (15%)
    # val_size = 0.15 / 0.85 ≈ 0.1765
    train, val = train_test_split(
        train_val, test_size=0.15 / 0.85, stratify=train_val["label_combo"], random_state=random_state
    )
    return train, val, test
```

### PostgreSQL Query for Incremental Mode

```python
# Source: src/utils/db.py (connection helper) + project SQL schema
import pandas as pd
from src.utils.db import get_db_connection

INCREMENTAL_QUERY = """
    SELECT
        m.id AS message_id,
        COALESCE(m.cleaned_text, m.text) AS cleaned_text,
        m.is_suicide,
        (m.toxic OR m.severe_toxic OR m.obscene OR m.threat
            OR m.insult OR m.identity_hate) AS is_toxicity,
        m.source
    FROM messages m
    INNER JOIN moderation mod ON m.id = mod.message_id
    WHERE m.created_at < mod.decided_at
    ORDER BY m.created_at
"""

conn = get_db_connection()
df = pd.read_sql(INCREMENTAL_QUERY, conn)
conn.close()
```

### MinIO Upload (existing pattern)

```python
# Source: src/data/ingest_and_expand.py (lines 56-66)
import io
from src.utils.minio_client import get_minio_client
from src.utils.config import config

client = get_minio_client()

csv_bytes = df.to_csv(index=False).encode("utf-8")
client.put_object(
    bucket_name=config.BUCKET_TRAINING,
    object_name=f"{version}/train.csv",
    data=io.BytesIO(csv_bytes),
    length=len(csv_bytes),
    content_type="text/csv",
)
```

### TextCleaner Fallback for NULL cleaned_text

```python
# Source: src/data/text_cleaner.py (TextCleaner class)
from src.data.text_cleaner import TextCleaner

cleaner = TextCleaner()

def ensure_cleaned_text(row):
    """Use cleaned_text if available, fall back to TextCleaner on raw text."""
    if pd.notna(row.get("cleaned_text")) and row["cleaned_text"]:
        return row["cleaned_text"]
    return cleaner.clean(str(row.get("text", "")))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual train/test split with numpy random | scikit-learn `train_test_split` with `stratify` | sklearn 0.17+ (2015) | Handles class-proportional splits in one call |
| `datetime.utcnow()` (naive) | `datetime.now(timezone.utc)` (aware) | Python 3.12 deprecation | Avoids timezone comparison errors |
| psycopg2 cursor iteration | pandas `read_sql` | pandas 0.14+ | Returns DataFrame directly, handles type inference |

**Deprecated/outdated:**
- `datetime.utcnow()`: Deprecated in Python 3.12, emits `DeprecationWarning`. Use `datetime.now(timezone.utc)` instead.
- `pd.read_csv(chunksize=...)` for datasets that fit in memory: Only needed for 1M+ row datasets. At 391K rows, full load is fine.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scikit-learn | Stratified split (D-14) | ✗ | — | pip install scikit-learn>=1.8.0 |
| pandas | CSV/SQL operations | ✓ | ≥3.0.0 | — |
| psycopg2-binary | PostgreSQL queries | ✓ | ≥2.9.0 | — |
| minio | MinIO upload/download | ✓ | ≥7.2.0 | — |
| ftfy | TextCleaner fallback | ✓ | ≥6.3.1 | — |
| PostgreSQL | Data source for incremental mode | ✓ | — (Docker) | — |
| MinIO | Data source/sink | ✓ | — (Docker) | — |

**Missing dependencies with no fallback:**
- scikit-learn: Must be installed (`pip install scikit-learn>=1.8.0`) and added to `pyproject.toml` dependencies

**Missing dependencies with fallback:**
- None — all other dependencies are installed

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.0.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_compile_training_data.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BATCH-01 | Initial mode: CSV from MinIO → clean → PostgreSQL → versioned snapshot | integration | `pytest tests/test_compile_training_data.py::test_initial_mode -x` | ❌ Wave 0 |
| BATCH-01 | Incremental mode: PostgreSQL query → versioned snapshot | integration | `pytest tests/test_compile_training_data.py::test_incremental_mode -x` | ❌ Wave 0 |
| BATCH-02 | Temporal leakage: only messages with `created_at < decided_at` included | unit | `pytest tests/test_compile_training_data.py::test_temporal_leakage_filter -x` | ❌ Wave 0 |
| BATCH-03 | Versioned snapshot uploaded to MinIO with correct folder structure | integration | `pytest tests/test_compile_training_data.py::test_snapshot_upload -x` | ❌ Wave 0 |
| BATCH-04 | Output contains only 5 columns (cleaned_text, is_suicide, is_toxicity, source, message_id) | unit | `pytest tests/test_compile_training_data.py::test_output_schema -x` | ❌ Wave 0 |
| BATCH-05 | Stratified split preserves class proportions across train/val/test | unit | `pytest tests/test_compile_training_data.py::test_stratified_split -x` | ❌ Wave 0 |
| D-20/24 | Quality gate removes #ERROR!, filters < 10 chars, caps > 5000 chars | unit | `pytest tests/test_compile_training_data.py::test_quality_gate -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_compile_training_data.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_compile_training_data.py` — covers BATCH-01 through BATCH-05
- [ ] `scikit-learn>=1.8.0` added to `pyproject.toml` dependencies
- [ ] Test fixtures: sample DataFrames mimicking CSV schema (text, is_suicide, is_toxicity) and PostgreSQL schema (with cleaned_text, toxicity booleans, moderation join)

## Open Questions

1. **Initial mode PostgreSQL bulk load strategy**
   - What we know: CSV has 391,645 rows, 3 columns (text, is_suicide, is_toxicity). PostgreSQL messages table has 12 columns including UUID user_id, toxicity booleans, timestamps.
   - What's unclear: How to map the 3-column CSV to the 12-column messages table. Need a synthetic user_id, need to split `is_toxicity` into individual booleans (toxic, severe_toxic, etc.), need to populate `source` column.
   - Recommendation: Create a default bulk-load user, split `is_toxicity` into all-true or all-false for the 6 toxicity columns (since we don't have per-column breakdowns in the CSV), set `source='real'` to match the CSV's origin. This is a design decision that should be clarified before implementation.

2. **Handling the "both=1" class (is_suicide=1 AND is_toxicity=1)**
   - What we know: DATA_ISSUES.md Issue 2 confirms 0 rows have both labels = 1 (mutual exclusivity).
   - What's unclear: Whether the stratification should use 3 classes (not 4) since one class is empty, or if future data might populate it.
   - Recommendation: Use 4-class label for stratification but handle the empty class gracefully — check label counts before splitting, fall back to 3 classes if one is empty.

## Sources

### Primary (HIGH confidence)
- `src/data/ingest_and_expand.py` — Established patterns: CSV chunked processing, MinIO upload, argparse CLI, logging
- `src/utils/config.py` — Config with `BUCKET_TRAINING`, `DATABASE_URL`
- `src/utils/minio_client.py` — `get_minio_client()` factory
- `src/utils/db.py` — `get_db_connection()` helper
- `src/data/text_cleaner.py` — `TextCleaner` pipeline class
- `docker/init_sql/00_create_tables.sql` — PostgreSQL schema (messages, moderation tables)
- `data/DATA_ISSUES.md` — Data quality issues #4 (262 #ERROR! duplicates), #5 (extreme text lengths)
- scikit-learn docs — `train_test_split` with `stratify` parameter

### Secondary (MEDIUM confidence)
- `pyproject.toml` — Current dependencies (no scikit-learn yet)
- pip registry — scikit-learn 1.8.0 available (verified 2026-04-04)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified, versions confirmed
- Architecture: HIGH — established patterns from existing codebase, sklearn API well-documented
- Pitfalls: HIGH — identified from code analysis, sklearn docs, and DATA_ISSUES.md

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days — stable stack, no fast-moving dependencies)

---

## Deep Dive: Implementation Patterns & Class Imbalance

**Investigated:** 2026-04-04
**Focus:** Two-step split validation, stratify edge cases, class imbalance handling, temporal leakage subtleties

### Two-Step Stratified Split: Validation & Alternatives

**Current approach (Pattern 3):** Two `train_test_split` calls — first 85/15, then 82.35/17.65 on the 85% portion.

**Validation:** The approach is correct. Verified against scikit-learn 1.8.0 docs — `train_test_split` with `stratify` parameter delegates to `StratifiedShuffleSplit` internally. The two-call pattern is the standard community approach for 3-way splits.

**Edge case: Second `test_size` calculation**
The second call uses `test_size=0.15/0.85 ≈ 0.1765`, NOT `0.15`. Using `0.15` again would give:
- Step 2 val: 15% × 85% = 12.75% of original (WRONG — should be 15%)
- Total: 70% train + 12.75% val + 15% test = 97.75% (missing 2.25%!)

**Alternative approaches considered:**

| Approach | Step 1 | Step 2 | Complexity | Recommendation |
|----------|--------|--------|------------|----------------|
| **A: 70/30 then 50/50** (RECOMMENDED) | `test_size=0.30` | `test_size=0.50` on 30% | Simplest — both splits use clean ratios | **Use this** — eliminates the `0.15/0.85` calculation error risk |
| B: 85/15 then 17.65/82.35 | `test_size=0.15` | `test_size=0.15/0.85` | Error-prone ratio | Current plan — works but fragile |
| C: StratifiedShuffleSplit explicit | `n_test=58747` | `n_test=58747` on remainder | Verbose, explicit sizes | Overkill for this use case |

**Recommended change:** Use Approach A — split 70/30 first, then split the 30% evenly (50/50) into val/test. Both ratios are clean integers, no division required, impossible to get wrong.

```python
# Recommended: 70/30 then 50/50
train_df, temp_df = train_test_split(
    df, test_size=0.30, stratify=df["label_combo"], random_state=42
)
val_df, test_df = train_test_split(
    temp_df, test_size=0.50, stratify=temp_df["label_combo"], random_state=42
)
# Result: 70% train, 15% val, 15% test — same as current plan, cleaner math
```

**Confidence:** HIGH — verified against sklearn docs, simpler than current approach

### Stratify Edge Cases & Safe Minimums

**How `train_test_split(stratify=...)` works internally:**
- Calls `StratifiedShuffleSplit` under the hood
- For each class `k`, allocates `round(test_size × n_k)` samples to the test set
- Error condition: if `round(test_size × n_k) < 1` for any class → `ValueError: The least populated class has only N member(s)`

**Minimum class size formula:**
- For `test_size=t`: minimum class size = `ceil(1/t)`
- `test_size=0.15` → minimum 7 samples per class
- `test_size=0.30` → minimum 4 samples per class
- `test_size=0.50` → minimum 2 samples per class

**Our dataset's class distribution (4-class combined label):**

| Label | Description | Count | % | Safe for 0.30? | Safe for 0.50? |
|-------|-------------|-------|---|----------------|----------------|
| `1_0` | Suicide only | ~274,152 | 70.0% | ✅ (274152 >> 4) | ✅ |
| `0_0` | Neither | ~101,827 | 26.0% | ✅ | ✅ |
| `0_1` | Toxic only | ~15,666 | 4.0% | ✅ (15666 >> 4) | ✅ |
| `1_1` | Both | 0 | 0.0% | ❌ EMPTY CLASS | ❌ EMPTY CLASS |

**Critical finding:** The `1_1` (both=1) class has 0 samples (DATA_ISSUES.md Issue 2 — mutual exclusivity). Passing a 4-class label with an empty class to `stratify=` will raise `ValueError`.

**Resolution — 3 options:**

1. **Drop empty class before split (RECOMMENDED):** Filter out the `1_1` class (0 rows anyway), stratify on the 3 populated classes. Simple, correct, no edge cases.
   ```python
   # Filter to only populated classes
   df = df[df["label_combo"] != "1_1"]
   # Or: use only 3-class stratification directly
   df["label_combo"] = df["is_suicide"].astype(str) + "_" + df["is_toxicity"].astype(str)
   label_counts = df["label_combo"].value_counts()
   populated_classes = label_counts[label_counts > 0].index
   df = df[df["label_combo"].isin(populated_classes)]
   ```

2. **Check before split:** Count classes, if any has 0, remove from stratify label. More defensive but adds code.

3. **Don't create `1_1` labels:** Since we know labels are mutually exclusive, construct the label to only produce 3 classes.

**Recommendation:** Option 1 — filter empty classes before stratification. The planner should add a pre-split check that logs class distribution and drops empty classes.

**Confidence:** HIGH — verified against sklearn source behavior, DATA_ISSUES.md confirms 0 rows for `1_1`

### Class Imbalance: Data Pipeline vs Training Layer

**Class imbalance ratios in our dataset:**
- Toxicity: 23:1 ratio (4% toxic vs 96% non-toxic) — SEVERE
- Suicide: 2.3:1 ratio (70% suicide vs 30% non-suicide) — MODERATE

**Technique comparison:**

| Technique | What It Does | Data Pipeline? | Why Not |
|-----------|-------------|----------------|---------|
| **SMOTE** | Generates synthetic minority samples via interpolation | ❌ NO | Requires feature vectors (embeddings), not raw text. Generates nonsensical text. Adds `imblearn` dependency. MUST be train-only (leakage if before split). |
| **Random Oversampling** | Duplicates minority class samples | ❌ NO | Creates exact duplicates. Causes overfitting. MUST be train-only (duplicates in test = inflated metrics). |
| **Random Undersampling** | Removes majority class samples | ❌ NO | For 23:1 ratio: discards 96% of data. Destroys information. MUST be train-only. |
| **class_weight** | Adjusts loss function weights | ❌ NO (training) | Pure training-time concern. `sklearn: class_weight="balanced"`, PyTorch: weight tensor to loss function. |
| **Stratified Split** | Preserves proportions in each split | ✅ YES (already planned) | Does NOT fix imbalance, but ensures representative splits. Already D-13/D-14. |

**Key insight:** ALL resampling techniques modify the data distribution. If applied BEFORE split → data leakage (test set contains synthetic/duplicated samples). If applied AFTER split → belongs in the training loop, not the data pipeline.

**What the data pipeline SHOULD do:**
1. Perform stratified splits (already planned) ✅
2. Log class distribution per split for visibility ✅
3. Document imbalance ratios in output metadata (optional enhancement)

**What the data pipeline SHOULD NOT do:**
1. Apply SMOTE (needs embeddings, creates leakage)
2. Apply oversampling (creates duplicates, leakage risk)
3. Apply undersampling (destroys data)
4. Compute class weights (training-time only)

**The stratified split is the CORRECT data-pipeline-level response to class imbalance. Everything else is training-layer responsibility (Aadarsh's scope per D-56 in CONTEXT.md).**

**Confidence:** HIGH — clear separation of concerns, verified against sklearn/imblearn documentation

### Temporal Leakage: Subtle Paths Beyond `created_at < decided_at`

The primary temporal leakage filter (`WHERE created_at < decided_at`) is correctly implemented. However, 5 additional subtle leakage paths exist:

| # | Path | Risk | Confidence | Action |
|---|------|------|------------|--------|
| 1 | **Moderation updates after initial decision** — admin passes message at T1, reconsiders and flags at T2 | MEDIUM | MEDIUM | Use LATEST moderation record per message_id, or accept single-decision assumption |
| 2 | **Text modification after creation** — Zulip allows message edits; cleaned_text may reflect edited version, not the version the moderator saw | LOW | LOW | Accept as acceptable noise; edits are rare in practice |
| 3 | **Source column contamination** — synthetic data generated after real moderation may inadvertently mirror moderated patterns | LOW | MEDIUM | Synthetic data is generated from original CSV (Phase 1), not from moderated messages — already safe |
| 4 | **Incremental pipeline window** — between runs, messages may be re-moderated | LOW | LOW | COALESCE(cleaned_text, text) handles text version; new decisions only adds, doesn't re-label |
| 5 | **Test/val temporal proximity** — random split puts temporally adjacent messages in different splits | LOW | LOW | Acceptable for course project; time-series split deferred |

**Recommendation:** The current `WHERE created_at < decided_at` filter handles the PRIMARY leakage path. The subtle paths (1-5) are real but have LOW to MEDIUM impact for this project scope. Document them in implementation comments for the ML team to be aware of.

**Specific action for implementation:** Add a comment in the SQL query explaining WHY the temporal filter exists:
```sql
-- Temporal leakage prevention: only train on information available BEFORE the moderation decision.
-- This ensures the model cannot learn from post-decision message content or edits.
WHERE m.created_at < mod.decided_at
```

**Confidence:** MEDIUM — leakage paths are real but impact assessment is based on assumptions about Zulip behavior that would need production validation

### `datetime.utcnow()` Deprecation: Confirmed

**Verified on this system:** Python 3.12.3 emits `DeprecationWarning` for `datetime.utcnow()`:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal
in a future version. Use timezone-aware objects to represent datetimes in UTC:
datetime.datetime.now(datetime.UTC).
```

**Comparison test confirmed:** Mixing naive (`utcnow()`) and aware (`now(timezone.utc)`) datetimes raises `TypeError: can't compare offset-naive and offset-aware datetimes`.

**Action:** Use `datetime.now(timezone.utc)` throughout `compile_training_data.py` for version naming and incremental query timestamps. This is already documented in the State of the Art section but warrants a code-level enforcement note.

**Confidence:** HIGH — verified directly on target Python version

### Summary of Deep Dive Findings

| Topic | Finding | Confidence | Impact on Plan |
|-------|---------|------------|----------------|
| Two-step split | Switch to 70/30 → 50/50 approach (simpler ratios) | HIGH | Change Pattern 3 example code |
| Empty stratify class | Must filter `1_1` (0 rows) before stratification | HIGH | Add pre-split class distribution check |
| Class imbalance | Stratified split is sufficient; resampling = training layer | HIGH | No plan change needed |
| Temporal leakage (subtle) | 5 additional paths identified, all LOW-MEDIUM risk | MEDIUM | Add SQL comment, document for ML team |
| datetime.utcnow() | Deprecated in Python 3.12, confirmed with TypeError | HIGH | Enforce `now(timezone.utc)` in code
