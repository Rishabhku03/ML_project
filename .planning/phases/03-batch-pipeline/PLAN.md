---
phase: 03-batch-pipeline
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/data/compile_training_data.py
  - tests/test_compile_training_data.py
autonomous: true
requirements:
  - BATCH-01
  - BATCH-02
  - BATCH-03
  - BATCH-04
  - BATCH-05
user_setup: []

must_haves:
  truths:
    - "scikit-learn installed and importable, listed in pyproject.toml"
    - "compile_training_data.py --mode initial reads CSV chunks from MinIO, cleans via TextCleaner, bulk-loads to PostgreSQL"
    - "compile_training_data.py --mode incremental queries PostgreSQL with temporal leakage filter (created_at < decided_at)"
    - "Quality gate removes #ERROR! rows, filters < 10 chars, caps > 5000 chars before split"
    - "Stratified 70/15/15 split preserves class proportions across train/val/test using combined 4-class label"
    - "Versioned snapshot (vYYYYMMDD-HHMMSS/) uploaded to MinIO zulip-training-data with train.csv, val.csv, test.csv"
    - "Output exports only 5 columns: cleaned_text, is_suicide, is_toxicity, source, message_id — no PostgreSQL metadata"
  artifacts:
    - path: "pyproject.toml"
      provides: "scikit-learn>=1.8.0 dependency"
    - path: "src/data/compile_training_data.py"
      provides: "Batch pipeline with quality gate, temporal leakage prevention, stratified split, MinIO upload"
      exports:
        - "compile_initial()"
        - "compile_incremental()"
        - "apply_quality_gate(df)"
        - "filter_temporal_leakage(df)"
        - "select_output_columns(df)"
        - "stratified_split(df)"
        - "upload_snapshot(client, bucket, train_df, val_df, test_df)"
        - "generate_version()"
    - path: "tests/test_compile_training_data.py"
      provides: "Unit tests covering BATCH-01 through BATCH-05"
  key_links:
    - from: "src/data/compile_training_data.py"
      to: "src/data/text_cleaner.py"
      via: "from src.data.text_cleaner import TextCleaner"
      pattern: "TextCleaner"
    - from: "src/data/compile_training_data.py"
      to: "src/utils/minio_client.py"
      via: "from src.utils.minio_client import get_minio_client"
      pattern: "get_minio_client"
    - from: "src/data/compile_training_data.py"
      to: "src/utils/db.py"
      via: "from src.utils.db import get_db_connection"
      pattern: "get_db_connection"
    - from: "src/data/compile_training_data.py"
      to: "sklearn.model_selection.train_test_split"
      via: "from sklearn.model_selection import train_test_split"
      pattern: "train_test_split"
    - from: "stratified_split()"
      to: "train_test_split(stratify=label_combo)"
      via: "70/30 then 50/50 split approach"
      pattern: "test_size=0\\.30.*test_size=0\\.50"
---

# Phase 3: Batch Pipeline

## Objective

Build the batch compilation pipeline (`compile_training_data.py`) that produces versioned training datasets from production data with temporal leakage prevention, quality gates, stratified splits, and MinIO upload.

Purpose: Deliver a reproducible data pipeline that compiles train/val/test datasets the ML training team can consume. The pipeline prevents temporal data leakage, filters known data quality issues, preserves class proportions via stratified splits, and stores immutable versioned snapshots in MinIO.
Output: `src/data/compile_training_data.py` (pipeline), `tests/test_compile_training_data.py` (tests), `pyproject.toml` (scikit-learn dependency)

## Context

@.planning/phases/03-batch-pipeline/03-RESEARCH.md
@.planning/phases/03-batch-pipeline/03-CONTEXT.md
@src/data/text_cleaner.py
@src/utils/config.py
@src/utils/minio_client.py
@src/utils/db.py
@docker/init_sql/00_create_tables.sql
@pyproject.toml
@data/DATA_ISSUES.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->
<!-- Executor should use these directly — no codebase exploration needed. -->

From src/data/text_cleaner.py:
```python
class TextCleaner:
    """Stateless text cleaning pipeline. Call cleaner.clean(text) for any string."""
    steps: list[Callable[[str], str]]
    def clean(self, text: str) -> str: ...
```

From src/utils/config.py:
```python
@dataclass(frozen=True)
class Config:
    DATABASE_URL: str       # PostgreSQL connection string
    MINIO_ENDPOINT: str     # e.g. "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool
    BUCKET_RAW: str = "zulip-raw-messages"
    BUCKET_TRAINING: str = "zulip-training-data"

config = Config()  # module-level singleton
```

From src/utils/minio_client.py:
```python
def get_minio_client() -> Minio:  # Returns connected Minio client
```

From src/utils/db.py:
```python
def get_db_connection():  # Returns psycopg2 connection using config.DATABASE_URL
```

From docker/init_sql/00_create_tables.sql — PostgreSQL schema:
```sql
-- messages table columns: id (UUID), user_id (UUID), text, cleaned_text,
--   toxic, severe_toxic, obscene, threat, insult, identity_hate (booleans),
--   is_suicide (boolean), source (varchar), created_at (timestamptz)

-- moderation table columns: id (UUID), message_id (UUID), action, confidence,
--   model_version, source, decided_at (timestamptz)
```

From pyproject.toml — current dependencies (no scikit-learn yet):
```toml
dependencies = [
    "fastapi>=0.135.0", "uvicorn>=0.42.0", "minio>=7.2.0",
    "psycopg2-binary>=2.9.0", "pandas>=3.0.0", "huggingface_hub>=1.9.0",
    "python-dotenv>=1.2.0", "pyyaml>=6.0.0", "ftfy>=6.3.1",
    "emoji>=2.15.0", "markdownify>=1.2.2",
]
```
</interfaces>

## Tasks

<task type="auto">
  <name>Task 1: Add scikit-learn dependency (BATCH-05 prerequisite)</name>
  <files>pyproject.toml</files>
  <action>Add `"scikit-learn>=1.8.0"` to `[project] dependencies` in pyproject.toml. Then install it:

```toml
# In pyproject.toml [project] dependencies list, add after existing entries:
dependencies = [
    "fastapi>=0.135.0",
    "uvicorn>=0.42.0",
    "minio>=7.2.0",
    "psycopg2-binary>=2.9.0",
    "pandas>=3.0.0",
    "huggingface_hub>=1.9.0",
    "python-dotenv>=1.2.0",
    "pyyaml>=6.0.0",
    "ftfy>=6.3.1",
    "emoji>=2.15.0",
    "markdownify>=1.2.2",
    "scikit-learn>=1.8.0",  # NEW — stratified train/test/validation split
]
```

Run: `pip install scikit-learn>=1.8.0`
</action>
  <verify>
    <automated>python -c "import sklearn; print(sklearn.__version__)" && pip show scikit-learn | grep Version</automated>
  </verify>
  <done>scikit-learn installed and importable, listed in pyproject.toml dependencies</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create compile_training_data.py batch pipeline (BATCH-01 through BATCH-05)</name>
  <files>src/data/compile_training_data.py, tests/test_compile_training_data.py</files>
  <behavior>
    - `apply_quality_gate(df)`: Removes `#ERROR!` rows, filters cleaned_text < 10 chars, caps at 5000 chars, logs results
    - `filter_temporal_leakage(df)`: Filters rows where `created_at >= decided_at`
    - `select_output_columns(df)`: Derives `is_toxicity` from OR of 6 booleans (PostgreSQL) or uses column directly (CSV), returns 5 columns
    - `stratified_split(df)`: Combined label `label_combo = "{is_suicide}_{is_toxicity}"`, filter empty classes, 70/30 then 50/50 split with `stratify=`, random_state=42, drop `label_combo` before return
    - `compile_initial()`: Read CSV chunks from MinIO `zulip-raw-messages/real/combined_dataset/`, TextCleaner on text column, bulk-load to PostgreSQL
    - `compile_incremental()`: SQL query with INNER JOIN moderation, temporal filter, COALESCE(cleaned_text, text), TextCleaner fallback for NULLs
    - `upload_snapshot()`: UTC timestamp version `vYYYYMMDD-HHMMSS/`, upload 3 CSVs to `zulip-training-data`
    - CLI: `--mode initial|incremental` via argparse
  </action>
  <action>Create `src/data/compile_training_data.py` implementing the batch pipeline per D-01 through D-26. Create `tests/test_compile_training_data.py` with unit tests.

**src/data/compile_training_data.py:**

```python
"""Batch training data compiler — compiles versioned training datasets from PostgreSQL.

Two modes:
  --mode initial:     Read CSV chunks from MinIO, clean via TextCleaner, bulk-load to PostgreSQL
  --mode incremental: Query PostgreSQL for new moderated messages with temporal leakage prevention

Per BATCH-01 through BATCH-05.
"""

import argparse
import io
import logging
from datetime import datetime, timezone

import pandas as pd
from sklearn.model_selection import train_test_split

from src.data.text_cleaner import TextCleaner
from src.utils.config import config
from src.utils.db import get_db_connection
from src.utils.minio_client import get_minio_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL query: incremental mode with temporal leakage prevention (BATCH-02, D-04, D-05)
# ---------------------------------------------------------------------------

INCREMENTAL_QUERY = """
    SELECT
        m.id AS message_id,
        COALESCE(m.cleaned_text, m.text) AS cleaned_text,
        m.is_suicide,
        (m.toxic OR m.severe_toxic OR m.obscene OR m.threat
            OR m.insult OR m.identity_hate) AS is_toxicity,
        m.source,
        m.created_at,
        mod.decided_at
    FROM messages m
    INNER JOIN moderation mod ON m.id = mod.message_id
    -- Temporal leakage prevention: only train on information available
    -- BEFORE the moderation decision. This ensures the model cannot
    -- learn from post-decision message content or edits.
    WHERE m.created_at < mod.decided_at
    ORDER BY m.created_at
"""


def apply_quality_gate(df: pd.DataFrame) -> pd.DataFrame:
    """Filter known data quality issues before split (D-20 through D-24).

    1. Remove #ERROR! duplicates (DATA_ISSUES.md Issue 4)
    2. Filter texts below 10 chars (noise threshold, Issue 5)
    3. Cap texts above 5000 chars (outlier threshold, Issue 5)

    Args:
        df: DataFrame with 'cleaned_text' column.

    Returns:
        Filtered DataFrame.
    """
    initial_count = len(df)

    # Remove #ERROR! duplicates (D-21)
    df = df[~df["cleaned_text"].str.contains("#ERROR!", na=False)]

    # Filter texts below 10 chars (D-22)
    df = df[df["cleaned_text"].str.len() >= 10]

    # Cap texts above 5000 chars (D-23)
    df["cleaned_text"] = df["cleaned_text"].str[:5000]

    removed = initial_count - len(df)
    logger.info(
        "Quality gate: removed %d rows (%.2f%%)",
        removed,
        removed / initial_count * 100 if initial_count > 0 else 0,
    )
    return df


def filter_temporal_leakage(df: pd.DataFrame) -> pd.DataFrame:
    """Filter rows where created_at >= decided_at (BATCH-02, D-05).

    Only messages created BEFORE the moderation decision are included.
    If decided_at column is not present (e.g. CSV data without join),
    returns df unchanged.

    Args:
        df: DataFrame potentially with 'created_at' and 'decided_at' columns.

    Returns:
        Filtered DataFrame.
    """
    if "decided_at" not in df.columns:
        return df
    return df[df["created_at"] < df["decided_at"]].copy()


def select_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select and derive the 5 export columns (BATCH-04, D-15 through D-17).

    For PostgreSQL rows: derive is_toxicity from OR of 6 toxicity booleans (D-25).
    For CSV rows: use is_toxicity column directly (D-26).

    Output columns: cleaned_text, is_suicide, is_toxicity, source, message_id.

    Args:
        df: DataFrame from either CSV or PostgreSQL source.

    Returns:
        DataFrame with exactly 5 columns.
    """
    # Derive is_toxicity if individual booleans present (PostgreSQL source)
    toxicity_cols = [
        "toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate",
    ]
    if all(col in df.columns for col in toxicity_cols):
        df = df.copy()
        df["is_toxicity"] = (
            df["toxic"] | df["severe_toxic"] | df["obscene"]
            | df["threat"] | df["insult"] | df["identity_hate"]
        ).astype(int)

    # Ensure message_id exists (CSV rows use index or row number)
    if "message_id" not in df.columns:
        df = df.copy()
        df["message_id"] = range(len(df))

    output_cols = ["cleaned_text", "is_suicide", "is_toxicity", "source", "message_id"]
    return df[output_cols]


def stratified_split(
    df: pd.DataFrame, random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified 70/15/15 train/val/test split (BATCH-05, D-12 through D-14).

    Uses 70/30 then 50/50 approach for clean ratios.
    Filters empty stratification classes before splitting.

    Args:
        df: DataFrame with 'is_suicide' and 'is_toxicity' columns.
        random_state: Random seed for reproducibility.

    Returns:
        Tuple of (train_df, val_df, test_df).
    """
    df = df.copy()

    # Create combined stratification label (4 classes, D-13)
    df["label_combo"] = df["is_suicide"].astype(str) + "_" + df["is_toxicity"].astype(str)

    # Filter empty classes (DATA_ISSUES.md Issue 2: 1_1 has 0 rows)
    label_counts = df["label_combo"].value_counts()
    populated_classes = label_counts[label_counts > 0].index
    df = df[df["label_combo"].isin(populated_classes)]

    logger.info("Stratification classes: %s", dict(label_counts[label_counts > 0]))

    # Step 1: 70% train, 30% temp (D-14)
    train_df, temp_df = train_test_split(
        df, test_size=0.30, stratify=df["label_combo"], random_state=random_state,
    )

    # Step 2: split 30% evenly into val (15%) and test (15%)
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, stratify=temp_df["label_combo"], random_state=random_state,
    )

    # Drop temporary label_combo column before returning
    train_df = train_df.drop(columns=["label_combo"])
    val_df = val_df.drop(columns=["label_combo"])
    test_df = test_df.drop(columns=["label_combo"])

    logger.info(
        "Split sizes: train=%d, val=%d, test=%d",
        len(train_df), len(val_df), len(test_df),
    )
    return train_df, val_df, test_df


def generate_version() -> str:
    """Generate UTC timestamp version string (D-09).

    Returns:
        Version string like 'v20260403-142301'.
    """
    return datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S")


def upload_snapshot(
    client, bucket: str, train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame,
) -> str:
    """Upload versioned training data snapshot to MinIO (BATCH-03, D-09 through D-11).

    Args:
        client: MinIO client instance.
        bucket: Target bucket name (zulip-training-data).
        train_df: Training split DataFrame.
        val_df: Validation split DataFrame.
        test_df: Test split DataFrame.

    Returns:
        Version string used for the snapshot folder.
    """
    version = generate_version()

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
        logger.info(
            "Uploaded %s (%d rows) to %s/%s",
            split_name, len(split_df), bucket, object_name,
        )

    return version


def compile_initial() -> None:
    """Initial mode: read CSV from MinIO, clean, load to PostgreSQL, compile snapshot (BATCH-01, D-01, D-02).

    Steps:
    1. List CSV chunk objects from MinIO zulip-raw-messages/real/combined_dataset/
    2. Concatenate into single DataFrame
    3. Run TextCleaner on text column to produce cleaned_text
    4. Bulk-load to PostgreSQL messages table
    5. Apply quality gate
    6. Select output columns (derive is_toxicity from CSV column)
    7. Stratified split
    8. Upload versioned snapshot to MinIO
    """
    client = get_minio_client()
    cleaner = TextCleaner()

    # Read CSV chunks from MinIO
    logger.info("Reading CSV chunks from MinIO zulip-raw-messages/real/combined_dataset/")
    objects = client.list_objects(
        config.BUCKET_RAW, prefix="real/combined_dataset/", recursive=True,
    )

    chunks = []
    for obj in objects:
        response = client.get_object(config.BUCKET_RAW, obj.object_name)
        chunk_df = pd.read_csv(io.BytesIO(response.read()))
        chunks.append(chunk_df)
        response.close()
        response.release_conn()

    df = pd.concat(chunks, ignore_index=True)
    logger.info("Loaded %d rows from MinIO CSV chunks", len(df))

    # Clean text via TextCleaner
    logger.info("Running TextCleaner on text column")
    df["cleaned_text"] = df["text"].apply(lambda t: cleaner.clean(str(t)))

    # Bulk-load to PostgreSQL
    logger.info("Bulk-loading %d rows to PostgreSQL messages table", len(df))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(
                    """INSERT INTO messages (text, cleaned_text, is_suicide, source,
                       toxic, severe_toxic, obscene, threat, insult, identity_hate)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        row["text"], row["cleaned_text"], row["is_suicide"], "real",
                        bool(row.get("is_toxicity", False)), False, False, False,
                        bool(row.get("is_toxicity", False)), False,
                    ),
                )
        conn.commit()
        logger.info("Bulk load complete")
    finally:
        conn.close()

    # Apply quality gate
    df = apply_quality_gate(df)

    # Select output columns (CSV source — use is_toxicity column directly per D-26)
    df = select_output_columns(df)

    # Stratified split
    train_df, val_df, test_df = stratified_split(df)

    # Upload versioned snapshot
    client = get_minio_client()
    version = upload_snapshot(client, config.BUCKET_TRAINING, train_df, val_df, test_df)
    logger.info("Initial compilation complete: version %s", version)


def compile_incremental() -> None:
    """Incremental mode: query PostgreSQL, compile snapshot (BATCH-01, D-03, D-18).

    Steps:
    1. Query PostgreSQL with INNER JOIN moderation + temporal filter
    2. Apply TextCleaner fallback for NULL cleaned_text (D-18)
    3. Apply quality gate
    4. Select output columns (derive is_toxicity from boolean OR per D-25)
    5. Stratified split
    6. Upload versioned snapshot to MinIO
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql(INCREMENTAL_QUERY, conn)
        logger.info("Incremental query returned %d rows", len(df))
    finally:
        conn.close()

    if df.empty:
        logger.warning("No new moderated messages found — skipping snapshot")
        return

    # Temporal leakage filter (redundant with SQL WHERE but defense-in-depth)
    df = filter_temporal_leakage(df)

    # TextCleaner fallback for NULL cleaned_text (D-18)
    cleaner = TextCleaner()
    null_mask = df["cleaned_text"].isna() | (df["cleaned_text"] == "")
    if null_mask.any():
        logger.info("Running TextCleaner fallback on %d rows with NULL cleaned_text", null_mask.sum())
        df.loc[null_mask, "cleaned_text"] = df.loc[null_mask, "text"].apply(
            lambda t: cleaner.clean(str(t)) if pd.notna(t) else "",
        )

    # Drop temporal columns before quality gate
    df = df.drop(columns=["created_at", "decided_at"], errors="ignore")

    # Apply quality gate
    df = apply_quality_gate(df)

    # Select output columns (PostgreSQL source — derive is_toxicity per D-25)
    df = select_output_columns(df)

    # Stratified split
    train_df, val_df, test_df = stratified_split(df)

    # Upload versioned snapshot
    client = get_minio_client()
    version = upload_snapshot(client, config.BUCKET_TRAINING, train_df, val_df, test_df)
    logger.info("Incremental compilation complete: version %s", version)


if __name__ == "__main__":
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

**tests/test_compile_training_data.py:**

```python
"""Tests for compile_training_data.py — batch pipeline (BATCH-01 through BATCH-05)."""

import pandas as pd
import pytest


@pytest.fixture
def csv_sample_df() -> pd.DataFrame:
    """Sample DataFrame matching combined_dataset.csv schema (text, is_suicide, is_toxicity).

    Includes known data quality issues for quality gate testing:
    - 2 rows with '#ERROR!' text (DATA_ISSUES.md Issue 4)
    - 1 row with text < 10 chars (Issue 5)
    - 1 row with text > 5000 chars (Issue 5)
    - Mix of label combinations (1_0, 0_0, 0_1) — no 1_1 rows (Issue 2)
    """
    long_text = "x" * 5001
    return pd.DataFrame(
        {
            "text": [
                "I feel so sad and hopeless today",
                "You are such an idiot, kill yourself",
                "#ERROR!",
                "#ERROR!",
                "Hi",
                long_text,
                "This is a normal message about cats",
                "I want to end my life",
                "Go away you stupid person",
                "The weather is nice today",
                "I am thinking about suicide",
                "What a terrible awful person you are",
                "Nice work on the project",
                "I feel like nobody would miss me",
                "Shut up you moron",
                "Let's meet for lunch tomorrow",
            ],
            "cleaned_text": [
                "I feel so sad and hopeless today",
                "You are such an idiot, kill yourself",
                "#ERROR!",
                "#ERROR!",
                "Hi",
                long_text,
                "This is a normal message about cats",
                "I want to end my life",
                "Go away you stupid person",
                "The weather is nice today",
                "I am thinking about suicide",
                "What a terrible awful person you are",
                "Nice work on the project",
                "I feel like nobody would miss me",
                "Shut up you moron",
                "Let's meet for lunch tomorrow",
            ],
            "is_suicide": [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
            "is_toxicity": [0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
            "source": ["real"] * 16,
        }
    )


@pytest.fixture
def pg_sample_df() -> pd.DataFrame:
    """Sample DataFrame matching PostgreSQL messages+moderation join schema.

    Represents the output of the incremental query with individual toxicity
    booleans as returned by PostgreSQL (D-25: derived from OR of 6 columns).
    """
    return pd.DataFrame(
        {
            "message_id": [f"uuid-{i}" for i in range(8)],
            "cleaned_text": [
                "I feel so sad and hopeless today",
                None,  # NULL cleaned_text — triggers TextCleaner fallback (D-18)
                "This is a normal message",
                "I want to end my life",
                "Go away you stupid person",
                "Nice work on the project",
                None,  # Another NULL
                "Shut up you moron",
            ],
            "text": [
                "I feel so sad and hopeless today",
                "RAW: some unclean text here",
                "This is a normal message",
                "I want to end my life",
                "Go away you stupid person",
                "Nice work on the project",
                "RAW: another unclean text",
                "Shut up you moron",
            ],
            "is_suicide": [1, 0, 0, 1, 0, 0, 0, 0],
            "toxic": [0, 0, 0, 0, 1, 0, 0, 1],
            "severe_toxic": [0, 0, 0, 0, 0, 0, 0, 0],
            "obscene": [0, 0, 0, 0, 0, 0, 0, 0],
            "threat": [0, 0, 0, 0, 0, 0, 0, 0],
            "insult": [0, 0, 0, 0, 1, 0, 0, 1],
            "identity_hate": [0, 0, 0, 0, 0, 0, 0, 0],
            "source": ["real"] * 8,
            "created_at": pd.to_datetime(
                [
                    "2026-01-01T10:00:00Z",
                    "2026-01-02T10:00:00Z",
                    "2026-01-03T10:00:00Z",
                    "2026-01-04T10:00:00Z",
                    "2026-01-05T10:00:00Z",
                    "2026-01-06T10:00:00Z",
                    "2026-01-07T10:00:00Z",
                    "2026-01-08T10:00:00Z",
                ]
            ),
            "decided_at": pd.to_datetime(
                [
                    "2026-01-01T12:00:00Z",
                    "2026-01-02T12:00:00Z",
                    "2026-01-03T12:00:00Z",
                    "2026-01-04T12:00:00Z",
                    "2026-01-05T12:00:00Z",
                    "2026-01-06T12:00:00Z",
                    "2026-01-07T12:00:00Z",
                    "2026-01-08T12:00:00Z",
                ]
            ),
        }
    )


# ---------------------------------------------------------------------------
# Quality gate tests (D-20 through D-24, BATCH-04)
# ---------------------------------------------------------------------------


def test_quality_gate_removes_error_rows(csv_sample_df):
    """Quality gate removes rows containing '#ERROR!' (D-21, DATA_ISSUES.md Issue 4)."""
    from src.data.compile_training_data import apply_quality_gate

    result = apply_quality_gate(csv_sample_df)
    assert not result["cleaned_text"].str.contains("#ERROR!", na=False).any()


def test_quality_gate_filters_short_texts(csv_sample_df):
    """Quality gate removes texts below 10 chars (D-22, DATA_ISSUES.md Issue 5)."""
    from src.data.compile_training_data import apply_quality_gate

    result = apply_quality_gate(csv_sample_df)
    assert (result["cleaned_text"].str.len() >= 10).all()


def test_quality_gate_caps_long_texts(csv_sample_df):
    """Quality gate caps texts above 5000 chars (D-23, DATA_ISSUES.md Issue 5)."""
    from src.data.compile_training_data import apply_quality_gate

    result = apply_quality_gate(csv_sample_df)
    assert (result["cleaned_text"].str.len() <= 5000).all()


def test_quality_gate_logs_results(csv_sample_df, caplog):
    """Quality gate logs filtering results for audit trail (D-24)."""
    import logging

    from src.data.compile_training_data import apply_quality_gate

    with caplog.at_level(logging.INFO):
        apply_quality_gate(csv_sample_df)
    assert "Quality gate" in caplog.text


# ---------------------------------------------------------------------------
# Temporal leakage prevention tests (BATCH-02, D-04 through D-06)
# ---------------------------------------------------------------------------


def test_temporal_leakage_filter_excludes_future_decisions():
    """Only messages with created_at < decided_at are included (D-05)."""
    from src.data.compile_training_data import filter_temporal_leakage

    df = pd.DataFrame(
        {
            "message_id": ["a", "b", "c"],
            "created_at": pd.to_datetime(
                ["2026-01-01T10:00:00Z", "2026-01-02T10:00:00Z", "2026-01-03T10:00:00Z"]
            ),
            "decided_at": pd.to_datetime(
                ["2026-01-01T12:00:00Z", "2026-01-01T08:00:00Z", "2026-01-03T12:00:00Z"]
            ),
        }
    )
    result = filter_temporal_leakage(df)
    assert len(result) == 2
    assert "b" not in result["message_id"].values


# ---------------------------------------------------------------------------
# Output schema tests (BATCH-04, D-15 through D-17)
# ---------------------------------------------------------------------------


def test_output_schema_has_five_columns():
    """Output contains exactly 5 columns: cleaned_text, is_suicide, is_toxicity, source, message_id (D-15)."""
    from src.data.compile_training_data import select_output_columns

    df = pd.DataFrame(
        {
            "message_id": ["a"],
            "cleaned_text": ["hello"],
            "is_suicide": [0],
            "toxic": [0],
            "severe_toxic": [0],
            "obscene": [0],
            "threat": [0],
            "insult": [0],
            "identity_hate": [0],
            "source": ["real"],
            "created_at": pd.to_datetime(["2026-01-01T10:00:00Z"]),
            "decided_at": pd.to_datetime(["2026-01-01T12:00:00Z"]),
        }
    )
    result = select_output_columns(df)
    expected_cols = {"cleaned_text", "is_suicide", "is_toxicity", "source", "message_id"}
    assert set(result.columns) == expected_cols


# ---------------------------------------------------------------------------
# Stratified split tests (BATCH-05, D-12 through D-14)
# ---------------------------------------------------------------------------


def test_stratified_split_proportions():
    """Stratified split preserves class proportions across train/val/test (D-13, D-14)."""
    from src.data.compile_training_data import stratified_split

    # Create dataset with known class distribution
    n = 1000
    df = pd.DataFrame(
        {
            "cleaned_text": [f"message {i}" for i in range(n)],
            "is_suicide": [1] * 700 + [0] * 300,
            "is_toxicity": [0] * 700 + [1] * 40 + [0] * 260,
            "source": ["real"] * n,
            "message_id": [f"uuid-{i}" for i in range(n)],
        }
    )
    train, val, test = stratified_split(df)

    # Check proportions are approximately 70/15/15
    assert abs(len(train) / n - 0.70) < 0.05
    assert abs(len(val) / n - 0.15) < 0.05
    assert abs(len(test) / n - 0.15) < 0.05

    # Check no label_combo column in output
    assert "label_combo" not in train.columns


def test_stratified_split_filters_empty_class():
    """Stratified split filters out empty stratification classes before splitting."""
    from src.data.compile_training_data import stratified_split

    df = pd.DataFrame(
        {
            "cleaned_text": [f"message {i}" for i in range(100)],
            "is_suicide": [1] * 70 + [0] * 30,
            "is_toxicity": [0] * 70 + [1] * 30,
            "source": ["real"] * 100,
            "message_id": [f"uuid-{i}" for i in range(100)],
        }
    )
    # This dataset has no 1_1 rows — should still split without error
    train, val, test = stratified_split(df)
    assert len(train) + len(val) + len(test) == len(df)


# ---------------------------------------------------------------------------
# Versioned upload test (BATCH-03, D-09 through D-11)
# ---------------------------------------------------------------------------


def test_version_format():
    """Version string follows vYYYYMMDD-HHMMSS format (D-09)."""
    from src.data.compile_training_data import generate_version

    version = generate_version()
    import re

    assert re.match(r"v\d{8}-\d{6}", version)
```

Write both files, then run tests to verify they fail with "module not found" (RED phase):
```bash
pytest tests/test_compile_training_data.py -x -v 2>&1 | head -30
```

Then verify tests pass after implementation (GREEN phase):
```bash
pytest tests/test_compile_training_data.py -x -v
```
</action>
  <verify>
    <automated>pytest tests/test_compile_training_data.py -x -v</automated>
  </verify>
  <done>
    - `src/data/compile_training_data.py` exists with all exported functions
    - CLI supports `--mode initial|incremental` via argparse
    - `compile_initial()`: reads CSV from MinIO, TextCleaner, bulk-loads PostgreSQL
    - `compile_incremental()`: queries PostgreSQL with temporal leakage filter, TextCleaner fallback
    - `apply_quality_gate()`: removes #ERROR!, filters < 10 chars, caps > 5000 chars, logs results
    - `filter_temporal_leakage()`: filters created_at >= decided_at
    - `select_output_columns()`: derives is_toxicity from OR of 6 booleans (PostgreSQL), returns 5 columns
    - `stratified_split()`: 70/30 then 50/50 with stratify on combined label, filters empty classes, drops label_combo
    - `upload_snapshot()`: UTC timestamp version, uploads 3 CSVs to zulip-training-data
    - All unit tests pass covering BATCH-01 through BATCH-05
  </done>
</task>

<task type="auto">
  <name>Task 3: Run full test suite and verify pipeline end-to-end</name>
  <files>src/data/compile_training_data.py</files>
  <action>Run the full test suite to verify all BATCH-01 through BATCH-05 requirements are covered and passing. Then do a dry-run import check to verify the module loads cleanly with all dependencies:

```bash
# Run full test suite
pytest tests/test_compile_training_data.py -x -v

# Verify module imports cleanly
python -c "from src.data.compile_training_data import compile_initial, compile_incremental, apply_quality_gate, filter_temporal_leakage, select_output_columns, stratified_split, upload_snapshot, generate_version; print('All imports OK')"

# Verify CLI --help works
python -m src.data.compile_training_data --help
```
</action>
  <verify>
    <automated>pytest tests/test_compile_training_data.py -x -v && python -c "from src.data.compile_training_data import compile_initial, compile_incremental, apply_quality_gate, filter_temporal_leakage, select_output_columns, stratified_split, upload_snapshot, generate_version; print('All imports OK')"</automated>
  </verify>
  <done>All tests pass, module imports cleanly, CLI --help shows usage</done>
</task>

## Verification

```bash
# Full test suite
pytest tests/test_compile_training_data.py -x -v

# Lint check
ruff check src/data/compile_training_data.py

# Verify scikit-learn version
python -c "import sklearn; print(f'scikit-learn {sklearn.__version__}')"
```

## Success Criteria

- [ ] `pyproject.toml` includes `scikit-learn>=1.8.0` in dependencies
- [ ] `src/data/compile_training_data.py` implements all 8 exported functions
- [ ] CLI supports `--mode initial` and `--mode incremental`
- [ ] Quality gate removes #ERROR!, filters < 10 chars, caps > 5000 chars (D-20 through D-24)
- [ ] Temporal leakage filter enforces `created_at < decided_at` (BATCH-02, D-05)
- [ ] Stratified split uses 70/30 then 50/50 approach with `stratify=` on combined 4-class label (BATCH-05, D-12 through D-14)
- [ ] Empty stratification classes filtered before split (DATA_ISSUES.md Issue 2)
- [ ] Output exports exactly 5 columns: cleaned_text, is_suicide, is_toxicity, source, message_id (BATCH-04, D-15)
- [ ] `is_toxicity` derived from OR of 6 toxicity booleans for PostgreSQL rows (D-25)
- [ ] Version naming uses `datetime.now(timezone.utc)` (not deprecated `datetime.utcnow()`)
- [ ] Versioned snapshot uploaded to `zulip-training-data` bucket (BATCH-03, D-11)
- [ ] `tests/test_compile_training_data.py` covers BATCH-01 through BATCH-05
- [ ] All tests pass: `pytest tests/test_compile_training_data.py -x -v`

## Output

After completion, create `.planning/phases/03-batch-pipeline/03-01-SUMMARY.md`
