# ChatSentry — High-Level Data Design Document

## 1. Overview

ChatSentry is an AI-powered content moderation system for Zulip chat. This document describes the data architecture covering all data repositories, schemas, data flow, versioning, and transformation pipelines.

The system uses three data repositories:
1. **Chameleon Cloud S3** (`proj09_Data`) — Persistent object storage for raw data, training data, and quality reports
2. **PostgreSQL** (`chatsentry`) — Application state for real-time message processing
3. **Docker named volumes** (`hf_cache`) — Model cache persistence

---

## 2. Data Repositories

### 2.1 Chameleon Cloud S3 — `proj09_Data`

**Service:** Ceph RadosGW at CHI@TACC (`chi.tacc.chameleoncloud.org:7480`)

**Type:** S3-compatible object storage (persistent — survives VM deletion)

#### 2.1.1 Raw Data Prefix: `zulip-raw-messages/`

| Sub-prefix | Format | Schema | Written By | When |
|-----------|--------|--------|-----------|------|
| `real/combined_dataset/chunk_NNN.csv` | CSV | `text (str), is_suicide (int), is_toxicity (int)` | `ingest_and_expand.py` | On initial data ingestion (manual) |
| `synthetic/synthetic_data.csv` | CSV | `text (str), is_suicide (int), is_toxicity (int)` | `synthetic_generator.py` | On synthetic generation run (manual) |
| `cleaned/batch-{uuid}.jsonl` | JSONL | `user_id (str), raw_text (str), cleaned_text (str), source (str)` | `api/main.py` (flush) | On `/admin/flush` call (manual or batch) |

**Raw CSV schema (identical for real and synthetic):**
```
text           VARCHAR    # Raw message text
is_suicide     INT        # 0 or 1 — suicide/self-harm label
is_toxicity    INT        # 0 or 1 — toxicity label
```

**Cleaned JSONL schema:**
```
user_id        VARCHAR    # User identifier or "unknown"
raw_text       VARCHAR    # Original unprocessed text
cleaned_text   VARCHAR    # Text after TextCleaner pipeline
source         VARCHAR    # "real" or "synthetic_local"
```

#### 2.1.2 Training Data Prefix: `zulip-training-data/`

| Path | Format | Schema | Written By | When |
|------|--------|--------|-----------|------|
| `v{YYYYMMDD-HHMMSS}/train.csv` | CSV | 5 columns (see below) | `compile_training_data.py` | After quality gate + stratified split |
| `v{YYYYMMDD-HHMMSS}/val.csv` | CSV | Same as train | Same | Same |
| `v{YYYYMMDD-HHMMSS}/test.csv` | CSV | Same as train | Same | Same |

**Training CSV schema (5 columns):**
```
cleaned_text   VARCHAR    # Cleaned message text
is_suicide     INT        # 0 or 1 (normalized from bool if PostgreSQL source)
is_toxicity    INT        # 0 or 1 (normalized from bool if PostgreSQL source)
source         VARCHAR    # "real" or "synthetic_local"
message_id     INT        # Sequential ID or UUID-derived integer
```

**Versioning:** Timestamp-based versions (`v20260406-225153`). Each compilation run creates a new version. Multiple versions can coexist.

#### 2.1.3 Quality Report Prefix: `data-quality-report/`

| Path | Format | Written By | When |
|------|--------|-----------|------|
| `report-{YYYYMMDD-HHMMSS}.html` | HTML | `data_quality.py` | After GE validation in each compilation run |

#### 2.1.4 Model Cache Prefix: `models/`

| Path | Format | Size | Written By | When |
|------|--------|------|-----------|------|
| `models/Qwen2.5-1.5B/` | HuggingFace Hub cache | ~2.9 GB | Manual upload | Model setup |

---

### 2.2 PostgreSQL — `chatsentry`

**Service:** PostgreSQL 18 (Docker container)

**Type:** Relational database (persistent via Docker named volume `postgres_data`)

#### 2.2.1 `users` Table

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username   VARCHAR(255) NOT NULL UNIQUE,
    email      VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source     VARCHAR(32) NOT NULL DEFAULT 'real'
               CHECK (source IN ('real', 'synthetic_hf'))
);
```

| Written By | When | Operation |
|-----------|------|-----------|
| `01_seed_data.sql` | On container init | INSERT seed user `batch_pipeline` |
| `compile_training_data.py` | During initial load | INSERT batch user (ON CONFLICT DO NOTHING) |

#### 2.2.2 `messages` Table

```sql
CREATE TABLE messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id),
    text         TEXT NOT NULL,
    cleaned_text TEXT,
    is_toxicity  BOOLEAN DEFAULT FALSE,
    is_suicide   BOOLEAN DEFAULT FALSE,
    source       VARCHAR(32) NOT NULL DEFAULT 'real'
                 CHECK (source IN ('real', 'synthetic_hf')),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

| Written By | When | Operation |
|-----------|------|-----------|
| `api/main.py` | On POST /messages | INSERT (text, cleaned_text, user_id, source) |
| `compile_training_data.py` | During initial load | Bulk INSERT (text, cleaned_text, is_toxicity, is_suicide, source) |
| `routes/dashboard.py` | On label save | UPDATE (is_toxicity, is_suicide) |

**Index:** GIN full-text search index on `text` column.

#### 2.2.3 `flags` Table

```sql
CREATE TABLE flags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id  UUID NOT NULL REFERENCES messages(id),
    flagged_by  UUID REFERENCES users(id),
    reason      TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    source      VARCHAR(32) NOT NULL DEFAULT 'real'
                CHECK (source IN ('real', 'synthetic_hf')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

| Written By | When | Operation |
|-----------|------|-----------|
| `api/main.py` | On POST /flags | INSERT |

#### 2.2.4 `moderation` Table

```sql
CREATE TABLE moderation (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id    UUID NOT NULL REFERENCES messages(id),
    action        VARCHAR(50) NOT NULL,
    confidence    FLOAT,
    model_version VARCHAR(100),
    source        VARCHAR(32) NOT NULL DEFAULT 'real'
                  CHECK (source IN ('real', 'synthetic_hf')),
    decided_at    TIMESTAMPTZ DEFAULT NOW()
);
```

| Written By | When | Operation |
|-----------|------|-----------|
| `routes/dashboard.py` | On label save | INSERT (action="labeled", confidence=1.0) |
| `compile_training_data.py` | During initial load | Bulk INSERT (action="labeled", confidence=1.0) |

---

### 2.3 Docker Named Volumes

| Volume | Container | Mount Point | Content | Persistent? |
|--------|-----------|-------------|---------|-------------|
| `postgres_data` | postgres | `/var/lib/postgresql` | All PostgreSQL data | Yes (survives `docker compose down`) |
| `hf_cache` | api | `/root/.cache/huggingface` | Qwen2.5-1.5B model files (~2.9 GB) | Yes |

---

## 3. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL DATA SOURCES                              │
│                                                                             │
│  ┌──────────────────┐    ┌────────────────────┐    ┌──────────────────────┐ │
│  │ combined_dataset  │    │ HuggingFace API    │    │ Zulip Chat (live)    │ │
│  │ .csv (218 MB)     │    │ Qwen2.5-1.5B       │    │ POST /messages       │ │
│  │ text, is_suicide, │    │ (local generation)  │    │ POST /flags          │ │
│  │ is_toxicity       │    │                    │    │                      │ │
│  └────────┬─────────┘    └──────────┬─────────┘    └──────────┬───────────┘ │
└───────────┼──────────────────────────┼─────────────────────────┼─────────────┘
            │                          │                         │
            ▼                          ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA INGESTION LAYER                               │
│                                                                             │
│  ┌──────────────────┐    ┌────────────────────┐    ┌──────────────────────┐ │
│  │ ingest_and_expand │    │ synthetic_generator│    │ api/main.py          │ │
│  │ .py              │    │ .py                │    │ TextCleaner pipeline │ │
│  │                  │    │                    │    │                      │ │
│  │ Read CSV chunks  │    │ Generate with      │    │ 1. fix_unicode       │ │
│  │ 50K rows/chunk   │    │ Qwen2.5-1.5B       │    │ 2. strip_markdown    │ │
│  │                  │    │ Few-shot prompting  │    │ 3. extract_urls      │ │
│  └────────┬─────────┘    └──────────┬─────────┘    │ 4. standardize_emojis│ │
│           │                         │              │ 5. scrub_pii          │ │
│           │                         │              └──────────┬───────────┘ │
└───────────┼─────────────────────────┼─────────────────────────┼─────────────┘
            │                         │                         │
            ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CHAMELON CLOUD S3  (proj09_Data)                         │
│                    chi.tacc.chameleoncloud.org:7480                         │
│                                                                             │
│  zulip-raw-messages/                                                        │
│  ├── real/combined_dataset/                                                 │
│  │   ├── chunk_000.csv  (33 MB) ──────────┐                               │
│  │   ├── chunk_001.csv  (34 MB)           │                               │
│  │   ├── ...                               │                               │
│  │   └── chunk_007.csv  (16 MB)           │                               │
│  ├── synthetic/                            │                               │
│  │   └── synthetic_data.csv  ─────────────┤                               │
│  └── cleaned/                              │                               │
│      └── batch-{uuid}.jsonl  ─────────────┤                               │
│                                            │                               │
│  zulip-training-data/                       │                               │
│  ├── v20260406-225153/                      │                               │
│  │   ├── train.csv  (148 MB)  ◄────────────┤                               │
│  │   ├── val.csv    (32 MB)   ◄────────────┤                               │
│  │   └── test.csv   (32 MB)   ◄────────────┤                               │
│  └── v{timestamp}/                          │                               │
│      └── ...                                │                               │
│                                              │                               │
│  data-quality-report/                        │                               │
│  └── report-{timestamp}.html  ◄─────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  POSTGRESQL  (chatsentry)                                    │
│                  postgres:5432                                              │
│                                                                             │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────────┐          │
│  │  users   │  │  messages  │  │  flags   │  │  moderation     │          │
│  │          │  │            │  │          │  │                 │          │
│  │ id       │  │ id         │  │ id       │  │ id              │          │
│  │ username │  │ user_id FK │  │ msg_id FK│  │ msg_id FK       │          │
│  │ email    │  │ text       │  │ flagged  │  │ action          │          │
│  │ source   │  │ cleaned    │  │   _by FK │  │ confidence      │          │
│  │          │  │ is_toxicity│  │ reason   │  │ model_version   │          │
│  └──────────┘  │ is_suicide │  │ verified │  │ source          │          │
│                │ source     │  │ source   │  │ decided_at      │          │
│                │ created_at │  │ created  │  └─────────────────┘          │
│                └────────────┘  └──────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 TRAINING DATA COMPILATION                                   │
│                 compile_training_data.py                                    │
│                                                                             │
│  Initial Mode:           Incremental Mode:                                  │
│  1. Read CSV chunks      1. Query PostgreSQL                               │
│     from S3                 SELECT messages JOIN moderation                 │
│  2. TextCleaner             WHERE created_at < decided_at                  │
│  3. Bulk load to PG       2. Temporal leakage filter                       │
│  4. GE validation        3. GE validation                                  │
│  5. Quality gate          4. Quality gate                                   │
│  6. Stratified split      5. Stratified split                              │
│  7. Upload to S3          6. Upload to S3                                  │
│                                                                             │
│  Quality Gate:                                                               │
│  • Remove #ERROR! rows (262 known duplicates)                              │
│  • Drop texts < 10 chars (noise)                                            │
│  • Cap texts > 5000 chars (outliers)                                        │
│                                                                             │
│  Stratified Split (70/15/15):                                               │
│  • Stratify by (is_suicide, is_toxicity) combination                       │
│  • 4 classes: (0,0), (1,0), (0,1), (1,1)                                  │
│                                                                             │
│  Output: train.csv, val.csv, test.csv  →  S3 zulip-training-data/v{t}/     │
│  Output: report-{t}.html             →  S3 data-quality-report/            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Versioning Strategy

### 4.1 Training Data Versioning

Training data snapshots are versioned with timestamps (`vYYYYMMDD-HHMMSS`). Each compilation run creates a new version directory under `zulip-training-data/`. This ensures:

- **Reproducibility:** Any training run can be traced to a specific data version
- **Rollback:** Previous versions remain available in S3
- **Audit trail:** GE HTML reports (same timestamp) document data quality at the time of compilation

**Version format:** `v20260406-225153` = 2026-04-06 at 22:51:53 UTC

### 4.2 Source Tracking

Every data record carries a `source` field:

| Source Value | Meaning |
|-------------|---------|
| `real` | Original dataset from combined_dataset.csv |
| `synthetic_local` | Generated by Qwen2.5-1.5B model (few-shot prompting) |
| `synthetic_hf` | Reserved for future HuggingFace API generation |

### 4.3 Transformation Tracking

Each training CSV contains 5 columns that trace the data lineage:

| Column | Provenance |
|--------|-----------|
| `cleaned_text` | Result of TextCleaner pipeline (5 steps applied) |
| `is_suicide` | Original label from dataset or synthetic prompt |
| `is_toxicity` | Original label from dataset or synthetic prompt |
| `source` | Origin classification (real vs synthetic) |
| `message_id` | Unique identifier linking to PostgreSQL or row index |

### 4.4 Temporal Leakage Prevention

The `INCREMENTAL_QUERY` enforces that only messages created BEFORE the moderation decision are included in training data:

```sql
WHERE m.created_at < mod.decided_at
```

This prevents future knowledge from leaking into training data.

---

## 5. End-to-End Data Pipeline Flow

```
Step 1: DATA INGESTION
  combined_dataset.csv (218 MB)
  → ingest_and_expand.py
  → Read in 50K-row chunks
  → Upload to S3: proj09_Data/zulip-raw-messages/real/combined_dataset/chunk_NNN.csv

Step 2: SYNTHETIC DATA GENERATION
  Qwen2.5-1.5B model (local, 2.9 GB)
  → synthetic_generator.py --mode training --count 10000
  → Few-shot prompting with real dataset examples
  → Upload to S3: proj09_Data/zulip-raw-messages/synthetic/synthetic_data.csv

Step 3: REAL-TIME MESSAGE PROCESSING
  Zulip chat messages → POST /messages
  → api/main.py middleware
  → TextCleaner (5 steps: unicode, markdown, URLs, emojis, PII)
  → Store in PostgreSQL (messages table)
  → Buffer in memory (10,000 rows per batch)
  → Flush to S3: proj09_Data/zulip-raw-messages/cleaned/batch-{uuid}.jsonl

Step 4: HUMAN LABELING
  → Labeling dashboard (http://localhost:8000/dashboard)
  → Mark messages as is_toxicity / is_suicide
  → UPDATE messages table + INSERT moderation table

Step 5: TRAINING DATA COMPILATION
  compile_training_data.py (initial or incremental mode)
  → Read from S3 CSV chunks (initial) or PostgreSQL (incremental)
  → TextCleaner (initial mode only)
  → GE validation (6 expectations)
  → Upload GE report to S3: data-quality-report/report-{t}.html
  → Quality gate (remove #ERROR!, filter short/long texts)
  → Stratified split (70/15/15)
  → Upload to S3: zulip-training-data/v{t}/{train,val,test}.csv

Step 6: MODEL TRAINING (ML team consumes training data)
  → Read from S3: zulip-training-data/v{t}/train.csv + val.csv
  → Fine-tune HateBERT model
  → Evaluate on test.csv
```

---

## 6. Summary Table

| Repository | Type | Data | Versioned? | Persistent? |
|-----------|------|------|-----------|-------------|
| `proj09_Data` S3 | Object storage | Raw CSV, cleaned JSONL, training CSV, GE reports, model | Yes (timestamps) | Yes (Chameleon cloud) |
| PostgreSQL `chatsentry` | Relational DB | Users, messages, flags, moderation | Via timestamps | Yes (Docker volume) |
| `hf_cache` volume | File system | Qwen2.5-1.5B model (2.9 GB) | No | Yes (Docker volume) |
| `postgres_data` volume | File system | All PostgreSQL data files | No | Yes (Docker volume) |

---

## 7. Schema Consistency Notes

- All label columns (`is_suicide`, `is_toxicity`) are normalized to `int` (0/1) in training CSVs regardless of source (PostgreSQL returns `bool`, which is cast to `int` by `select_output_columns`)
- The `source` field tracks data provenance through the entire pipeline
- Training CSVs always contain exactly 5 columns: `cleaned_text, is_suicide, is_toxicity, source, message_id`
- Raw CSVs always contain exactly 3 columns: `text, is_suicide, is_toxicity`
