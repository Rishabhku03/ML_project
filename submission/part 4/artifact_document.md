# ChatSentry — Batch Pipeline: Versioned Training & Evaluation Datasets from Production Data

**Requirement:**
Batch pipeline that compiles versioned training and evaluation datasets from "production" data, with well-justified candidate selection and avoiding data leakage.

**Project:** ChatSentry AI-Powered Content Moderation — Data Pipeline
**Author:** Rishabh Narayan (Data Specialist)
**Repository:** `Ml_Project`
**Infrastructure:** Chameleon Cloud KVM@TACC (m1.xlarge — 4 vCPU / 16GB RAM, no GPU)

---

## 1. Overview

This artifact documents the batch training data compilation pipeline. The pipeline queries production data from PostgreSQL, applies candidate selection with well-justified filtering, prevents temporal data leakage at two levels, validates output with Great Expectations, and produces versioned train/val/test snapshots in S3.

**Core responsibilities:**
1. **Candidate selection** — Only messages with a moderation decision (labeled by human or model) enter the training set
2. **Temporal leakage prevention** — Messages can only appear in training if the moderation decision was made AFTER the message was created
3. **Quality gate** — Removes corrupt data, noise, and outliers before training
4. **Versioned output** — UTC-timestamped snapshots of stratified 70/15/15 train/val/test splits
5. **Data validation** — Great Expectations runs 6 declarative checks on every compilation

---

## 2. Artifact Inventory

### 2.1 Core Pipeline — `compile_training_data.py`

**File:** `src/data/compile_training_data.py` (446 lines)

The pipeline operates in two modes:

| Mode | Entry Function | When | Data Source |
|------|---------------|------|-------------|
| Initial | `compile_initial()` (line 246) | PostgreSQL is empty | CSV chunks from S3 → clean → PostgreSQL |
| Incremental | `compile_incremental()` (line 359) | PostgreSQL has data | Direct SQL query with leakage prevention |

**Auto-detection** (lines 420–446): The `__main__` block checks PostgreSQL row count and selects the appropriate mode.

**Both modes share the same compilation steps after data loading:**
1. Temporal leakage filter (incremental mode)
2. TextCleaner fallback for NULL `cleaned_text`
3. Output column selection (5 columns)
4. Great Expectations validation (6 checks)
5. Quality gate filtering
6. Stratified 70/15/15 split
7. Versioned S3 upload

---

### 2.2 Candidate Selection — Well-Justified Filtering

Candidate selection determines which rows from production data are eligible for training. Three filters are applied in sequence:

#### Filter 1: INNER JOIN with Moderation Table

```sql
SELECT ...
FROM messages m
INNER JOIN moderation mod ON m.id = mod.message_id
WHERE m.created_at < mod.decided_at
ORDER BY m.created_at
```

**Justification:** Only messages that have received a moderation decision (action=labeled or reviewed by admin) are included. Unmoderated messages — those never reviewed — cannot contribute supervised training signal.

#### Filter 2: Temporal Leakage Prevention

```sql
WHERE m.created_at < mod.decided_at
```

**Justification:** A message can only appear in training data if it was created BEFORE the moderation decision was made. This prevents the model from training on information that wasn't available at inference time.

#### Filter 3: Quality Gate

```python
def apply_quality_gate(df: pd.DataFrame) -> pd.DataFrame:
    initial_count = len(df)
    # Remove #ERROR! duplicates (DATA_ISSUES.md Issue 4: 262 rows)
    df = df[~df["cleaned_text"].str.contains(config.QUALITY_ERROR_PATTERN, na=False)]
    # Filter texts below min chars (DATA_ISSUES.md Issue 5: noise)
    df = df[df["cleaned_text"].str.len() >= config.QUALITY_MIN_TEXT_LENGTH]
    # Cap texts above max chars (DATA_ISSUES.md Issue 5: outliers)
    df["cleaned_text"] = df["cleaned_text"].str[: config.QUALITY_MAX_TEXT_LENGTH]
    return df
```

**Justification:**
| Filter | Threshold | Why |
|--------|-----------|-----|
| Remove `#ERROR!` | Pattern match | 262 corrupt rows identified in DATA_ISSUES.md Issue 4 — parser artifacts that produce nonsensical training signal |
| Drop <10 chars | `len(cleaned_text) < 10` | Short texts are noise (greetings, fragments) with insufficient context for label learning |
| Cap >5000 chars | `len(cleaned_text) > 5000` | Outliers skew token distributions and consume excessive memory during training |

**Result:** Only messages that (a) have a moderation decision, (b) were created before that decision, and (c) pass quality thresholds enter the training set.

---

### 2.3 Temporal Leakage Prevention — Defense-in-Depth

Temporal leakage is prevented at two independent levels:

#### SQL Level (line 29–42, `INCREMENTAL_QUERY`)

```sql
WHERE m.created_at < mod.decided_at
```

The SQL WHERE clause is the primary enforcement mechanism. PostgreSQL executes the filter before data reaches the application, minimizing memory usage and ensuring the constraint is always applied.

#### Python Level (line 45–60, `filter_temporal_leakage()`)

```python
def filter_temporal_leakage(df: pd.DataFrame) -> pd.DataFrame:
    if "decided_at" not in df.columns:
        return df
    return df[df["created_at"] < df.decided_at].copy()
```

Called at `compile_incremental()` line 383 as defense-in-depth. Catches edge cases where SQL joins may produce unexpected results (e.g., timezone handling differences, NULL comparisons).

**Test coverage:**
| Test | File | Validates |
|------|------|-----------|
| `test_temporal_leakage_filter_excludes_future_decisions` | `tests/test_compile_training_data.py:249` | Rows where `decided_at < created_at` are dropped |

---

### 2.4 Versioned Dataset Storage

**Version generation** (line 193–199):

```python
def generate_version() -> str:
    return datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S")
```

**Upload structure** (lines 202–243, `upload_snapshot()`):

```
S3: proj09_Data/zulip-training-data/vYYYYMMDD-HHMMSS/
  ├── train.csv (70%)
  ├── val.csv (15%)
  └── test.csv (15%)
```

**Versioning properties:**
| Property | Value |
|----------|-------|
| Format | `vYYYYMMDD-HHMMSS` (e.g., `v20260403-142301`) |
| Timezone | UTC |
| Uniqueness | Globally unique per compilation run |
| Sortability | Lexicographic sort = chronological sort |
| Human-readable | Date and time immediately interpretable |
| Format | CSV (not Parquet) — broader compatibility for ML team |

**Test coverage:**
| Test | File | Validates |
|------|------|-----------|
| `test_version_format` | `tests/test_compile_training_data.py:354` | Regex match `v\d{8}-\d{6}` |

---

### 2.5 Stratified 70/15/15 Split

**Implementation** (lines 130–190, `stratified_split()`):

```python
# Combined stratification label: "is_suicide_is_toxicity" (4 classes)
df["label_combo"] = (
    df["is_suicide"].astype(str) + "_" + df["is_toxicity"].astype(str)
)

# Step 1: 70% train / 30% temp (stratified)
train_df, temp_df = train_test_split(
    df, test_size=0.30, stratify=df["label_combo"], random_state=42
)

# Step 2: 30% temp → 15% val / 15% test (stratified)
val_df, test_df = train_test_split(
    temp_df, test_size=0.50, stratify=temp_df["label_combo"], random_state=42
)
```

**Stratification design:**
- Combined label: 4 classes (`0_0`, `0_1`, `1_0`, `1_1`)
- Empty classes (e.g., `1_1` with 0 rows) are filtered before splitting (line 156–158)
- `random_state=42` ensures reproducibility
- `label_combo` column dropped from output (lines 180–182)

**Label class definitions:**

| Class | `is_suicide` | `is_toxicity` | Description |
|-------|-------------|---------------|-------------|
| `0_0` | 0 | 0 | Benign messages |
| `0_1` | 0 | 1 | Toxic but not suicidal |
| `1_0` | 1 | 0 | Suicidal but not toxic |
| `1_1` | 1 | 1 | Both (typically 0 rows in this dataset) |

**Test coverage:**
| Test | File | Validates |
|------|------|-----------|
| `test_stratified_split_proportions` | `tests/test_compile_training_data.py:305` | ~70/15/15 proportions, no `label_combo` in output |
| `test_stratified_split_filters_empty_class` | `tests/test_compile_training_data.py:331` | Splits without error when `1_1` class is empty |

---

### 2.6 Data Quality Validation — Great Expectations

**File:** `src/data/data_quality.py`

6 declarative expectations run on every compilation output:

| # | Check | Column | Rule | Severity | Behavior |
|---|-------|--------|------|----------|----------|
| 1 | Required Column Present | `cleaned_text` | Column must exist | Error | Halt pipeline |
| 2 | Text Length Within Bounds | `cleaned_text` | Length 10–5000 chars | Warning | Log + HTML report |
| 3 | No Corrupt Data | `cleaned_text` | Must not match `#ERROR!` | Warning | Log + HTML report |
| 4 | Valid Label Values | `is_suicide` | Values in {0, 1} | Error | Halt pipeline |
| 5 | Class Balance Ratio | `is_toxicity` | Mean between 2–8% | Warning | Log + HTML report |
| 6 | No Missing Values | `cleaned_text` | Must not be null | Error | Halt pipeline |

**Design decision:** WARNING-level failures do NOT halt the pipeline — they log warnings and the HTML report is uploaded to S3 for the ML team to review. This "warn and continue" approach prioritizes production uptime while maintaining quality visibility.

**Output:** HTML Data Docs report uploaded to S3 at `data-quality-report/report-YYYYMMDD-HHMMSS.html`, viewable via the GE Viewer Flask app on port 8080.

---

### 2.7 Text Cleaning Pipeline (Shared)

**File:** `src/data/text_cleaner.py`

The same `TextCleaner` class is used by both the online API middleware and the batch compilation path, ensuring identical transformations.

**5-step pipeline (in order):**

| Step | Function | Input | Output |
|------|----------|-------|--------|
| 1 | `fix_unicode()` | `cafÃ©` | `café` |
| 2 | `strip_markdown()` | `**bold** text` | `bold text` |
| 3 | `extract_urls()` | `https://example.com` | `[URL]` |
| 4 | `standardize_emojis()` | `😊` | `:smiling_face_with_smiling_eyes:` |
| 5 | `scrub_pii()` | `user@email.com` | `[EMAIL]` |

**Pipeline order rationale:**
- Unicode fix before Markdown strip (fixes encoding inside HTML tags)
- URL extraction before PII scrub (avoids matching email patterns inside URLs)

---

### 2.8 PostgreSQL Schema

**File:** `docker/init_sql/00_create_tables.sql`

**Tables relevant to batch pipeline:**

| Table | Purpose | Key columns for batch |
|-------|---------|----------------------|
| `messages` | Production chat messages | `id`, `text`, `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `created_at` |
| `moderation` | Moderation decisions | `message_id`, `action`, `confidence`, `decided_at` |

**Key constraint:** `moderation.message_id → messages.id` (foreign key)

---

### 2.9 Configuration

**File:** `config/pipeline.yaml`

```yaml
quality:
  min_text_length: 10
  max_text_length: 5000
  error_pattern: "#ERROR!"

split:
  train_ratio: 0.70
  val_ratio: 0.15
  test_ratio: 0.15
  random_state: 42

buckets:
  training: proj09_Data

batch:
  upload_size: 10000
```

Loaded by `src/utils/config.py` as a frozen dataclass. Environment variables override secrets (S3 credentials, DATABASE_URL).

---

### 2.10 Docker Infrastructure

**File:** `docker/docker-compose.yaml`

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5432 | PostgreSQL 18 — production messages + moderation decisions |
| `adminer` | 5050 | Web GUI for PostgreSQL queries and verification |
| `api` | 8000 | FastAPI — runs batch pipeline via `docker exec` |
| `ge-viewer` | 8080 | Flask app serving GE HTML quality reports from S3 |

**Dockerfile.api:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. End-to-End Pipeline Flow

```
PostgreSQL (production data)
    │
    │  INCREMENTAL_QUERY:
    │  SELECT messages + moderation
    │  WHERE created_at < decided_at  ← candidate selection + leakage prevention
    ▼
compile_incremental()
    │
    ├─ 1. Temporal leakage filter (defense-in-depth Python check)
    ├─ 2. TextCleaner fallback (NULL cleaned_text → clean raw text)
    ├─ 3. select_output_columns() → 5-column schema
    ├─ 4. validate_training_data() → GE 6 checks → HTML report → S3
    ├─ 5. apply_quality_gate() → remove #ERROR!, filter <10, cap >5000
    ├─ 6. stratified_split() → 70/15/15 on combined label
    └─ 7. upload_snapshot() → S3 versioned folder
          │
          ▼
    S3: proj09_Data/zulip-training-data/vYYYYMMDD-HHMMSS/
      ├── train.csv (70%, stratified)
      ├── val.csv (15%, stratified)
      └── test.csv (15%, stratified)

    S3: proj09_Data/data-quality-report/report-YYYYMMDD-HHMMSS.html
```

---

## 4. Test Inventory

### Unit Tests

| Test | File | Line | Validates |
|------|------|------|-----------|
| `test_ge_validation_replaces_quality_gate` | `test_compile_training_data.py` | 128 | GE validation runs and returns results |
| `test_ge_validation_catches_error_rows` | `test_compile_training_data.py` | 141 | GE catches `#ERROR!` pattern |
| `test_ge_validation_catches_short_texts` | `test_compile_training_data.py` | 158 | GE catches texts <10 chars |
| `test_ge_validation_warn_and_continue` | `test_compile_training_data.py` | 175 | GE warnings don't halt pipeline |
| `test_quality_gate_removes_error_rows` | `test_compile_training_data.py` | 190 | Quality gate removes `#ERROR!` rows |
| `test_quality_gate_filters_short_texts` | `test_compile_training_data.py` | 209 | Quality gate removes <10 char texts |
| `test_quality_gate_caps_long_texts` | `test_compile_training_data.py` | 228 | Quality gate caps >5000 char texts |
| `test_temporal_leakage_filter_excludes_future_decisions` | `test_compile_training_data.py` | 249 | Rows with `decided_at < created_at` dropped |
| `test_output_schema_has_five_columns` | `test_compile_training_data.py` | 274 | Output has exactly 5 columns |
| `test_stratified_split_proportions` | `test_compile_training_data.py` | 305 | ~70/15/15 split proportions |
| `test_stratified_split_filters_empty_class` | `test_compile_training_data.py` | 331 | Handles empty stratification classes |
| `test_version_format` | `test_compile_training_data.py` | 354 | Version string matches `v\d{8}-\d{6}` |

**Run all unit tests:**
```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v
```

### E2E Tests (require running Docker infrastructure)

| File | Covers |
|------|--------|
| `tests/e2e/test_02_data_flow/test_compilation.py` | Initial mode upload, temporal leakage, quality gate, PostgreSQL insert/query |
| `tests/e2e/test_03_data_quality/test_quality_gates.py` | GE validation against live data |
| `tests/e2e/test_05_full_pipeline/test_full_pipeline_small.py` | Small end-to-end pipeline run |

---

## 5. Reproducibility Instructions

### Prerequisites
- Chameleon Cloud account with access to KVM@TACC
- SSH key configured for VM access
- S3 credentials for `proj09_Data` bucket

### Steps to Reproduce

**1. Deploy services**
```bash
ssh -i ~/.ssh/id_rsa_chameleon cc@<VM_IP>
cd chatsentry
cp docker/.env.example docker/.env  # Fill in S3 credentials
cd docker && docker compose up -d
```

**2. Verify infrastructure**
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

**3. Run batch pipeline**
```bash
# Auto-detect mode
docker exec api python3 -m src.data.compile_training_data

# Explicit incremental mode
docker exec api python3 -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
from src.data.compile_training_data import compile_incremental
compile_incremental()
"
```

**4. Verify output in S3**
```bash
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for obj in sorted(c.list_objects('proj09_Data', prefix='zulip-training-data/', recursive=True), key=lambda o: o.object_name):
    print(f'{obj.object_name} ({obj.size/1024:.1f} KB)')
"
```

**5. Verify GE report**
- Open `http://<VM_IP>:8080` in browser
- Click latest report to see 6 expectation results

**6. Run tests**
```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py tests/test_data_quality.py -v
```

---

## 6. Design Decisions & Justifications

| Decision | Justification |
|----------|---------------|
| INNER JOIN with `moderation` for candidate selection | Only labeled messages provide supervised training signal; unmoderated messages are noise |
| `WHERE created_at < decided_at` for leakage prevention | Prevents model from seeing future information; a message must exist before it can be moderated |
| Defense-in-depth: SQL WHERE + Python filter | SQL handles 99% of cases; Python filter catches edge cases from JOIN behavior |
| Quality gate at batch level, not API level | API accepts all messages for production availability; quality filtering happens at training time |
| Remove `#ERROR!` rows (262 identified) | Parser artifacts produce nonsensical training signal (DATA_ISSUES.md Issue 4) |
| Drop <10 char texts | Short fragments (greetings, reactions) lack sufficient context for label learning |
| Cap >5000 char texts | Outliers skew token distributions and consume excessive training memory |
| Stratified split on combined label | Preserves rare class proportions (suicidal + toxic) across train/val/test |
| Filter empty stratification classes | Dataset has 0 rows in `1_1` class; splitting would fail on empty strata |
| UTC timestamp versioning | Globally unique, sortable, human-readable version tags |
| CSV over Parquet | Broader compatibility; no additional dependencies for ML team |
| GE warnings don't halt pipeline | ML team reviews HTML reports separately; production uptime prioritized |
| Shared TextCleaner (online + batch) | Eliminates training-serving skew; identical transformations in both paths |

---

## 7. Artifact File Listing

```
Ml_Project/
├── src/
│   ├── data/
│   │   ├── compile_training_data.py     # Batch compiler (446 lines) — CORE ARTIFACT
│   │   ├── data_quality.py              # GE validation — 6 declarative checks
│   │   ├── text_cleaner.py              # 5-step cleaning pipeline (shared)
│   │   └── ingest_and_expand.py         # CSV → S3 ingestion
│   ├── api/
│   │   └── main.py                      # FastAPI app (runs pipeline via docker exec)
│   └── utils/
│       ├── config.py                    # Configuration loader
│       ├── minio_client.py              # S3 client factory
│       └── db.py                        # PostgreSQL connection factory
├── docker/
│   ├── docker-compose.yaml              # 4 services
│   ├── Dockerfile.api                   # API container image
│   ├── ge-viewer/
│   │   ├── Dockerfile                   # GE Viewer container
│   │   └── app.py                       # Flask GE report viewer
│   └── init_sql/
│       ├── 00_create_tables.sql         # PostgreSQL schema DDL
│       └── 01_seed_data.sql             # Seed data
├── config/
│   └── pipeline.yaml                    # Pipeline configuration
├── tests/
│   ├── test_compile_training_data.py    # 12 unit tests — CORE TEST ARTIFACT
│   ├── test_data_quality.py             # GE validation tests
│   └── e2e/
│       ├── test_02_data_flow/
│       │   └── test_compilation.py      # Compilation E2E tests
│       ├── test_03_data_quality/
│       │   └── test_quality_gates.py    # Quality gate E2E tests
│       └── test_05_full_pipeline/
│           └── test_full_pipeline_small.py
├── requirements.txt                     # Python dependencies
├── pyproject.toml                       # Project metadata + tool config
└── combined_dataset.csv                 # Source dataset (391,645 rows)
```
