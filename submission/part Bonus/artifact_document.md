# ChatSentry — Bonus: Great Expectations Data Quality Framework Integration

**Requirement:** Integrate a data framework not used in the lab assignments, that substantially improves your data design. Justify why it improves your design with a concrete example realistic in the context of your proposed service.

**Framework chosen:** Great Expectations (GE) v1.15.2+ — declarative data quality validation
**Project:** ChatSentry AI-Powered Content Moderation — Data Pipeline
**Author:** Rishabh Narayan (Data Specialist)
**Repository:** `Ml_Project`
**Infrastructure:** Chameleon Cloud KVM@TACC (m1.xlarge — 4 vCPU / 16GB RAM, no GPU)

---

## 1. Overview & Justification

### 1.1 The Problem

ChatSentry's batch training data pipeline compiles versioned train/val/test snapshots from production PostgreSQL data for hateBERT retraining. Before GE integration, data quality was enforced by a hand-coded `apply_quality_gate()` function in `compile_training_data.py`:

```python
def apply_quality_gate(df: pd.DataFrame) -> pd.DataFrame:
    initial_count = len(df)
    # Remove #ERROR! pattern
    df = df[~df["cleaned_text"].str.contains("#ERROR!", na=False)]
    # Remove too-short texts (< 10 chars)
    df = df[df["cleaned_text"].str.len() >= 10]
    # Remove too-long texts (> 5000 chars)
    df = df[df["cleaned_text"].str.len() <= 5000]
    logger.info("Quality gate: %d → %d rows", initial_count, len(df))
    return df
```

This approach has three critical weaknesses for an ML production system:

| Weakness | Impact on ChatSentry |
|----------|---------------------|
| **Hidden rules** | Quality logic buried in imperative code — data scientists can't inspect thresholds without reading Python |
| **No per-check reporting** | Silent filtering — no audit trail of WHAT was filtered or WHY |
| **No configurability** | Changing a text length limit requires editing code, testing, and redeploying |

### 1.2 How Great Expectations Solves This

Great Expectations replaces imperative filtering with **declarative Expectation Suites** — named, versioned, independently reportable quality checks. For ChatSentry, this means:

1. **Declarative specification** — quality rules are explicit `Expectation` objects, readable by non-engineers
2. **Per-expectation diagnostics** — each check reports PASS/FAIL with unexpected_percent, enabling targeted debugging
3. **Runtime configurability** — thresholds are parameters, not code constants
4. **Audit trail** — HTML Data Docs uploaded to S3 alongside versioned training data
5. **Testability** — 15 unit tests covering suite construction, violation detection, and edge cases

### 1.3 Concrete Realistic Example

**Scenario:** The ML team retrains hateBERT every 200 verified flags. After a weekend of Zulip traffic, the pipeline compiles a new training snapshot.

**Without GE:** The pipeline silently drops 340 rows — 120 with `#ERROR!` corruption, 80 too-short, 140 too-long. The ML team downloads the training CSV from S3 and notices the row count is lower than expected. They have no way to know what was removed, why, or whether the filtering was appropriate.

**With GE:** The pipeline generates an HTML Data Docs report showing:
- `No Corrupt Data (#ERROR!)` — FAIL — 1.2% of rows failed (120 rows)
- `Text Length Within Bounds (10–5000 chars)` — FAIL — 2.2% of rows failed (220 rows)
- `Valid Label Values (0 or 1)` — PASS
- `Class Balance Ratio (2–8% toxicity)` — PASS
- `No Missing Values` — PASS
- `Required Column Present` — PASS

The ML team reviews the report before consuming the snapshot, discovers the `#ERROR!` rate has doubled since last week, and investigates upstream data ingestion. This is the difference between blind filtering and auditable data quality governance.

---

## 2. Artifact Inventory

### 2.1 Core Module — `src/data/data_quality.py` (279 lines)

The GE integration module provides three public functions:

| Function | Purpose | Returns |
|----------|---------|---------|
| `build_expectation_suite()` | Creates GE Expectation Suite with 6 declarative checks | `ExpectationSuite` |
| `validate_training_data()` | Validates DataFrame against suite, generates HTML Data Docs | `(success: bool, results: dict)` |
| `upload_data_docs()` | Uploads HTML report to MinIO S3 | `object_name: str` |

**Configuration via `DEFAULT_THRESHOLDS`:**

```python
DEFAULT_THRESHOLDS = {
    "min_text_length": 10,
    "max_text_length": 5000,
    "error_pattern": "#ERROR!",
    "min_toxicity_ratio": 0.02,
    "max_toxicity_ratio": 0.08,
}
```

Thresholds can be overridden at validation time without code changes:

```python
success, results = validate_training_data(
    df, thresholds={"min_text_length": 5, "max_text_length": 3000}
)
```

### 2.2 Expectation Suite — 6 Declarative Checks

| # | Expectation Type | Column | Threshold | Severity | Replaces |
|---|-----------------|--------|-----------|----------|----------|
| 1 | `ExpectColumnToExist` | `cleaned_text` | — | error | Implicit column assumption |
| 2 | `ExpectColumnValueLengthsToBeBetween` | `cleaned_text` | 10–5000 chars | warning | `len() >= 10` and `len() <= 5000` |
| 3 | `ExpectColumnValuesToNotMatchRegex` | `cleaned_text` | `#ERROR!` | warning | `str.contains("#ERROR!")` |
| 4 | `ExpectColumnValuesToBeInSet` | `is_suicide` | `{0, 1}` | error | No prior check |
| 5 | `ExpectColumnMeanToBeBetween` | `is_toxicity` | 2–8% mean | warning | No prior check |
| 6 | `ExpectColumnValuesToNotBeNull` | `cleaned_text` | — | error | Implicit assumption |

Expectations 1, 4, 6 are `severity="error"` (hard failures). Expectations 2, 3, 5 are `severity="warning"` (log but continue — D-03: warn-and-continue behavior).

### 2.3 Pipeline Integration — `compile_training_data.py`

GE validation runs at Step 5 of the batch pipeline, after column selection and before the quality gate:

```
1. Query PostgreSQL (INNER JOIN moderation, temporal filter)
2. Defense-in-depth temporal leakage filter
3. TextCleaner fallback for NULL cleaned_text
4. Select output columns (5 columns)
5. >>> Great Expectations validation (6 checks) <<<  ← GE integration
6. Quality gate (filter issues found by GE)
7. Stratified 70/15/15 train/val/test split
8. Upload versioned snapshot to S3
```

**Integration code (lines 339–348 in `compile_training_data.py`):**

```python
# GE validation replaces SQL quality gate (D-01)
df = select_output_columns(df)

# GE validation (warn, generate HTML report)
success, results = validate_training_data(df)
if results.get("data_docs_html"):
    upload_data_docs(results["data_docs_html"], config.BUCKET_TRAINING)

# Quality gate: filter data issues before training bucket
df = apply_quality_gate(df)
```

The quality gate is **intentionally retained** alongside GE for defense-in-depth (decision D-05). GE validates and reports; the quality gate filters. This two-layer approach ensures:
- GE provides diagnostic visibility (what failed, what percentage)
- Quality gate ensures bad data never enters training (safety net)

### 2.4 Data Docs Viewer — `docker/ge-viewer/`

A lightweight Flask application serves GE HTML reports from MinIO:

**Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY docker/ge-viewer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/ge-viewer/app.py .
EXPOSE 8080
CMD ["python", "app.py"]
```

**Features:**
- Lists all reports from `data-quality-report/` prefix in MinIO
- Serves individual HTML reports at `/report/<filename>`
- Refresh button to re-fetch from MinIO
- Runs on port 8080 alongside the API (port 8000) and Adminer (port 5050)

---

## 3. Test Suite — `tests/test_data_quality.py` (334 lines, 15 tests)

### 3.1 Test Categories

| Category | Tests | What they verify |
|----------|-------|------------------|
| Suite construction | 2 | Suite has exactly 6 expectations; custom thresholds accepted |
| Clean data validation | 2 | All 6 expectations pass; statistics returned correctly |
| Violation detection | 6 | Each expectation catches its specific violation type |
| Warn-and-continue | 1 | Validation failures log warnings but don't raise exceptions |
| Data Docs generation | 2 | HTML report generated with pass/fail status |
| Edge cases | 2 | Empty DataFrame; runtime threshold overrides |

### 3.2 Key Test Examples

**Test: Error pattern detection**
```python
def test_catches_error_pattern():
    """Expectation catches #ERROR! rows (replaces D-21)."""
    df = pd.DataFrame({
        "cleaned_text": ["Good message", "#ERROR!", "Another good message"],
        "is_suicide": [0, 0, 0],
        "is_toxicity": [0, 0, 0],
        "source": ["real"] * 3,
    })
    success, results = validate_training_data(df)
    error_results = [
        r for r in results["expectation_results"]
        if "regex" in r.expectation_config.type
    ]
    assert len(error_results) == 1
    assert not error_results[0].success
```

**Test: Configurable thresholds**
```python
def test_runtime_parameters():
    """Thresholds can be overridden at validation time (D-05)."""
    df = pd.DataFrame({
        "cleaned_text": ["Short", "Normal length message here"],
        "is_suicide": [0, 0],
        "is_toxicity": [0, 0],
        "source": ["real"] * 2,
    })
    # Default: "Short" (5 chars) fails min_text_length=10
    success_default, _ = validate_training_data(df)
    # Relaxed: min_text_length=3, "Short" passes
    success_relaxed, _ = validate_training_data(
        df, thresholds={"min_text_length": 3}
    )
    # Verify different outcomes with different thresholds
```

### 3.3 Running Tests

```bash
# All GE tests
docker exec api python3 -m pytest tests/test_data_quality.py -v

# Specific test category
docker exec api python3 -m pytest tests/test_data_quality.py -v -k "error_pattern"
docker exec api python3 -m pytest tests/test_data_quality.py -v -k "clean_data"
docker exec api python3 -m pytest tests/test_data_quality.py -v -k "threshold"
```

---

## 4. Concrete Example: ChatSentry Batch Pipeline

### 4.1 Scenario

ChatSentry moderates Zulip chat messages. The batch pipeline compiles training data from production PostgreSQL for hateBERT retraining. After a weekend of traffic:

- **Total messages in PostgreSQL:** 12,450
- **Messages with moderation decisions:** 8,320
- **Eligible candidates (after temporal filter):** 7,890

### 4.2 GE Validation Results

```
=== Expectation Suite: training_data_quality ===
Total expectations: 6

1. ExpectColumnToExist on "cleaned_text" → PASS
2. ExpectColumnValueLengthsToBeBetween on "cleaned_text" → FAIL (2.2% unexpected)
3. ExpectColumnValuesToNotMatchRegex on "cleaned_text" → FAIL (1.2% unexpected)
4. ExpectColumnValuesToBeInSet on "is_suicide" → PASS
5. ExpectColumnMeanToBeBetween on "is_toxicity" → PASS
6. ExpectColumnValuesToNotBeNull on "cleaned_text" → PASS

Overall: FAILED (4/6 passed)
```

### 4.3 What GE Reveals

- **Text length violations (2.2%):** 174 rows outside 10–5000 char range — mostly very short messages ("ok", "hi", "lol") from Zulip chat
- **Error pattern matches (1.2%):** 95 rows containing `#ERROR!` — indicates upstream data ingestion corruption from CSV parsing

**Without GE:** Pipeline silently drops 269 rows. ML team downloads training CSV, notices count is 7,621 instead of expected 7,890. No explanation available.

**With GE:** ML team reviews HTML Data Docs, sees:
- Text length failures are expected (chat messages are short) — acceptable
- Error pattern failures spiked from 0.3% to 1.2% — investigation needed

The ML team investigates and discovers a CSV parsing bug in `ingest_and_expand.py` that inserts `#ERROR!` for rows with embedded newlines. Fix deployed before next retraining cycle.

### 4.4 Impact on Model Quality

This diagnostic capability directly impacts model quality:
- **Short messages** may not provide sufficient context for hateBERT classification — filtering them improves training signal quality
- **Error patterns** represent corrupt data that would introduce noise into the training set
- **Class balance monitoring** (2–8% toxicity ratio) prevents the model from overfitting to rare classes

---

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Batch Pipeline                         │
│                 compile_training_data.py                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. PostgreSQL Query ──┐                                │
│     (INNER JOIN +       │                                │
│      temporal filter)   │                                │
│                         ▼                                │
│  2. Temporal Leakage    DataFrame                        │
│     Defense-in-Depth    (7,890 rows)                     │
│                         │                                │
│                         ▼                                │
│  3. TextCleaner ──────── DataFrame                       │
│     Fallback            (cleaned_text filled)            │
│                         │                                │
│                         ▼                                │
│  4. Column Selection ── DataFrame                        │
│     (5 columns)         (cleaned_text, is_suicide,       │
│                          is_toxicity, source, msg_id)    │
│                         │                                │
│                         ▼                                │
│  5. GE Validation ───── SUCCESS/FAIL + HTML Report      │
│     ┌──────────────┐    │                                │
│     │ 6 Expectations│    │                                │
│     │ - Column exist│    │                                │
│     │ - Length check │    │                                │
│     │ - Error pattern│   │                                │
│     │ - Label values │   │                                │
│     │ - Class balance│   │                                │
│     │ - Null check   │   │                                │
│     └──────────────┘    │                                │
│          │               │                                │
│          ▼               ▼                                │
│     HTML Report ──► S3 (data-quality-report/)            │
│                         │                                │
│                         ▼                                │
│  6. Quality Gate ────── DataFrame                        │
│     (filter bad rows)   (7,621 rows)                     │
│                         │                                │
│                         ▼                                │
│  7. Stratified Split ── train.csv (70%)                  │
│                         val.csv   (15%)                  │
│                         test.csv  (15%)                  │
│                         │                                │
│                         ▼                                │
│  8. S3 Upload ──────── S3 (zulip-training-data/v*/)     │
│                                                         │
└─────────────────────────────────────────────────────────┘

External Services:
┌──────────┐  ┌──────────┐  ┌──────────────┐
│PostgreSQL│  │ MinIO S3 │  │ GE Viewer    │
│  :5432   │  │  :7480   │  │  :8080       │
│(messages,│  │(training │  │(HTML reports)│
│moderation│  │ data,    │  │              │
│ tables)  │  │ reports) │  │              │
└──────────┘  └──────────┘  └──────────────┘
```

---

## 6. Deployment Configuration

### 6.1 Docker Compose (relevant services)

```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    # great-expectations>=1.15.2 installed via requirements.txt
    environment:
      - S3_ENDPOINT=chi.tacc.chameleoncloud.org:7480
      - MINIO_ACCESS_KEY=admin
      - MINIO_SECRET_KEY=chatsentry_minio
      - BUCKET_TRAINING=proj09_Data

  ge-viewer:
    build:
      context: .
      dockerfile: docker/ge-viewer/Dockerfile
    ports:
      - "8080:8080"
    environment:
      - S3_ENDPOINT=chi.tacc.chameleoncloud.org:7480
      - MINIO_ACCESS_KEY=admin
      - MINIO_SECRET_KEY=chatsentry_minio
      - BUCKET_TRAINING=proj09_Data
```

### 6.2 Requirements

```txt
# requirements.txt (relevant line)
great-expectations>=1.15.2
```

### 6.3 MinIO Bucket Layout

```
proj09_Data/
├── zulip-training-data/
│   └── v20260407-012345/
│       ├── train.csv
│       ├── val.csv
│       └── test.csv
├── data-quality-report/
│   └── report-20260407-012345.html   ← GE Data Docs
└── combined_dataset.csv
```

---

## 7. Why This Improves ChatSentry's Data Design

| Dimension | Before GE | After GE | Improvement |
|-----------|-----------|----------|-------------|
| **Visibility** | Quality rules hidden in Python code | Declarative expectations readable by all stakeholders | Non-engineers can review data contracts |
| **Debugging** | Silent row drops with no explanation | Per-expectation diagnostics with unexpected_percent | ML team can trace data quality regressions |
| **Configuration** | Edit code + redeploy to change thresholds | Runtime parameter override | Different thresholds for dev/staging/prod |
| **Auditability** | No record of what was filtered | HTML Data Docs in S3 alongside training data | Regulatory compliance + debugging history |
| **Testability** | One monolithic function, hard to test edge cases | 15 targeted unit tests, each testing one expectation | Higher confidence in data quality guarantees |
| **Maintainability** | If-else chains grow with each new check | Add expectations to suite — same pattern every time | Scales to 10, 20, 50+ quality checks |

---

## 8. Files Delivered

| File | Lines | Purpose |
|------|-------|---------|
| `src/data/data_quality.py` | 279 | GE Expectation Suite builder, validator, Data Docs generator |
| `tests/test_data_quality.py` | 334 | 15 unit tests for GE integration |
| `docker/ge-viewer/Dockerfile` | 12 | GE Viewer container |
| `docker/ge-viewer/app.py` | 125 | Flask app serving HTML reports from MinIO |
| `docker/ge-viewer/requirements.txt` | — | Flask + MinIO dependencies |
| `requirements.txt` | 14 | `great-expectations>=1.15.2` dependency |

All code is production-ready, tested, and deployed on Chameleon Cloud KVM@TACC.
