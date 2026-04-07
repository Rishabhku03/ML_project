# ChatSentry Data Pipeline — Artifact Documentation

**Project:** ChatSentry AI-Powered Content Moderation — Data Pipeline
**Author:** Rishabh Narayan (Data Specialist)
**Repository:** `Ml_Project`
**Infrastructure:** Chameleon Cloud KVM@TACC (m1.xlarge — 4 vCPU / 16GB RAM, no GPU)

---

## 1. Pipeline Overview

This artifact documents a **reproducible data pipeline** that:

1. **Ingests** the `combined_dataset.csv` (1,586,127 rows, 218MB) of toxic/suicide detection data into Chameleon S3 object storage
2. **Transforms** raw text through a 5-step cleaning pipeline (Unicode normalization, Markdown stripping, URL extraction, emoji standardization, PII scrubbing)
3. **Validates** training data with Great Expectations (6 declarative quality checks)
4. **Expands** the dataset synthetically using a local Qwen2.5-1.5B model (10K labeled rows, minority-class oversampled)
5. **Compiles** versioned train/val/test splits (70/15/15 stratified) and uploads to S3 for the ML training team

All components run on a single Chameleon VM via Docker Compose.

---

## 2. Artifact Inventory

### 2.1 Infrastructure — Docker

| File | Purpose |
|------|---------|
| `docker/docker-compose.yaml` | Orchestrates 4 services: PostgreSQL 18, Adminer (DB GUI), FastAPI API server, GE Viewer (Flask quality report viewer) |
| `docker/Dockerfile.api` | Python 3.12-slim image, installs dependencies, copies `src/`, runs `uvicorn src.api.main:app` |
| `docker/ge-viewer/Dockerfile` | Python 3.12-slim, Flask app that fetches and renders GE HTML reports from S3 |
| `docker/ge-viewer/app.py` | Flask app serving GE Data Docs from MinIO `data-quality-report/` prefix |
| `docker/init_sql/00_create_tables.sql` | Creates 4 PostgreSQL tables: `users`, `messages`, `flags`, `moderation` with GIN full-text index |
| `docker/init_sql/01_seed_data.sql` | Seeds one default user for the batch pipeline |
| `docker/.env.example` | Template for S3 credentials (`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_ENDPOINT`) |

**docker-compose.yaml services:**

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5432 | PostgreSQL 18 — application state, messages, moderation decisions |
| `adminer` | 5050 | Web GUI for PostgreSQL queries and inspection |
| `api` | 8000 | FastAPI application — message ingestion, text cleaning, inference API |
| `ge-viewer` | 8080 | Flask app serving Great Expectations HTML quality reports |

**How to reproduce:**
```bash
cd docker/
cp .env.example .env  # Fill in Chameleon S3 credentials
docker compose up -d
```

---

### 2.2 Data Ingestion — `src/data/ingest_and_expand.py`

**Purpose:** Reads `combined_dataset.csv` in 50,000-row chunks and uploads each as a CSV to Chameleon S3.

**Key design decisions:**
- CSV format preserved (no Parquet) for broad compatibility
- Chunk size of 50K rows balances memory usage and upload reliability
- Uploaded to `proj09_Data/zulip-raw-messages/real/combined_dataset/chunk_NNN.csv`
- Does NOT load into PostgreSQL (that happens in the compilation step)
- Memory freed after each chunk upload (explicit `del`)

**Input:** Local CSV file (1,586,127 rows, ~218MB)
**Output:** 8 CSV chunks in Chameleon S3, each ~33MB

**Usage:**
```bash
docker exec api python3 -m src.data.ingest_and_expand /path/to/combined_dataset.csv
```

---

### 2.3 Text Cleaning — `src/data/text_cleaner.py`

**Purpose:** Shared text cleaning pipeline used by both online (API middleware) and batch (compilation) paths.

**5-step pipeline (executed in order):**

| Step | Function | Transformation | Example |
|------|----------|---------------|---------|
| 1 | `fix_unicode()` | Normalize encoding via `ftfy` | `cafÃ©` → `café` |
| 2 | `strip_markdown()` | Remove HTML tags + Markdown markers | `**bold**` → `bold` |
| 3 | `extract_urls()` | Replace URLs with `[URL]` | `https://evil.com` → `[URL]` |
| 4 | `standardize_emojis()` | Convert emojis to `:shortcode:` | `😊` → `:smiling_face_with_smiling_eyes:` |
| 5 | `scrub_pii()` | Replace email/phone/@username with placeholders | `user@email.com` → `[EMAIL]` |

**PII patterns (regex):**
- Email: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}` → `[EMAIL]`
- Phone: US-style `(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` → `[PHONE]`
- Username: `@\w+` → `[USER]`

**Also used in real-time** by `TextCleaningMiddleware` in `src/api/middleware.py` — same pipeline, applied to every incoming API request before inference.

---

### 2.4 Batch Compilation — `src/data/compile_training_data.py`

**Purpose:** Compiles versioned training datasets from either raw CSV chunks (initial mode) or PostgreSQL (incremental mode).

**Two modes:**

#### `compile_initial()` — First-time load
1. List CSV chunks from S3 `zulip-raw-messages/real/combined_dataset/`
2. Concatenate into single DataFrame
3. Apply TextCleaner to produce `cleaned_text` column
4. Bulk-load into PostgreSQL `messages` + `moderation` tables
5. Select output columns: `cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`
6. Run Great Expectations validation (6 checks) + upload HTML report to S3
7. Apply quality gate:
   - Remove rows containing `#ERROR!` (corrupt data)
   - Drop rows with `cleaned_text < 10` chars (noise)
   - Truncate rows with `cleaned_text > 5000` chars (outliers)
8. Stratified 70/15/15 train/val/test split (stratified on label combination)
9. Upload versioned snapshot to S3: `zulip-training-data/vYYYYMMDD-HHMMSS/{train,val,test}.csv`

#### `compile_incremental()` — Subsequent runs
1. Query PostgreSQL with temporal leakage prevention (`created_at < decided_at`)
2. Apply TextCleaner fallback for NULL `cleaned_text`
3. Steps 5–9 same as initial mode

**Key functions:**

| Function | Purpose |
|----------|---------|
| `filter_temporal_leakage()` | Removes rows where moderation decision precedes message creation |
| `apply_quality_gate()` | Filters corrupt/noisy data per DATA_ISSUES.md |
| `select_output_columns()` | Ensures consistent 5-column output schema |
| `stratified_split()` | Two-step 70/15/15 split with stratification on `is_suicide`+`is_toxicity` combo |
| `generate_version()` | Creates UTC timestamp version tag `vYYYYMMDD-HHMMSS` |
| `upload_snapshot()` | Uploads train/val/test CSVs to S3 under versioned prefix |

**Usage:**
```bash
# Initial (auto-detected if PostgreSQL is empty)
docker exec api python3 -m src.data.compile_training_data

# Or explicitly:
docker exec -d api python3 -c "from src.data.compile_training_data import compile_initial; compile_initial()"
```

---

### 2.5 Data Quality — `src/data/data_quality.py`

**Purpose:** Great Expectations integration for declarative data quality validation.

**6 Expectation checks:**

| # | Check | Column | Rule | Severity |
|---|-------|--------|------|----------|
| 1 | Required column | `cleaned_text` | Column must exist | Error |
| 2 | Text length bounds | `cleaned_text` | Length between 10–5000 chars | Warning |
| 3 | No corrupt data | `cleaned_text` | Must not match `#ERROR!` pattern | Warning |
| 4 | Valid labels | `is_suicide` | Values must be 0 or 1 | Error |
| 5 | Class balance | `is_toxicity` | Mean between 2–8% (minority class check) | Warning |
| 6 | No nulls | `cleaned_text` | Must not be null | Error |

**Output:** HTML Data Docs report uploaded to S3 at `data-quality-report/report-YYYYMMDD-HHMMSS.html`, viewable via the GE Viewer Flask app.

**Design decision:** Validation failures at WARNING level do NOT halt the pipeline — they log warnings and the ML team reviews the HTML report separately. Only ERROR-level failures would stop execution.

---

### 2.6 Synthetic Data Expansion — `src/data/synthetic_generator.py`

**Purpose:** Generates labeled synthetic text data to expand the dataset beyond its 1.58M rows (required because dataset < 5GB per course guidelines).

**Model:** Qwen2.5-1.5B (1.5B parameter causal LM, runs locally on CPU via HuggingFace Transformers)

**Label distribution (oversamples minority classes):**

| Label | Proportion | Rows (of 10K target) |
|-------|-----------|---------------------|
| `toxic` | 30% | ~3,000 |
| `suicide` | 30% | ~3,000 |
| `benign` | 40% | ~4,000 |

**Two modes:**

| Mode | Command | Behavior |
|------|---------|----------|
| `training` | `--mode training --count 10000` | Generates labeled CSV, uploads to S3 `zulip-raw-messages/synthetic/synthetic_data.csv` |
| `test` | `--mode test --count 10 --label toxic` | Generates messages one-at-a-time, POSTs to API endpoint for traffic simulation |

**Prompt templates** (`src/data/prompts.py`): Few-shot prompts with real dataset examples for each label type. Each prompt asks the model to generate 10 numbered messages.

**Output columns:** `text`, `is_suicide`, `is_toxicity`

**Usage:**
```bash
# Generate 10K synthetic training rows
docker exec api python3 -m src.data.synthetic_generator --mode training --count 10000

# Generate 100 rows for demo
docker exec api python3 -m src.data.synthetic_generator --mode training --count 100

# Simulate traffic (10 messages, 2s apart)
docker exec api python3 -m src.data.synthetic_generator --mode test --count 10 --interval 2
```

---

### 2.7 Configuration — `config/pipeline.yaml`

All pipeline parameters are centralized:

```yaml
ingestion:
  chunk_size: 50000            # Rows per CSV chunk
  synthetic_target_rows: 10000 # Synthetic expansion target

quality:
  min_text_length: 10          # Drop rows shorter than this
  max_text_length: 5000        # Truncate rows longer than this
  error_pattern: "#ERROR!"     # Remove matching rows

split:
  train_ratio: 0.70
  val_ratio: 0.15
  test_ratio: 0.15
  random_state: 42             # Reproducibility seed

buckets:
  raw: proj09_Data             # Chameleon S3 bucket
  training: proj09_Data        # Same bucket, different prefixes
```

Overridable via environment variables. Loaded by `src/utils/config.py`.

---

### 2.8 API Layer — `src/api/`

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app with endpoints: `GET /health`, `POST /messages`, `POST /flags`, `POST /admin/flush` |
| `middleware.py` | `TextCleaningMiddleware` — applies the same 5-step TextCleaner pipeline to every incoming request |
| `models.py` | Pydantic schemas: `MessagePayload`, `MessageResponse`, `FlagPayload`, `FlagResponse` |
| `routes/messages.py` | `POST /messages` — receives message, cleans text, stores in PostgreSQL + buffers to S3 |
| `routes/flags.py` | `POST /flags` — receives moderation flag, stores in PostgreSQL |
| `routes/dashboard.py` | `GET /dashboard` — HTML labeling interface for manual data annotation |

---

### 2.9 Utilities — `src/utils/`

| File | Purpose |
|------|---------|
| `config.py` | Frozen dataclass loading from `config/pipeline.yaml` + env vars. All pipeline tunables. |
| `minio_client.py` | Factory function returning configured MinIO client (Chameleon S3 endpoint) |
| `db.py` | Factory function returning psycopg2 PostgreSQL connection |

---

### 2.10 Tests — `tests/`

**Unit tests (14 files, 85/88 passing):**

| File | Tests |
|------|-------|
| `test_text_cleaner.py` | 13 tests covering all 5 cleaning steps, full pipeline, edge cases |
| `test_compile_training_data.py` | 12 tests: quality gate, temporal leakage, output schema, split proportions, version format |
| `test_data_quality.py` | GE validation tests |
| `test_synthetic_gen.py` | Synthetic generator tests |
| `test_csv_chunking.py` | CSV chunking tests |
| `test_config.py` | Configuration loading tests |
| `test_schema.py` | Schema validation tests |
| `test_middleware.py` | Middleware tests |
| 6 more files | Various component tests |

**E2E tests (5 layers):**

| Layer | Purpose |
|-------|---------|
| `test_01_infrastructure/` | Docker service health checks |
| `test_02_data_flow/` | Pipeline stage tests: ingestion, cleaning, compilation, splitting |
| `test_03_data_quality/` | GE validation + quality gate |
| `test_04_chaos/` | Failure injection: storage failures, container crashes, DB failures |
| `test_05_full_pipeline/` | Full end-to-end: small/medium pipeline runs, idempotency |

3 unit tests require Docker infrastructure to be running.

---

## 3. Data Flow Diagram

```
combined_dataset.csv (218MB, 1.58M rows)
        │
        ▼
┌─────────────────────┐
│  ingest_and_expand   │  Read in 50K chunks → upload to S3
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  S3: zulip-raw-messages/real/combined_dataset/  │
│  chunk_000.csv ... chunk_007.csv                │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────┐     ┌──────────────────────┐
│ synthetic_generator  │────▶│ S3: zulip-raw-       │
│ (Qwen2.5-1.5B)      │     │ messages/synthetic/  │
└──────────────────────┘     └──────────┬───────────┘
                                        │
          ┌─────────────────────────────┘
          ▼
┌─────────────────────────┐
│  compile_training_data   │
│  1. Read CSV chunks      │
│  2. TextCleaner (5 steps)│
│  3. Bulk-load PostgreSQL │
│  4. GE validation        │
│  5. Quality gate         │
│  6. Stratified split     │
└─────────┬───────────────┘
          │
          ▼
┌──────────────────────────────────────────────┐
│  S3: zulip-training-data/vYYYYMMDD-HHMMSS/  │
│  ├── train.csv (70%)                        │
│  ├── val.csv (15%)                          │
│  └── test.csv (15%)                         │
└──────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────┐
│  S3: data-quality-report/report-*.html       │
│  (viewable via GE Viewer at port 8080)       │
└──────────────────────────────────────────────┘
```

**Real-time path (parallel):**
```
Zulip webhook → POST /messages → TextCleaningMiddleware → PostgreSQL + S3 buffer
```

---

## 4. Reproducibility Instructions

### Prerequisites
- Chameleon Cloud account with access to KVM@TACC
- SSH key configured for VM access
- S3 credentials for `proj09_Data` bucket

### Steps to reproduce

**1. Provision VM and S3** (via `Chameleon_deploy.ipynb`)
- Create lease, launch VM, configure security groups
- Create S3 bucket `proj09_Data`

**2. Deploy services**
```bash
# SSH into VM
ssh -i ~/.ssh/id_rsa_chameleon cc@<VM_IP>

# Clone repo, configure credentials
cd chatsentry
cp docker/.env.example docker/.env  # Fill in S3 credentials

# Start all services
cd docker && docker compose up -d
```

**3. Upload dataset**
```bash
# From local machine
scp -i ~/.ssh/id_rsa_chameleon combined_dataset.csv cc@<VM_IP>:/home/cc/chatsentry/combined_dataset.csv/combined_dataset.csv

# Copy into container
docker cp /home/cc/chatsentry/combined_dataset.csv/combined_dataset.csv api:/tmp/combined_dataset.csv
```

**4. Run pipeline**
```bash
# Ingest CSV → S3
docker exec api python3 -m src.data.ingest_and_expand /tmp/combined_dataset.csv

# Compile training data (CSV → clean → PostgreSQL → split → S3)
docker exec -d api python3 -c "from src.data.compile_training_data import compile_initial; compile_initial()"

# Generate synthetic data (optional, for expansion)
docker exec api python3 -m src.data.synthetic_generator --mode training --count 10000
```

**5. Verify**
```bash
# Check PostgreSQL
docker exec postgres psql -U user -d chatsentry -c "SELECT COUNT(*) FROM messages;"

# Check S3
docker exec api python3 -c "from minio import Minio; import os; c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region=''); [print(o.object_name) for o in c.list_objects('proj09_Data', recursive=True)]"
```

---

## 5. Artifact File Listing

```
Ml_Project/
├── src/
│   ├── data/
│   │   ├── ingest_and_expand.py       # CSV → S3 ingestion
│   │   ├── text_cleaner.py            # 5-step text cleaning pipeline
│   │   ├── compile_training_data.py   # Batch compilation + split
│   │   ├── data_quality.py            # Great Expectations validation
│   │   ├── synthetic_generator.py     # Synthetic data generation
│   │   ├── prompts.py                 # Few-shot prompt templates
│   │   └── __init__.py
│   ├── api/
│   │   ├── main.py                    # FastAPI application
│   │   ├── middleware.py              # Text cleaning middleware
│   │   ├── models.py                  # Pydantic schemas
│   │   └── routes/
│   │       ├── messages.py
│   │       ├── flags.py
│   │       └── dashboard.py
│   └── utils/
│       ├── config.py                  # Configuration loader
│       ├── minio_client.py            # S3 client factory
│       └── db.py                      # PostgreSQL client factory
├── docker/
│   ├── docker-compose.yaml            # Service orchestration
│   ├── Dockerfile.api                 # API container image
│   ├── ge-viewer/
│   │   ├── Dockerfile                 # GE Viewer container image
│   │   └── app.py                     # Flask GE report viewer
│   ├── init_sql/
│   │   ├── 00_create_tables.sql       # Schema DDL
│   │   └── 01_seed_data.sql           # Seed data
│   └── .env.example                   # Credentials template
├── config/
│   └── pipeline.yaml                  # Pipeline configuration
├── tests/                             # Unit + E2E test suite
│   ├── test_text_cleaner.py
│   ├── test_compile_training_data.py
│   ├── test_data_quality.py
│   ├── test_synthetic_gen.py
│   ├── test_csv_chunking.py
│   ├── test_config.py
│   ├── test_schema.py
│   ├── test_middleware.py
│   └── e2e/
│       ├── test_01_infrastructure/
│       ├── test_02_data_flow/
│       ├── test_03_data_quality/
│       ├── test_04_chaos/
│       └── test_05_full_pipeline/
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata + tool config
└── combined_dataset.csv               # Source dataset (1.58M rows)
```
