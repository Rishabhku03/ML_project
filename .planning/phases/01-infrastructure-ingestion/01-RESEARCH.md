# Phase 1: Infrastructure & Ingestion - Research

**Researched:** 2026-04-03
**Domain:** Docker Compose, PostgreSQL, MinIO, FastAPI, CSV ingestion, HuggingFace synthetic data
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundational infrastructure: a Docker Compose stack with PostgreSQL (schema + tables), MinIO (object storage with buckets), and a FastAPI stub on a KVM@TACC VM. It also includes a CSV ingestion pipeline that reads `combined_dataset.csv` (1.58M rows, 3 columns: `text`, `is_suicide`, `is_toxicity`) in 50K-row chunks and uploads to MinIO, plus synthetic data generation via the HuggingFace Inference API using Mistral-7B-Instruct-v0.2.

The course lab (`data-platform-chi`) provides exact Docker Compose patterns for PostgreSQL 18 + MinIO on Chameleon KVM@TACC. The MinIO Python SDK (7.2.20) supports in-memory `BytesIO` uploads without temp files. HuggingFace's `InferenceClient` with `chat_completion()` is the current API for Mistral inference.

**Primary recommendation:** Follow the course lab Docker Compose patterns exactly — PostgreSQL with healthcheck, MinIO with init job for bucket creation, and environment variables via `.env` file.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full schema upfront — all tables (users, messages, flags, moderation) created with complete columns, foreign keys, and constraints
- **D-02:** Individual boolean columns for toxicity labels: `toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate`, `is_suicide` (not JSONB)
- **D-03:** GIN full-text search index on messages.text column
- **D-04:** UUIDs for all primary keys, source tracking column, created_at timestamps
- **D-05:** Upload CSV chunks as-is to MinIO (no Parquet conversion during ingestion)
- **D-06:** 50,000 rows per chunk (~32 chunks total for 1.58M rows)
- **D-07:** MinIO only — ingestion uploads to object storage, does NOT load into PostgreSQL
- **D-08:** By-dataset folder structure: `zulip-raw-messages/combined_dataset/chunk_000.csv`
- **D-09:** HuggingFace model: `mistralai/Mistral-7B-Instruct-v0.2` via Inference API
- **D-10:** Target volume: ~10K synthetic rows (representative sample; full-scale generation deferred to batch pipeline phase)
- **D-11:** Oversample minority classes (toxic/suicide) to rebalance the dataset
- **D-12:** Multi-turn thread prompts to generate realistic Zulip-style conversations
- **D-13:** Prompt-guided labeling — prompt instructs model to generate toxic or benign content; labels assigned from prompt, not post-hoc classification
- **D-14:** String enum `source` column in PostgreSQL with values like `real`, `synthetic_hf`
- **D-15:** Folder split in MinIO: `zulip-raw-messages/real/` and `zulip-raw-messages/synthetic/`

### Agent's Discretion
- Docker Compose port mappings, volume mounts, and environment variable naming
- PostgreSQL schema details for users/flags/moderation tables beyond what requirements specify
- Error handling and retry logic for HuggingFace API calls
- Synthetic data prompt template wording

### Deferred Ideas (OUT OF SCOPE)
- Parquet conversion during ingestion — can be added in batch pipeline phase
- PostgreSQL loading of ingested data — deferred to batch pipeline or a separate load step
- Deterministic seeds for reproducible synthetic generation (QUALITY-01, ADV-01 — v2 requirements)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | PostgreSQL schema with tables: users, messages, flags, moderation (UUIDs, source tracking, timestamps) | Standard Stack: psycopg2-binary 2.9.11, UUID via `gen_random_uuid()`, init SQL mounted to `/docker-entrypoint-initdb.d` |
| INFRA-02 | MinIO buckets created: zulip-raw-messages, zulip-training-data (browsable at :9001) | Standard Stack: minio 7.2.20, minio-init container pattern from course lab |
| INFRA-03 | FastAPI dummy endpoints: POST /messages, POST /flags (accepting synthetic traffic) | Standard Stack: fastapi 0.135.2 + uvicorn 0.42.0, Pydantic models for request validation |
| INFRA-04 | Docker Compose file orchestrating all services on single KVM@TACC VM | Architecture: Course lab pattern with healthchecks, depends_on, named volumes |
| INGEST-01 | Ingestion script reads combined_dataset.csv (1.58M rows, chunked to avoid OOM) | Standard Stack: pandas 3.0.2 with `chunksize=50000`, CSV confirmed: 1,586,127 rows, 3 columns |
| INGEST-02 | Synthetic data generation via HuggingFace API (toxic + benign Zulip-style messages) | Standard Stack: huggingface_hub 1.9.0 with `InferenceClient.chat_completion()`, Mistral-7B-Instruct-v0.2 |
| INGEST-03 | Ingested + synthetic data uploaded to MinIO with source tagging (real vs synthetic) | Standard Stack: minio `put_object()` with `BytesIO`, folder structure per D-08/D-15 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Docker Compose | v5.1.1 (installed) | Service orchestration | Course lab standard; handles PostgreSQL + MinIO + FastAPI lifecycle |
| PostgreSQL | 18 (image tag) | Application state database | Course lab uses `postgres:18`; supports `gen_random_uuid()` natively |
| MinIO | RELEASE.2025-09-07 | S3-compatible object storage | Course lab standard for Chameleon; console at :9001 for staff browsing |
| minio (Python SDK) | 7.2.20 | MinIO client for uploads | Official SDK; supports `put_object()` with `BytesIO` for in-memory upload |
| FastAPI | 0.135.2 | API framework | Already installed; Pydantic validation, auto-generated `/docs` |
| uvicorn | 0.42.0 | ASGI server | Standard FastAPI companion |
| psycopg2-binary | 2.9.11 | PostgreSQL client | Binary install, no compile needed; standard for non-async PG access |
| pandas | 3.0.2 | CSV chunked reading | `pd.read_csv(chunksize=50000)` for OOM-safe 1.58M row processing |
| huggingface_hub | 1.9.0 | HuggingFace Inference API | `InferenceClient.chat_completion()` for Mistral-7B-Instruct-v0.2 |
| python-dotenv | 1.2.2 | Environment variable loading | `.env` file for credentials (HF token, MinIO/PG passwords) |
| PyYAML | 6.0.3 | YAML config parsing | For `config.yaml` pipeline parameters (CONFIG-01 prep) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| io (stdlib) | - | BytesIO for in-memory CSV upload | Avoid temp files when uploading chunks to MinIO |
| logging (stdlib) | - | Structured logging | Required by conventions — no print() in production |
| uuid (stdlib) | - | UUID generation | Fallback if `gen_random_uuid()` not available |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg2-binary | asyncpg | asyncpg is async but adds complexity; psycopg2 is simpler for batch scripts |
| minio (Python SDK) | boto3 | boto3 works with MinIO but minio-py has better MinIO-specific features |
| huggingface_hub InferenceClient | requests (raw HTTP) | Raw HTTP works but InferenceClient handles auth, retries, response parsing |
| pandas chunked read | polars | Polars is faster but pandas is the course standard |

**Installation:**
```bash
pip install minio psycopg2-binary fastapi uvicorn pandas huggingface_hub python-dotenv pyyaml
```

## Architecture Patterns

### Recommended Project Structure
```
├── docker/
│   ├── docker-compose.yaml       # All services
│   ├── .env                      # Credentials (gitignored)
│   └── init_sql/
│       ├── 00_create_tables.sql  # PostgreSQL schema
│       └── 01_seed_data.sql      # Optional seed data
├── src/
│   ├── data/
│   │   ├── ingest_and_expand.py  # CSV ingestion + synthetic generation
│   │   └── __init__.py
│   ├── api/
│   │   ├── main.py               # FastAPI app
│   │   ├── routes/
│   │   │   ├── messages.py       # POST /messages
│   │   │   └── flags.py          # POST /flags
│   │   ├── models.py             # Pydantic schemas
│   │   └── __init__.py
│   └── utils/
│       ├── config.py             # Config loader (YAML + env)
│       ├── minio_client.py       # MinIO client factory
│       ├── db.py                 # PostgreSQL connection helper
│       └── __init__.py
├── config.yaml                   # Pipeline parameters
├── combined_dataset.csv          # Source dataset (1.58M rows)
└── requirements.txt
```

### Pattern 1: Course Lab Docker Compose
**What:** Docker Compose with PostgreSQL, MinIO, MinIO init job, and FastAPI — matching `data-platform-chi` lab exactly
**When to use:** Always for this project — course staff expect familiar patterns
**Example:**
```yaml
# Source: data-platform-chi lab docker-compose.yaml
services:
  postgres:
    image: postgres:18
    container_name: postgres
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: chatsentry_pg
      POSTGRES_DB: chatsentry
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./init_sql:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d chatsentry"]

  minio:
    image: minio/minio:RELEASE.2025-09-07T16-13-09Z
    container_name: minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: chatsentry_minio
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]

  minio-init:
    image: minio/mc:RELEASE.2025-08-13T08-35-41Z-cpuv1
    container_name: minio-init
    depends_on:
      minio:
        condition: service_healthy
    command: |
      mc alias set myminio http://minio:9000 admin chatsentry_minio
      mc mb --ignore-existing myminio/zulip-raw-messages
      mc mb --ignore-existing myminio/zulip-training-data

  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile.api
    container_name: api
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:chatsentry_pg@postgres:5432/chatsentry
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=admin
      - MINIO_SECRET_KEY=chatsentry_minio

volumes:
  postgres_data:
```

### Pattern 2: PostgreSQL Init SQL via docker-entrypoint-initdb.d
**What:** Mount SQL files to `/docker-entrypoint-initdb.d` — PostgreSQL runs them on first init
**When to use:** Always for schema creation — no manual SQL execution needed
**Example:**
```sql
-- Source: data-platform-chi lab pattern
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source VARCHAR(32) NOT NULL DEFAULT 'real'
        CHECK (source IN ('real', 'synthetic_hf'))
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'real'
        CHECK (source IN ('real', 'synthetic_hf')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- GIN full-text search index (D-03)
CREATE INDEX IF NOT EXISTS idx_messages_text_fts
    ON messages USING GIN (to_tsvector('english', text));

CREATE TABLE IF NOT EXISTS flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id),
    flagged_by UUID REFERENCES users(id),
    reason TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS moderation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id),
    action VARCHAR(50) NOT NULL,
    confidence FLOAT,
    model_version VARCHAR(100),
    decided_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Pattern 3: Chunked CSV Upload to MinIO via BytesIO
**What:** Read CSV in chunks with pandas, convert each chunk to CSV bytes, upload via `put_object()` without temp files
**When to use:** Any large file upload to MinIO where memory efficiency matters
**Example:**
```python
# Source: minio/minio-py put_object.py example + pandas docs
import io
import pandas as pd
from minio import Minio

client = Minio(
    endpoint="minio:9000",
    access_key="admin",
    secret_key="chatsentry_minio",
    secure=False,
)

bucket = "zulip-raw-messages"
if not client.bucket_exists(bucket):
    client.make_bucket(bucket)

chunk_iter = pd.read_csv("combined_dataset.csv", chunksize=50000)
for i, chunk in enumerate(chunk_iter):
    csv_bytes = chunk.to_csv(index=False).encode("utf-8")
    object_name = f"real/combined_dataset/chunk_{i:03d}.csv"
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(csv_bytes),
        length=len(csv_bytes),
        content_type="text/csv",
    )
    logger.info("Uploaded chunk %d (%d rows)", i, len(chunk))
```

### Pattern 4: HuggingFace InferenceClient for Chat Completion
**What:** Use `InferenceClient.chat_completion()` to call Mistral-7B-Instruct-v0.2 via HuggingFace Inference API
**When to use:** Synthetic data generation — no GPU needed on KVM
**Example:**
```python
# Source: huggingface_hub docs (https://huggingface.co/docs/huggingface_hub/guides/inference)
from huggingface_hub import InferenceClient

client = InferenceClient(
    provider="featherless-ai",  # Mistral-7B-Instruct-v0.2 available here
    api_key="hf_****",  # HuggingFace token
)

messages = [
    {
        "role": "system",
        "content": "You are a Zulip chat user. Generate realistic chat messages.",
    },
    {
        "role": "user",
        "content": "Generate 5 toxic messages that would be flagged in a chat platform.",
    },
]

response = client.chat_completion(
    messages=messages,
    max_tokens=512,
    temperature=0.8,
)
generated_text = response.choices[0].message.content
```

### Anti-Patterns to Avoid
- **Uploading CSV directly to PostgreSQL during ingestion (D-07):** Ingestion goes to MinIO only. PostgreSQL loading is a separate batch pipeline concern.
- **Temp files for MinIO uploads:** Use `io.BytesIO()` to avoid disk I/O — cleaner and faster.
- **Hardcoded credentials in docker-compose.yaml:** Use `.env` file + `env_file:` directive (though course lab hardcodes for simplicity, use `.env` for portability).
- **Large chunk sizes causing OOM:** 50K rows × ~64 bytes/row ≈ 3MB per chunk — well within memory limits, but don't increase chunk size.
- **Missing healthchecks on PostgreSQL:** Without `depends_on: condition: service_healthy`, FastAPI/ingestion may start before PG is ready.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MinIO bucket creation | Custom init script | `minio/mc` container in Compose | Course lab pattern; idempotent `mc mb --ignore-existing` |
| CSV chunked reading | Manual file splitting | `pd.read_csv(chunksize=N)` | Built-in iterator, handles quoting/encoding, battle-tested |
| PostgreSQL schema init | Manual `psql` commands | Mount SQL to `/docker-entrypoint-initdb.d` | Postgres auto-runs on first start; idempotent with `IF NOT EXISTS` |
| UUID generation | Custom UUID code | `gen_random_uuid()` via `pgcrypto` | PostgreSQL native; no Python-side generation needed |
| FastAPI request validation | Manual JSON parsing | Pydantic `BaseModel` schemas | Auto-validation, error responses, OpenAPI docs |
| HuggingFace API auth | Raw HTTP with headers | `huggingface_hub.InferenceClient` | Handles token refresh, retries, response parsing |
| Environment config | Hardcoded values in code | `python-dotenv` + `.env` file | Standard pattern; `.env` gitignored |

**Key insight:** The course lab provides battle-tested patterns for every infrastructure component. Don't reinvent — follow the `data-platform-chi` patterns exactly.

## Common Pitfalls

### Pitfall 1: PostgreSQL Not Ready Before Dependents Start
**What goes wrong:** FastAPI or ingestion script starts before PostgreSQL accepts connections, causing `connection refused` errors
**Why it happens:** Docker Compose starts containers in order but doesn't wait for service readiness
**How to avoid:** Use `healthcheck` on postgres + `depends_on: condition: service_healthy` on all dependents
**Warning signs:** `psycopg2.OperationalError: connection refused` in logs

### Pitfall 2: MinIO Bucket Not Found During Upload
**What goes wrong:** Ingestion script fails with `NoSuchBucket` when uploading CSV chunks
**Why it happens:** The `minio-init` container hasn't finished creating buckets yet, or ingestion runs before minio-init completes
**How to avoid:** Make ingestion depend on minio-init (service_healthy or service_completed_successfully), or add `bucket_exists()` + `make_bucket()` as fallback in the ingestion script itself
**Warning signs:** `S3Error: NoSuchBucket` in ingestion logs

### Pitfall 3: CSV Encoding Issues with Special Characters
**What goes wrong:** Some text rows contain Unicode, emojis, or mojibake that causes `pandas.errors.ParserError`
**Why it happens:** The dataset is from Reddit — users post in multiple languages with emojis
**How to avoid:** Use `pd.read_csv(..., encoding="utf-8", on_bad_lines="warn")` — skip bad lines with warning, don't crash
**Warning signs:** `UnicodeDecodeError` or `ParserError` during chunk reading

### Pitfall 4: HuggingFace API Rate Limits / Timeouts
**What goes wrong:** Synthetic generation fails after too many API calls — rate limit or timeout
**Why it happens:** Free HuggingFace Inference API has rate limits; Mistral-7B may be slow
**How to avoid:** Implement exponential backoff retry (3 retries, 5s/10s/20s delays), respect `Retry-After` headers, log rate limit errors distinctly
**Warning signs:** HTTP 429 responses, `InferenceTimeoutError`

### Pitfall 5: Memory Pressure During Chunked Upload
**What goes wrong:** System runs out of memory when processing many chunks concurrently
**Why it happens:** Each pandas chunk + BytesIO buffer holds ~3MB; processing 32 chunks sequentially is fine but parallel upload could OOM on 16GB VM
**How to avoid:** Process chunks sequentially (not parallel), explicitly `del csv_bytes` after upload, rely on Python GC
**Warning signs:** OOM killer in `dmesg`, increasing RSS in `docker stats`

### Pitfall 6: MinIO Console Port Not Exposed on Chameleon
**What goes wrong:** Course staff can't browse MinIO at `:9001` because security group doesn't allow it
**Why it happens:** Chameleon VMs block all ports by default; must explicitly open `9001` in security group
**How to avoid:** Create `allow-9001` security group during VM setup (matching course lab pattern)
**Warning signs:** Connection timeout when browsing to `http://<floating-ip>:9001`

## Code Examples

Verified patterns from official sources:

### MinIO put_object with BytesIO
```python
# Source: https://github.com/minio/minio-py/blob/master/examples/put_object.py
import io
from minio import Minio

client = Minio(
    endpoint="minio:9000",
    access_key="admin",
    secret_key="chatsentry_minio",
    secure=False,
)

result = client.put_object(
    bucket_name="zulip-raw-messages",
    object_name="real/combined_dataset/chunk_000.csv",
    data=io.BytesIO(b"col1,col2\nval1,val2"),
    length=21,
    content_type="text/csv",
)
```

### HuggingFace InferenceClient chat_completion
```python
# Source: https://huggingface.co/docs/huggingface_hub/guides/inference
from huggingface_hub import InferenceClient

client = InferenceClient(
    provider="featherless-ai",
    api_key="hf_****",
)

response = client.chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    model="mistralai/Mistral-7B-Instruct-v0.2",
    max_tokens=100,
)
print(response.choices[0].message.content)
```

### PostgreSQL init SQL with GIN index
```sql
-- Source: data-platform-chi lab + PostgreSQL docs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text TEXT NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'real',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_text_fts
    ON messages USING GIN (to_tsvector('english', text));
```

### FastAPI stub endpoint
```python
# Source: FastAPI docs
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="ChatSentry API")

class MessagePayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    user_id: str

@app.post("/messages")
async def create_message(payload: MessagePayload):
    return {"status": "accepted", "message_id": "uuid-here"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Docker Compose v2 (`docker-compose`) | Docker Compose v3+ (`docker compose`) | Docker Desktop 4.x (2022+) | No hyphen; uses `docker compose` CLI |
| `psycopg2` async | `asyncpg` or `psycopg` v3 (async) | psycopg 3.0 (2022) | For batch scripts, psycopg2 is fine; async only needed for API |
| HuggingFace `InferenceClient(provider=...)` | Direct HF Inference API (deprecated approach) | huggingface_hub 0.22+ (2024) | Use `InferenceClient` with `provider` param, not raw HTTP |
| MinIO `fput_object` for uploads | `put_object` with BytesIO | Always available | BytesIO avoids temp files; use for in-memory chunks |

**Deprecated/outdated:**
- Raw HuggingFace Inference API (`requests.post("https://api-inference.huggingface.co/...")`) — use `InferenceClient` instead
- `docker-compose` (hyphenated) — use `docker compose` (space-separated, Docker Compose V2)
- PostgreSQL `uuid-ossp` extension — use `pgcrypto` for `gen_random_uuid()` (faster, no extra dependency)

## Open Questions

1. **HuggingFace Inference API provider selection for Mistral-7B-Instruct-v0.2**
   - What we know: The model page shows "Featherless AI" as an inference provider. The free HF Inference API may also serve it.
   - What's unclear: Which provider has the best availability/rate limits for ~1M tokens of generation
   - Recommendation: Try `provider="featherless-ai"` first; fall back to default HF inference if needed. Implement retry logic regardless.

2. **MinIO image tag version**
   - What we know: Course lab uses `minio/minio:RELEASE.2025-09-07T16-13-09Z`
   - What's unclear: Whether a newer release is available or if the exact tag matters
   - Recommendation: Use the exact course lab tag for reproducibility

3. **PostgreSQL 18 availability in Docker Hub**
   - What we know: Course lab uses `postgres:18`
   - What's unclear: Whether `postgres:18` is a stable release or a development tag
   - Recommendation: Use `postgres:18` as per course lab; fall back to `postgres:16` if image not found

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All scripts | ✓ | 3.12.3 | — |
| Docker | Container orchestration | ✓ | 29.3.1 | — |
| Docker Compose | Service management | ✓ | v5.1.1 | — |
| pip | Package installation | ✓ | 26.0.1 | — |
| PostgreSQL (Docker) | Schema + data | TBD | 18 (image) | postgres:16 |
| MinIO (Docker) | Object storage | TBD | RELEASE.2025-09-07 | Latest stable |
| HuggingFace API | Synthetic generation | ✓ (needs token) | via huggingface_hub 1.9.0 | — |
| combined_dataset.csv | Ingestion | ✓ | 1,586,127 rows | — |

**Missing dependencies with no fallback:**
- HuggingFace API token — must be provided by user; no fallback for synthetic generation

**Missing dependencies with fallback:**
- PostgreSQL/MinIO Docker images — not yet pulled, but `docker compose up` handles this automatically

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (to be installed) |
| Config file | none — see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | PostgreSQL tables created with correct schema | integration | `pytest tests/test_schema.py -x` | ❌ Wave 0 |
| INFRA-02 | MinIO buckets exist and are browsable | integration | `pytest tests/test_minio_buckets.py -x` | ❌ Wave 0 |
| INFRA-03 | POST /messages and POST /flags return 200 | integration | `pytest tests/test_api_endpoints.py -x` | ❌ Wave 0 |
| INFRA-04 | Docker Compose services all start healthy | integration | `docker compose ps \| grep -q healthy` | ❌ Wave 0 |
| INGEST-01 | CSV chunks read correctly (32 chunks, 50K each) | unit | `pytest tests/test_csv_chunking.py -x` | ❌ Wave 0 |
| INGEST-02 | Synthetic data generated with correct labels | unit | `pytest tests/test_synthetic_gen.py -x` | ❌ Wave 0 |
| INGEST-03 | Data uploaded to MinIO with source tags | integration | `pytest tests/test_minio_upload.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — shared fixtures (MinIO client, PG connection, API client)
- [ ] `tests/test_schema.py` — verify tables, columns, indexes, constraints
- [ ] `tests/test_minio_buckets.py` — verify buckets exist with correct names
- [ ] `tests/test_api_endpoints.py` — verify POST /messages and POST /flags accept valid payloads
- [ ] `tests/test_csv_chunking.py` — verify chunk count and row distribution
- [ ] `tests/test_synthetic_gen.py` — verify output has correct columns and source tag
- [ ] `tests/test_minio_upload.py` — verify objects exist in MinIO with correct paths
- [ ] Framework install: `pip install pytest httpx` — httpx for FastAPI TestClient

## Sources

### Primary (HIGH confidence)
- Course lab `data-platform-chi` — Docker Compose patterns for PostgreSQL 18, MinIO, healthchecks, init jobs
- minio/minio-py 7.2.20 — `put_object()` API with BytesIO (installed + GitHub examples)
- huggingface_hub 1.9.0 — `InferenceClient.chat_completion()` API (installed + official docs)
- FastAPI 0.135.2 — already installed, Pydantic model validation
- pandas 3.0.2 — `read_csv(chunksize=50000)` for chunked iteration (installed)

### Secondary (MEDIUM confidence)
- HuggingFace model card — `mistralai/Mistral-7B-Instruct-v0.2` availability via Inference Providers (Featherless AI)
- Docker Compose specification — `depends_on` with `condition: service_healthy` syntax

### Tertiary (LOW confidence)
- PostgreSQL 18 features — `gen_random_uuid()` availability (assumed from course lab; verify on first run)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All versions verified via `pip show` and course lab reference
- Architecture: HIGH — Course lab provides exact Docker Compose patterns
- Pitfalls: HIGH — Known issues from course lab and standard Docker/MinIO/PostgreSQL experience

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (30 days — stable stack, course-constrained)
