# ChatSentry — Online Feature Computation & Batch Training Data Pipeline Artifact

**Requirements:**
1. Online feature computation path for real-time inference (integrate-able with open source chat service)
2. Batch pipeline that compiles versioned training/evaluation datasets from "production" data, with candidate selection and data leakage prevention

**Project:** ChatSentry AI-Powered Content Moderation — Data Pipeline
**Author:** Rishabh Narayan (Data Specialist)
**Repository:** `Ml_Project`
**Infrastructure:** Chameleon Cloud KVM@TACC (m1.xlarge — 4 vCPU / 16GB RAM, no GPU)

---

## 1. Overview

This artifact documents two complementary data pipeline components:

1. **Online Feature Computation Path** — A real-time text preprocessing service that intercepts every incoming chat message at the API layer, applies a 5-step cleaning pipeline, and returns cleaned features for ML inference. Designed to integrate with any chat platform (Zulip, Slack, Discord) via standard HTTP POST webhooks.

2. **Batch Training Data Compiler** — A pipeline that compiles versioned training and evaluation datasets from production PostgreSQL data, with temporal leakage prevention, Great Expectations quality validation, and stratified 70/15/15 train/val/test splitting.

Both paths share the same `TextCleaner` class, guaranteeing identical text transformations whether processing one message in real-time or 1.58 million in batch.

---

## 2. Artifact Inventory

### 2.1 Online Feature Computation — TextCleaner Pipeline

**File:** `src/data/text_cleaner.py`

**Purpose:** Shared text cleaning pipeline used by both online (API middleware) and batch (compilation) paths. Applied to every incoming message before ML inference.

**5-step pipeline (executed in order per D-06):**

| Step | Function | Transformation | Example |
|------|----------|---------------|---------|
| 1 | `fix_unicode()` | Normalize encoding via `ftfy` | `cafÃ©` → `café` |
| 2 | `strip_markdown()` | Remove HTML tags + Markdown markers | `**bold**` → `bold` |
| 3 | `extract_urls()` | Replace URLs with `[URL]` | `https://evil.com` → `[URL]` |
| 4 | `standardize_emojis()` | Convert emojis to `:shortcode:` | `😊` → `:smiling_face_with_smiling_eyes:` |
| 5 | `scrub_pii()` | Replace email/phone/@username with placeholders | `user@email.com` → `[EMAIL]` |

**PII regex patterns:**
- Email: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b` → `[EMAIL]`
- Phone: `(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` → `[PHONE]`
- Username: `@\w+` → `[USER]`

**Key class:**
```python
@dataclass
class TextCleaner:
    steps: list[Callable[[str], str]]  # Ordered cleaning functions

    def clean(self, text: str) -> str:
        """Apply all cleaning steps sequentially."""
        for step in self.steps:
            text = step(text)
        return text
```

**Design decisions:**
- Pipeline order matters: Unicode fix before Markdown strip (fixes encoding in tags), URL extraction before PII scrub (avoids matching emails in URLs)
- Custom steps list allows restricting pipeline for specific use cases
- Stateless — no side effects, safe for concurrent requests

---

### 2.2 Online Feature Computation — FastAPI Middleware

**File:** `src/api/main.py` (lines 26–60)

**Purpose:** HTTP middleware that intercepts POST requests to `/messages` and `/flags`, applies the TextCleaner pipeline, and persists both raw and cleaned text to PostgreSQL.

**Integration architecture:**
```
Chat Service (Zulip/Slack)
    │
    │  POST /messages {text, user_id}
    ▼
┌─────────────────────────────────────────────┐
│ FastAPI TextCleaningMiddleware               │
│  1. Parse JSON body                          │
│  2. TextCleaner.clean(raw_text)             │
│  3. _persist_message() → PostgreSQL          │
│  4. _buffer_for_minio() → S3 (batch flush)   │
│  5. Forward to route handler                 │
└─────────────────────────────────────────────┘
    │
    ▼
{status, message_id, raw_text, cleaned_text}
```

**API endpoints:**

| Method | Path | Purpose | Integration point |
|--------|------|---------|-------------------|
| POST | `/messages` | Accept message, clean, store | Zulip outgoing webhook |
| POST | `/flags` | Accept moderation flag, clean reason | Manual flagging UI |
| GET | `/health` | Service health check | Load balancer / monitoring |
| POST | `/admin/flush` | Force-flush MinIO buffer | Testing / ops |
| GET | `/dashboard` | Labeling UI for manual annotation | Data quality team |

**Request/Response schema (Pydantic models in `src/api/models.py`):**

```python
class MessagePayload(BaseModel):
    text: str        # Raw message text (1–10,000 chars)
    user_id: str     # UUID of sending user
    source: str = "real"  # "real" or "synthetic_hf"

class MessageResponse(BaseModel):
    status: str = "accepted"
    message_id: str
    raw_text: str     # Original text (D-13)
    cleaned_text: str  # Cleaned text after middleware (D-13)
```

**Integration with Zulip:**
Zulip's outgoing webhook system sends a POST request to a configured URL when a message is posted. ChatSentry's `/messages` endpoint accepts this format directly. No code changes needed on the Zulip side — just configure the webhook URL to point to `http://<vm-ip>:8000/messages`.

**MinIO buffering:**
Cleaned messages are buffered in-memory and flushed to S3 as JSONL batches every 10,000 records (configurable via `config.MINIO_BATCH_UPLOAD_SIZE`). This provides durable storage for the batch pipeline to consume.

---

### 2.3 Batch Pipeline — Training Data Compiler

**File:** `src/data/compile_training_data.py`

**Purpose:** Compiles versioned training datasets from production data in PostgreSQL, with temporal leakage prevention and quality validation.

**Two modes:**

#### `compile_initial()` — First-time load from CSV
1. List CSV chunks from S3 `zulip-raw-messages/real/combined_dataset/`
2. Concatenate into single DataFrame (1.58M rows)
3. Apply TextCleaner to produce `cleaned_text` column
4. Bulk-load into PostgreSQL `messages` + `moderation` tables
5. Select output columns: `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`
6. Run Great Expectations validation (6 checks) + upload HTML report to S3
7. Apply quality gate (remove #ERROR!, filter <10 chars, cap >5000 chars)
8. Stratified 70/15/15 train/val/test split
9. Upload versioned snapshot to S3

#### `compile_incremental()` — Subsequent runs from PostgreSQL
1. Query PostgreSQL with temporal leakage prevention
2. Apply TextCleaner fallback for NULL `cleaned_text`
3. Steps 5–9 same as initial mode

**Key design decisions:**

**Temporal Leakage Prevention (D-04, D-05):**
The incremental query enforces `created_at < decided_at`:
```sql
SELECT m.id, COALESCE(m.cleaned_text, m.text) AS cleaned_text,
       m.is_suicide, m.is_toxicity, m.source, m.created_at, mod.decided_at
FROM messages m
INNER JOIN moderation mod ON m.id = mod.message_id
WHERE m.created_at < mod.decided_at
ORDER BY m.created_at
```
This ensures a message can only appear in training data if the moderation decision was made AFTER the message was created. A defense-in-depth filter `filter_temporal_leakage()` also applies this check in Python.

**Candidate Selection:**
Only messages with a moderation decision (INNER JOIN with `moderation` table) enter the training set. Unmoderated messages are excluded. The quality gate further filters:
- Remove rows with `#ERROR!` pattern (corrupt data, 262 rows identified in DATA_ISSUES.md Issue 4)
- Drop rows with `cleaned_text < 10` characters (noise, Issue 5)
- Truncate rows with `cleaned_text > 5000` characters (outliers, Issue 5)

**Stratified Split (D-12 through D-14):**
Two-step 70/15/15 split with stratification on the combined label (`is_suicide` + `is_toxicity`):
- Step 1: 70% train, 30% temp (stratified)
- Step 2: Split 30% evenly into 15% val, 15% test (stratified)
- Empty stratification classes are filtered before splitting (handles the `1_1` class with 0 rows)

**Versioning (D-09):**
Each compilation produces a UTC timestamped folder: `zulip-training-data/vYYYYMMDD-HHMMSS/{train,val,test}.csv`

**Key functions:**

| Function | Purpose |
|----------|---------|
| `filter_temporal_leakage(df)` | Remove rows where `created_at >= decided_at` |
| `apply_quality_gate(df)` | Filter corrupt/noisy data per DATA_ISSUES.md |
| `select_output_columns(df)` | Ensure 5-column output: cleaned_text, is_suicide, is_toxicity, source, message_id |
| `stratified_split(df)` | 70/15/15 split with label stratification |
| `generate_version()` | Create UTC timestamp version tag |
| `upload_snapshot(client, bucket, train, val, test)` | Upload split CSVs to S3 |

**Usage:**
```bash
# Auto-detect mode (checks if PostgreSQL is empty)
docker exec api python3 -m src.data.compile_training_data

# Explicit initial mode
docker exec -d api python3 -c "from src.data.compile_training_data import compile_initial; compile_initial()"

# Explicit incremental mode
docker exec api python3 -c "from src.data.compile_training_data import compile_incremental; compile_incremental()"
```

---

### 2.4 Data Quality Validation — Great Expectations

**File:** `src/data/data_quality.py`

**Purpose:** Declarative data quality validation using Great Expectations, replacing hand-coded quality checks.

**6 Expectation checks:**

| # | Check | Column | Rule | Severity |
|---|-------|--------|------|----------|
| 1 | Required Column Present | `cleaned_text` | Column must exist | Error |
| 2 | Text Length Within Bounds | `cleaned_text` | Length between 10–5000 chars | Warning |
| 3 | No Corrupt Data | `cleaned_text` | Must not match `#ERROR!` pattern | Warning |
| 4 | Valid Label Values | `is_suicide` | Values must be 0 or 1 | Error |
| 5 | Class Balance Ratio | `is_toxicity` | Mean between 2–8% | Warning |
| 6 | No Missing Values | `cleaned_text` | Must not be null | Error |

**Design decision:** WARNING-level failures do NOT halt the pipeline — they log warnings and the ML team reviews the HTML report separately. This follows the "warn and continue" approach (D-03).

**Output:** HTML Data Docs report uploaded to S3 at `data-quality-report/report-YYYYMMDD-HHMMSS.html`, viewable via the GE Viewer Flask app on port 8080.

---

### 2.5 Docker Infrastructure

**File:** `docker/docker-compose.yaml`

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5432 | PostgreSQL 18 — application state, messages, moderation decisions |
| `adminer` | 5050 | Web GUI for PostgreSQL queries |
| `api` | 8000 | FastAPI — message ingestion, text cleaning, online feature computation |
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

### 2.6 PostgreSQL Schema

**File:** `docker/init_sql/00_create_tables.sql`

4 tables with UUID primary keys, source tracking, and timestamps:

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `users` | Chat users | id, username, source |
| `messages` | Chat messages | id, user_id, text, cleaned_text, is_toxicity, is_suicide, source, created_at |
| `flags` | Moderation flags | id, message_id, flagged_by, reason, is_verified, created_at |
| `moderation` | Moderation decisions | id, message_id, action, confidence, model_version, decided_at |

**Key indexes:**
- GIN full-text search index on `messages.text`
- Foreign key constraints: `messages.user_id → users.id`, `flags.message_id → messages.id`, `moderation.message_id → messages.id`

---

### 2.7 Configuration

**File:** `config/pipeline.yaml`

```yaml
ingestion:
  chunk_size: 50000
  synthetic_target_rows: 10000

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
  raw: proj09_Data
  training: proj09_Data

batch:
  upload_size: 10000
```

Loaded by `src/utils/config.py` as a frozen dataclass. Environment variables override secrets (S3 credentials, database URL).

---

### 2.8 Tests

**Unit tests relevant to Part 3:**

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_text_cleaner.py` | 13 tests | All 5 cleaning steps, full pipeline, custom steps, edge cases, no side effects |
| `tests/test_compile_training_data.py` | 12 tests | GE validation, quality gate, temporal leakage, output schema, stratified split, version format |
| `tests/test_data_quality.py` | GE validation tests | Expectation suite building, validation pass/fail |
| `tests/test_middleware.py` | Middleware tests | Request interception, text cleaning integration |

**Key test commands:**
```bash
# TextCleaner pipeline
docker exec api python3 -m pytest tests/test_text_cleaner.py -v

# Batch compilation pipeline
docker exec api python3 -m pytest tests/test_compile_training_data.py -v

# Data quality validation
docker exec api python3 -m pytest tests/test_data_quality.py -v
```

**E2E tests (require running Docker infrastructure):**

| File | Covers |
|------|--------|
| `tests/e2e/test_02_data_flow/test_compilation.py` | Initial mode upload, temporal leakage, quality gate, PostgreSQL insert/query |
| `tests/e2e/test_02_data_flow/test_text_cleaning.py` | Text cleaning against live services |
| `tests/e2e/test_03_data_quality/test_quality_gates.py` | GE validation against live data |
| `tests/e2e/test_05_full_pipeline/test_full_pipeline_small.py` | Small end-to-end pipeline run |

---

## 3. Data Flow Diagram

### Online Path (Real-Time Inference)
```
Chat Service (Zulip)
    │
    │  POST /messages {text, user_id}
    ▼
┌─────────────────────────────────────────────┐
│ FastAPI TextCleaningMiddleware               │
│                                              │
│  TextCleaner.clean(raw_text):                │
│    1. fix_unicode()    → normalize encoding  │
│    2. strip_markdown() → remove formatting   │
│    3. extract_urls()   → URLs → [URL]        │
│    4. standardize_emojis() → :shortcodes:    │
│    5. scrub_pii()      → [EMAIL]/[PHONE]/[USER]│
│                                              │
│  → PostgreSQL (raw + cleaned text)           │
│  → MinIO buffer (JSONL batch flush)          │
│  → Response: {cleaned_text, message_id}      │
└─────────────────────────────────────────────┘
```

### Batch Path (Training Data Compilation)
```
PostgreSQL (production data)
    │
    │  INCREMENTAL_QUERY:
    │  SELECT messages + moderation
    │  WHERE created_at < decided_at  ← leakage prevention
    ▼
┌─────────────────────────────────────────────┐
│ compile_incremental()                        │
│                                              │
│  1. Temporal leakage filter (defense-in-depth)│
│  2. TextCleaner fallback (NULL cleaned_text) │
│  3. Select output columns (5 columns)        │
│  4. GE validation (6 checks → HTML report)   │
│  5. Quality gate (#ERROR!, length bounds)     │
│  6. Stratified 70/15/15 split                │
│  7. Upload versioned snapshot to S3           │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ S3: zulip-training-data/vYYYYMMDD-HHMMSS/   │
│  ├── train.csv (70%)                         │
│  ├── val.csv (15%)                           │
│  └── test.csv (15%)                          │
│                                              │
│ S3: data-quality-report/report-*.html        │
└─────────────────────────────────────────────┘
```

---

## 4. Integration Guide (How to Connect a Chat Service)

The online feature computation path is designed to be integrate-able with any chat service that supports outgoing webhooks.

### 4.1 Zulip Integration

1. Go to Zulip Settings → Bots → Add a new bot (Outgoing webhook)
2. Set the endpoint URL to `http://<vm-ip>:8000/messages`
3. Configure the payload format:
   ```json
   {"text": "{content}", "user_id": "{sender_id}"}
   ```
4. Messages posted in the configured stream will trigger POST requests to ChatSentry
5. The response contains `cleaned_text` ready for ML inference

### 4.2 Generic HTTP Integration

Any service that can send an HTTP POST with JSON body can integrate:

```bash
curl -X POST http://<vm-ip>:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "raw message text", "user_id": "user-123"}'
```

**Response:**
```json
{
  "status": "accepted",
  "message_id": "uuid-here",
  "raw_text": "raw message text",
  "cleaned_text": "raw message text"
}
```

### 4.3 Docker Deployment

```bash
cd docker/
cp .env.example .env  # Fill in S3 credentials
docker compose up -d
```

The API is available at `http://<vm-ip>:8000` with Swagger docs at `/docs`.

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

**2. Run online feature computation (test via curl)**
```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "**Test** @admin email@test.com https://example.com 😂", "user_id": "test-user"}'
```

**3. Run batch pipeline**
```bash
# Initial load (if PostgreSQL is empty)
docker exec -d api python3 -c "from src.data.compile_training_data import compile_initial; compile_initial()"

# Incremental (if PostgreSQL has data)
docker exec api python3 -c "from src.data.compile_training_data import compile_incremental; compile_incremental()"
```

**4. Verify**
```bash
# Check PostgreSQL
docker exec postgres psql -U user -d chatsentry -c "SELECT COUNT(*) FROM messages;"

# Check S3 for versioned training data
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for obj in c.list_objects('proj09_Data', prefix='zulip-training-data/', recursive=True):
    print(obj.object_name)
"

# Run tests
docker exec api python3 -m pytest tests/test_text_cleaner.py tests/test_compile_training_data.py -v
```

---

## 6. Design Decisions & Justifications

| Decision | Justification |
|----------|---------------|
| Shared TextCleaner for online + batch | Eliminates training-serving skew; identical transformations in both paths |
| Temporal leakage prevention via SQL WHERE | Only messages created before moderation decision enter training set |
| Defense-in-depth: Python filter + SQL WHERE | SQL handles most cases; Python filter catches edge cases from joins |
| Stratified split on label combination | Preserves rare class proportions (toxic+suicide) across train/val/test |
| GE warnings don't halt pipeline | ML team reviews HTML reports separately; production uptime is prioritized |
| 5-step cleaning order matters | Unicode fix before Markdown (fixes encoding in tags); URL extract before PII (avoids matching emails in URLs) |
| MinIO buffer with 10K flush threshold | Balances write amplification vs data durability for real-time messages |
| UTC timestamp versioning | Globally unique, sortable, human-readable version tags for training snapshots |
| CSV over Parquet | Broader compatibility; no additional dependencies for ML team to consume |
| Quality gate at batch level, not API level | API accepts all messages for production use; quality filtering happens at training time |

---

## 7. Artifact File Listing

```
Ml_Project/
├── src/
│   ├── data/
│   │   ├── text_cleaner.py              # 5-step text cleaning pipeline (shared online+batch)
│   │   ├── compile_training_data.py     # Batch compiler with leakage prevention
│   │   ├── data_quality.py              # Great Expectations validation (6 checks)
│   │   ├── ingest_and_expand.py         # CSV → S3 ingestion
│   │   ├── synthetic_generator.py       # Synthetic data generation
│   │   └── prompts.py                   # Few-shot prompt templates
│   ├── api/
│   │   ├── main.py                      # FastAPI app + TextCleaningMiddleware
│   │   ├── models.py                    # Pydantic request/response schemas
│   │   └── routes/
│   │       ├── messages.py              # POST /messages endpoint
│   │       ├── flags.py                 # POST /flags endpoint
│   │       └── dashboard.py             # GET /dashboard labeling UI
│   └── utils/
│       ├── config.py                    # Configuration loader (pipeline.yaml + env vars)
│       ├── minio_client.py              # S3 client factory
│       └── db.py                        # PostgreSQL connection factory
├── docker/
│   ├── docker-compose.yaml              # 4 services: postgres, api, adminer, ge-viewer
│   ├── Dockerfile.api                   # API container image
│   ├── ge-viewer/
│   │   ├── Dockerfile                   # GE Viewer container image
│   │   └── app.py                       # Flask GE report viewer
│   ├── init_sql/
│   │   ├── 00_create_tables.sql         # PostgreSQL schema DDL
│   │   └── 01_seed_data.sql             # Seed data
│   └── .env.example                     # S3 credentials template
├── config/
│   └── pipeline.yaml                    # Pipeline configuration
├── tests/
│   ├── test_text_cleaner.py             # TextCleaner unit tests (13 tests)
│   ├── test_compile_training_data.py    # Batch pipeline tests (12 tests)
│   ├── test_data_quality.py             # GE validation tests
│   ├── test_middleware.py               # Middleware tests
│   └── e2e/
│       ├── test_02_data_flow/
│       │   ├── test_compilation.py      # Compilation E2E tests
│       │   └── test_text_cleaning.py    # Cleaning E2E tests
│       ├── test_03_data_quality/
│       │   └── test_quality_gates.py    # Quality gate E2E tests
│       └── test_05_full_pipeline/
│           └── test_full_pipeline_small.py
├── requirements.txt                     # Python dependencies
├── pyproject.toml                       # Project metadata + tool config
└── combined_dataset.csv                 # Source dataset (1.58M rows)
```
