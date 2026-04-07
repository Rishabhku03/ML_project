# ChatSentry — Data Generator Artifact Documentation

**Requirement:** Data generator that hits the (hypothetical) service endpoints with real or synthetic data (following best practices for synthetic data generation, as discussed in the lecture).
**Project:** ChatSentry AI-Powered Content Moderation — Data Pipeline
**Author:** Rishabh Narayan (Data Specialist)
**Repository:** `Ml_Project`
**Infrastructure:** Chameleon Cloud KVM@TACC (m1.xlarge — 4 vCPU / 16GB RAM, no GPU)

---

## 1. Overview

This artifact documents the **synthetic data generator** that produces labeled chat messages and dispatches them to the ChatSentry FastAPI service endpoints. The generator runs entirely locally using a Qwen2.5-1.5B causal language model (no GPU, no external API) and follows lecture best practices for synthetic data generation.

Two modes are supported:

| Mode | Purpose | Output |
|------|---------|--------|
| `training` | Generate labeled CSV for downstream model training | CSV uploaded to Chameleon S3 |
| `test` | Simulate real-time user traffic hitting the API | POST requests to `/messages` endpoint |

---

## 2. Artifact Inventory

### 2.1 Synthetic Data Generator — `src/data/synthetic_generator.py`

**Purpose:** Generate labeled synthetic chat messages using few-shot prompting with a local Qwen2.5-1.5B model, then either upload to S3 (training mode) or POST to the API (test mode).

**Key functions:**

| Function | Purpose |
|----------|---------|
| `generate_text(prompt, max_new_tokens, temperature)` | Generate text from a prompt using the local Qwen2.5-1.5B model |
| `_parse_numbered_list(text)` | Parse numbered list output from the model into clean message strings |
| `generate_batch(label_type, count)` | Generate a batch of labeled messages for training data |
| `generate_training_data(target_total, bucket)` | Generate labeled synthetic data and upload to S3 as CSV |
| `generate_test_message(label_type, api_url)` | Generate a single test message and POST it to the API endpoint |

**Usage:**
```bash
# Training mode: generate 10K labeled rows → S3
docker exec api python3 -m src.data.synthetic_generator --mode training --count 10000

# Test mode: generate 10 messages, POST to API, 2s apart
docker exec api python3 -m src.data.synthetic_generator --mode test --count 10 --interval 2

# Test mode with specific label
docker exec api python3 -m src.data.synthetic_generator --mode test --count 5 --label toxic
```

**CLI arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--mode` | (required) | `training` or `test` |
| `--count` | 10000 (training), 1 (test) | Number of rows/requests |
| `--label` | random | Label type: `toxic`, `suicide`, `benign` |
| `--interval` | 2.0 | Seconds between requests (test mode) |
| `--api-url` | `http://localhost:8000/messages` | API endpoint URL |
| `--bucket` | `proj09_Data` | S3 bucket for training mode |

---

### 2.2 Prompt Templates — `src/data/prompts.py`

**Purpose:** Few-shot prompt templates for generating labeled chat messages per label type.

**Key types:**

| Name | Purpose |
|------|---------|
| `LabelType` | Literal type: `"toxic"`, `"suicide"`, `"benign"` |
| `GenerationPrompt` | Frozen dataclass holding prompt text, label flags, and label type |
| `LABEL_DISTRIBUTION` | Dict mapping label → proportion (oversamples minority classes) |
| `PROMPTS_BY_LABEL` | Dict mapping label → `GenerationPrompt` |

**Label distribution (oversamples minority classes per lecture best practices):**

| Label | Proportion | Rows (of 10K target) |
|-------|-----------|---------------------|
| `toxic` | 30% | ~3,000 |
| `suicide` | 30% | ~3,000 |
| `benign` | 40% | ~4,000 |

**Few-shot prompt structure:**
Each prompt includes 3 real examples extracted from the `combined_dataset.csv`:
- `TOXIC_EXAMPLES`: Insults, threats, hate speech
- `SUICIDE_EXAMPLES`: Suicidal ideation, self-harm expressions
- `BENIGN_EXAMPLES`: Normal chat messages, project updates, code reviews

The model is asked to generate 10 new messages similar to the examples, numbered 1–10.

---

### 2.3 FastAPI Service Endpoint — `src/api/main.py`

**Purpose:** Accepts incoming messages, applies the TextCleaner pipeline, persists to PostgreSQL, and buffers to MinIO.

**Relevant endpoint for data generator:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/messages` | Accept message payload, clean text, store in DB |

**Request payload:**
```json
{
  "text": "Generated synthetic message text",
  "user_id": "synth-test-toxic"
}
```

**Processing pipeline (applied on every POST /messages):**
1. TextCleaningMiddleware intercepts the request
2. `TextCleaner.clean(raw_text)` applies 5-step pipeline:
   - Unicode normalization (`ftfy`)
   - Markdown stripping
   - URL extraction → `[URL]`
   - Emoji standardization → `:shortcode:`
   - PII scrubbing → `[EMAIL]`, `[PHONE]`, `[USER]`
3. Message persisted to PostgreSQL with both `text` (raw) and `cleaned_text`
4. Cleaned data buffered for batch upload to MinIO (flushed at 10K records)

---

### 2.4 Text Cleaning Pipeline — `src/data/text_cleaner.py`

**Purpose:** Shared cleaning pipeline used by both online (API middleware) and batch (compilation) paths. Applied to every message generated by the data generator when it hits the API.

**Pipeline steps (in order):**

| Step | Function | Transformation | Example |
|------|----------|---------------|---------|
| 1 | `fix_unicode()` | Normalize encoding via `ftfy` | `cafÃ©` → `café` |
| 2 | `strip_markdown()` | Remove HTML tags + Markdown markers | `**bold**` → `bold` |
| 3 | `extract_urls()` | Replace URLs with `[URL]` | `https://evil.com` → `[URL]` |
| 4 | `standardize_emojis()` | Convert emojis to `:shortcode:` | `😊` → `:smiling_face_with_smiling_eyes:` |
| 5 | `scrub_pii()` | Replace email/phone/@username with placeholders | `user@email.com` → `[EMAIL]` |

---

### 2.5 Docker Infrastructure — `docker/`

| File | Purpose |
|------|---------|
| `docker-compose.yaml` | Orchestrates 4 services: PostgreSQL, Adminer, FastAPI API, GE Viewer |
| `Dockerfile.api` | Python 3.12-slim image, installs requirements.txt, runs uvicorn |
| `init_sql/00_create_tables.sql` | PostgreSQL schema: users, messages, flags, moderation tables |
| `init_sql/01_seed_data.sql` | Seeds one default user for the batch pipeline |

**How to reproduce:**
```bash
cd docker/
cp .env.example .env  # Fill in Chameleon S3 credentials
docker compose up -d
```

---

### 2.6 Tests — `tests/test_synthetic_gen.py`

**Purpose:** Unit tests for synthetic data generation — validates prompt coverage, label flags, distribution, and text parsing.

| Test | What it validates |
|------|-------------------|
| `test_prompts_cover_all_labels()` | All 3 labels (toxic, suicide, benign) have prompt templates |
| `test_prompt_labels_have_correct_flags()` | Toxic sets `is_toxicity=True, is_suicide=False`; suicide sets `is_suicide=True, is_toxicity=False`; benign sets both False |
| `test_label_distribution_sums_to_one()` | Label proportions sum to ~1.0 |
| `test_label_distribution_rebalances_minority_classes()` | Toxic ≥ 25%, suicide ≥ 25% (oversampled from original ratios) |
| `test_parse_generated_text_numbered_list()` | Parses "1. Hello\n2. World" into ["Hello", "World"] |
| `test_parse_generated_text_empty_lines()` | Handles empty lines between numbered items |
| `test_parse_generated_text_no_numbering()` | Falls back to plain text when no numbering |
| `test_target_total_is_reasonable()` | TARGET_TOTAL is between 5K and 10K |

---

### 2.7 Tests — `tests/test_traffic_generator.py`

**Purpose:** Tests for HTTP traffic dispatch — CSV loading, POST requests, rate control, error handling.

| Test | What it validates |
|------|-------------------|
| `test_load_csv_messages()` | CSV loading returns non-empty strings, filters whitespace |
| `test_load_csv_messages_empty_file()` | Empty CSV returns empty list |
| `test_send_message_makes_post_request()` | POST sent with correct URL and JSON payload |
| `test_send_message_handles_connection_error()` | Returns None on connection error |
| `test_send_message_handles_non_200()` | Returns None on 500 status |
| `test_build_message_payload()` | Payload has `text`, `user_id`, `source` fields |
| `test_build_flag_payload()` | Flag payload has `message_id`, `flagged_by`, `reason` |
| `test_run_traffic_generator_respects_rps()` | At 5 RPS for 2s, dispatches ~10 requests (±50%) |
| `test_run_traffic_generator_aborts_on_empty_csv()` | Gracefully aborts when CSV is empty |

---

## 3. Best Practices for Synthetic Data Generation

The generator follows these lecture best practices:

| Practice | Implementation |
|----------|---------------|
| **Few-shot prompting** | Each prompt includes 3 real dataset examples to ground the model's output in realistic language |
| **Label distribution rebalancing** | Oversamples minority classes: toxic 30%, suicide 30% (original dataset has ~2% toxic, ~22% suicide) |
| **Prompt-guided labeling** | Labels assigned from the prompt that generated the text, not post-hoc classification (avoids label noise) |
| **Source tracking** | All synthetic rows tagged with `source` field for provenance tracking |
| **Local model** | Qwen2.5-1.5B runs on CPU — no GPU, no external API calls, no API token needed |
| **Batch generation** | Generates 10 messages per prompt call to amortize model inference cost |
| **Temperature + sampling** | Uses `temperature=0.8`, `top_p=0.9`, `repetition_penalty=1.15` for diverse output |

---

## 4. Data Flow Diagram

```
┌──────────────────────────────────────┐
│  Qwen2.5-1.5B (local, CPU)          │
│  Few-shot prompts with real examples │
└──────────┬───────────────────────────┘
           │
           ├─── training mode ───────────────────────────────┐
           │   generate_training_data()                       │
           │   Output: CSV with text, is_suicide, is_toxicity │
           │   Upload: S3 → zulip-raw-messages/synthetic/    │
           │                                                  ▼
           │                              ┌──────────────────────────────┐
           │                              │ S3: synthetic_data.csv       │
           │                              │ (10K rows, minority-          │
           │                              │  oversampled)                │
           │                              └──────────────────────────────┘
           │
           └─── test mode ───────────────────────────────────┐
               generate_test_message()                       │
               POST /messages {text, user_id}                │
                                                             ▼
               ┌─────────────────────────────────────────────────────┐
               │ FastAPI (POST /messages)                            │
               │  → TextCleaner (5-step pipeline)                    │
               │  → PostgreSQL (raw + cleaned text)                  │
               │  → MinIO buffer (JSONL batch flush)                 │
               └─────────────────────────────────────────────────────┘
```

---

## 5. Reproducibility Instructions

### Prerequisites
- Chameleon Cloud account with access to KVM@TACC
- SSH key configured for VM access
- S3 credentials for `proj09_Data` bucket

### Steps to reproduce

**1. Deploy services**
```bash
# SSH into VM
ssh -i ~/.ssh/id_rsa_chameleon cc@<VM_IP>

# Clone repo, configure credentials
cd chatsentry
cp docker/.env.example docker/.env  # Fill in S3 credentials

# Start all services
cd docker && docker compose up -d
```

**2. Run synthetic data generator — training mode**
```bash
# Generate 10K labeled synthetic rows → S3
docker exec api python3 -m src.data.synthetic_generator --mode training --count 10000
```

**3. Run synthetic data generator — test mode (hits API endpoints)**
```bash
# Generate 20 messages, POST to API, 2 seconds apart
docker exec api python3 -m src.data.synthetic_generator --mode test --count 20 --interval 2
```

**4. Verify**
```bash
# Check S3 for training CSV
docker exec api python3 -c "
from minio import Minio; import os, io, pandas as pd
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
obj = c.get_object('proj09_Data', 'zulip-raw-messages/synthetic/synthetic_data.csv')
df = pd.read_csv(io.BytesIO(obj.read()))
obj.close()
print(f'Rows: {len(df)}')
print(df[['is_suicide','is_toxicity']].value_counts())
"

# Check PostgreSQL for test mode messages
docker exec postgres psql -U user -d chatsentry -c "SELECT COUNT(*), source FROM messages GROUP BY source;"
```

---

## 6. Artifact File Listing

```
Ml_Project/
├── src/
│   ├── data/
│   │   ├── synthetic_generator.py     # Data generator (training + test modes)
│   │   ├── prompts.py                 # Few-shot prompt templates + label distribution
│   │   ├── text_cleaner.py            # 5-step text cleaning pipeline
│   │   ├── ingest_and_expand.py       # CSV → S3 ingestion
│   │   ├── compile_training_data.py   # Batch compilation + split
│   │   └── data_quality.py            # Great Expectations validation
│   ├── api/
│   │   ├── main.py                    # FastAPI app (POST /messages endpoint)
│   │   ├── middleware.py              # Text cleaning middleware
│   │   └── models.py                  # Pydantic schemas
│   └── utils/
│       ├── config.py                  # Configuration (pipeline.yaml + env vars)
│       ├── minio_client.py            # S3 client factory
│       └── db.py                      # PostgreSQL client factory
├── docker/
│   ├── docker-compose.yaml            # 4 services: postgres, api, adminer, ge-viewer
│   ├── Dockerfile.api                 # API container image
│   ├── init_sql/
│   │   ├── 00_create_tables.sql       # PostgreSQL schema DDL
│   │   └── 01_seed_data.sql           # Seed data
│   └── .env.example                   # S3 credentials template
├── config/
│   └── pipeline.yaml                  # Pipeline configuration
├── tests/
│   ├── test_synthetic_gen.py          # Synthetic generator unit tests (8 tests)
│   └── test_traffic_generator.py      # Traffic dispatch tests (9 tests)
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata + tool config
└── combined_dataset.csv               # Source dataset (1.58M rows)
```
