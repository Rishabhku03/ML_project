# Technology Stack — ChatSentry Data Pipeline

**Project:** ChatSentry Content Moderation Data Pipeline
**Researched:** 2026-04-03
**Constraints:** Class-mandated tools only, single KVM@TACC VM, no GPU

## Recommended Stack

### Core Language & Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12.x | All application code | PyIceberg supports 3.10-3.13; Airflow 3.x supports 3.10-3.13. Python 3.12 is the sweet spot — stable, well-tested, all dependencies have prebuilt wheels. Avoid 3.13 for now (some packages still have limited wheel coverage). |
| Docker Compose | v2.x | Service orchestration | Class-mandated; all services (PostgreSQL, MinIO, Redpanda, Redis, Airflow) run as containers |

**Confidence:** HIGH — verified from PyPI classifiers for all core dependencies.

### Data Processing & Text Preprocessing

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| pandas | >=2.2 | CSV ingestion, DataFrame transforms | Industry standard; handles 1.58M rows comfortably in-memory (~500MB RAM). Use `chunked=True` with `pd.read_csv()` for memory control on 16GB VM. |
| emoji | 2.15.0 | Emoji detection & standardization | `emoji.demojize()` converts Unicode emojis to `:shortcode:` format, `emoji.is_emoji()` for detection. Latest stable, actively maintained, BSD license. PyPI-verified. |
| regex | >=2024 | Advanced text pattern matching | Drop-in replacement for `re` with Unicode property support (`\p{Emoji}`, `\p{Mark}`). Essential for PII detection patterns. |
| beautifulsoup4 | >=4.12 | HTML tag stripping from markdown | Lightweight HTML parser. Use `BeautifulSoup(text, 'html.parser').get_text()` to strip HTML remnants after markdown processing. |
| ftfy | >=6.2 | Fix broken Unicode / Mojibake | Fixes encoding issues in scraped Reddit data (common in the Jigsaw/Reddit combined_dataset.csv). |

**Confidence:** HIGH — emoji and regex verified via PyPI. ftfy is the standard for Unicode fixing.

### Why NOT bleach for HTML sanitization

**bleach is DEPRECATED** (announced Jan 2023, last release Oct 2025). The maintainers recommend:
- For HTML **stripping**: Use `BeautifulSoup.get_text()` — sufficient for our use case (we want plain text, not sanitized HTML)
- For HTML **sanitization**: Use `nh3` (Rust-based, Python bindings) — but overkill for content moderation text preprocessing

**Recommendation:** Use `beautifulsoup4` for stripping + `regex` for pattern cleanup. No need for a full sanitizer since we're extracting plain text for ML features, not rendering HTML.

**Confidence:** HIGH — bleach deprecation confirmed from PyPI project description.

### Markdown Removal Strategy

For markdown removal from Zulip messages, use a **regex-based approach** rather than a full Markdown parser:

```python
import re

def strip_markdown(text: str) -> str:
    """Remove common markdown formatting while preserving text content."""
    # Remove code blocks (```...```)
    text = re.sub(r'```[\s\S]*?```', ' [CODE_BLOCK] ', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Remove links but keep text: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove images: ![alt](url) -> [IMAGE]
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '[IMAGE]', text)
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    return text.strip()
```

**Why regex over mistune/markdown-it-py:**
- We're *stripping* markdown, not *parsing* it — regex is sufficient and 10x faster
- No need to generate AST → HTML → strip HTML (unnecessary roundtrip)
- 1.58M rows × regex is fast; 1.58M rows × full parser is slow
- Zulip uses a subset of Markdown — we only need to handle common patterns

**Confidence:** MEDIUM — this is a pragmatic choice. If Zulip messages contain complex nested markdown (tables, nested lists), regex can fail. But for content moderation preprocessing, the text content matters, not the structure.

### Synthetic Data Generation

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| huggingface-hub | 1.9.0 | HuggingFace Inference API client | Use `InferenceClient.text_generation()` to call HF-hosted LLMs. No GPU needed on KVM — the model runs on HF's infrastructure. Latest version, released today (2026-04-03). |
| requests | >=2.31 | HTTP client for HF API | Underlying HTTP library; huggingface-hub wraps this but you may need direct calls for custom endpoints |
| tenacity | >=8.2 | Retry logic for API calls | Exponential backoff for HF API rate limits. Essential for batch synthetic generation. |

**Synthetic Data Approach:**
```
1. Read combined_dataset.csv samples (stratified by label)
2. Construct prompts: "Generate a realistic Zulip chat message that is [toxic/suicide-related/normal]..."
3. Call HF Inference API (e.g., meta-llama/Llama-3.1-8B-Instruct)
4. Parse responses, validate, append labels
5. Upload augmented dataset to MinIO
```

**Rate Limit Considerations:** HF free tier = 1000 requests/day. For course scope, generate ~10K synthetic rows (10 days) or use HF Pro for higher limits.

**Confidence:** HIGH — huggingface-hub verified via PyPI. HF Inference API is well-documented.

### Storage Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 16.x (Docker) | Application state, moderation decisions, message metadata | Class-mandated. Relational schema for structured moderation data. Airflow metadata DB also uses PG. |
| psycopg2-binary | 2.9.11 | PostgreSQL Python adapter | Binary install avoids compilation on KVM. Synchronous API sufficient for batch pipelines. Use `COPY` command for bulk inserts (10x faster than INSERT). |
| MinIO (server) | latest (Docker) | Object storage for raw data, datasets, snapshots | Class-mandated; S3-compatible. Store CSV/Parquet snapshots as immutable objects. |
| minio (Python SDK) | 7.2.20 | MinIO client | `fput_object()` for uploads, `get_object()` for downloads. Handles multipart for large files. |
| Apache Iceberg | via PyIceberg 0.11.1 | Versioned table format for training datasets | Class-mandated. Provides time-travel queries, schema evolution, partition pruning. |

**Confidence:** HIGH — all versions verified from PyPI today.

### PostgreSQL Schema Design (Recommended)

```sql
-- Raw messages from synthetic traffic + real ingestion
CREATE TABLE messages (
    id              BIGSERIAL PRIMARY KEY,
    text_raw        TEXT NOT NULL,
    text_cleaned    TEXT,           -- After preprocessing
    source          VARCHAR(32) NOT NULL,  -- 'synthetic', 'csv', 'zulip'
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Moderation labels (ground truth + predictions)
CREATE TABLE moderation_labels (
    id              BIGSERIAL PRIMARY KEY,
    message_id      BIGINT REFERENCES messages(id),
    is_suicide      BOOLEAN NOT NULL DEFAULT FALSE,
    is_toxicity     BOOLEAN NOT NULL DEFAULT FALSE,
    label_source    VARCHAR(32) NOT NULL,  -- 'original', 'synthetic', 'model', 'human'
    confidence      FLOAT,                 -- For model predictions
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Moderation decisions (admin actions)
CREATE TABLE moderation_decisions (
    id              BIGSERIAL PRIMARY KEY,
    message_id      BIGINT REFERENCES messages(id),
    action          VARCHAR(16) NOT NULL,  -- 'hide', 'warn', 'pass', 'flag'
    decided_by      VARCHAR(32),           -- 'model', 'admin', 'rule'
    model_score     FLOAT,
    decided_at      TIMESTAMP DEFAULT NOW()
);

-- Dataset snapshots (versioned training data)
CREATE TABLE dataset_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    version_tag     VARCHAR(64) NOT NULL UNIQUE,  -- e.g., 'v2026-04-03-001'
    minio_path      TEXT NOT NULL,                 -- MinIO object key
    row_count       INTEGER NOT NULL,
    split_type      VARCHAR(16) NOT NULL,          -- 'train', 'eval', 'test'
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_messages_source ON messages(source);
CREATE INDEX idx_labels_message ON moderation_labels(message_id);
CREATE INDEX idx_decisions_message ON moderation_decisions(message_id);
CREATE INDEX idx_decisions_action ON moderation_decisions(action);
```

**Why this schema:**
- Separates messages from labels (many-to-many: a message can have multiple label sources)
- `moderation_decisions` tracks the admin/model decision separate from ground truth
- `dataset_snapshots` provides versioning metadata that points to MinIO for the actual data
- Supports the batch training path: query decisions + labels, exclude test split, produce snapshot

**Confidence:** MEDIUM — schema design is project-specific. This follows standard patterns but may need adjustment based on actual data flow.

### Pipeline Orchestration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Apache Airflow | 3.1.8 | DAG orchestration for batch pipelines | Class-mandated. Use `DockerOperator` or `PythonOperator` for pipeline tasks. Airflow 3.x has native DAG versioning. |

**Recommended DAG Structure:**

```
DAG: data_ingestion (manual trigger)
  ├─ Task: read_csv → read combined_dataset.csv with pandas
  ├─ Task: generate_synthetic → HF API calls via InferenceClient
  ├─ Task: preprocess_text → clean all text (markdown, emoji, URLs)
  ├─ Task: upload_to_minio → push Parquet to MinIO bucket
  └─ Task: register_snapshot → INSERT into dataset_snapshots

DAG: batch_training_compile (scheduled: daily or on-demand)
  ├─ Task: query_postgres → pull recent messages + decisions
  ├─ Task: filter_noise → remove bot messages, unresolved flags
  ├─ Task: scrub_pii → regex-based PII removal
  ├─ Task: split_data → temporal train/eval/test split (prevent leakage!)
  ├─ Task: save_iceberg → write to Iceberg table via PyIceberg
  └─ Task: notify_training → signal training team (via Redis pub/sub or file flag)
```

**Confidence:** MEDIUM — Airflow 3.x is new (released Apr 2025). If class labs use Airflow 2.x, use 2.11.1 instead. Check with course materials.

### Messaging / Streaming

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Redpanda | latest (Docker) | Kafka-compatible message broker | Class-mandated. Redpanda is a lighter alternative to Kafka — single binary, no JVM, better for a 16GB VM. |
| confluent-kafka | 2.14.0 | Python Kafka client | Works with Redpanda (Kafka API compatible). Latest release (Apr 2, 2026). Has AsyncIO support for FastAPI integration. |

**Usage:** Producer sends synthetic messages to `moderation-requests` topic. Consumer (online processor) reads, preprocesses, and passes to inference.

**Confidence:** HIGH — confluent-kafka is the standard Python Kafka client, verified via PyPI.

### Caching

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Redis | 7.x (Docker) | Feature cache, rate limiting, pub/sub | Class-mandated. Cache preprocessed text features for repeated messages. |
| redis (Python) | 7.4.0 | Redis client | Latest stable. Supports RESP3, connection pooling, pipelines. |

**Confidence:** HIGH — verified via PyPI.

### API Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | >=0.115 | Dummy endpoints + preprocessing API | Class-mandated. Async, Pydantic validation, auto-generated OpenAPI docs. |
| uvicorn | >=0.32 | ASGI server | Standard FastAPI deployment target. |
| pydantic | >=2.10 | Request/response models | FastAPI dependency; validate message schemas at API boundary. |

**Confidence:** HIGH — standard stack.

### Data Format & Versioning

| Format | Use Case | Why |
|--------|----------|-----|
| CSV | Initial ingestion only | `combined_dataset.csv` is already CSV. Read once, convert to Parquet. |
| Parquet | MinIO snapshots, interim storage | Columnar, compressed, fast column reads. `pandas.to_parquet()` with snappy compression. |
| Iceberg (Parquet underneath) | Final versioned training datasets | Class-mandated. Provides time-travel, schema evolution, partition evolution. Use PyIceberg with REST catalog pointing at MinIO. |

**Iceberg vs Plain MinIO:**
- **Plain MinIO (Parquet files):** Simpler, works immediately, `df.to_parquet('s3://bucket/path/data.parquet')`. No schema enforcement, no time-travel, manual versioning via path naming.
- **Iceberg on MinIO:** Schema enforcement, time-travel queries (`SELECT * FROM table FOR SYSTEM_TIME AS OF '2026-04-01'`), automatic partition management. More complex setup (needs catalog — use Nessie or Hive metastore in Docker).

**Recommendation:** Use **plain Parquet in MinIO** for interim/synthetic data. Use **Iceberg** for the final versioned training dataset that the ML team consumes. This gives you the demo video for Iceberg without overcomplicating every pipeline step.

**Confidence:** MEDIUM — PyIceberg 0.11.1 is current but the REST catalog setup on a single VM can be tricky. The class lab materials should cover this.

## Full pip install Command

```bash
pip install \
  "pandas>=2.2" \
  "emoji==2.15.0" \
  "regex>=2024" \
  "beautifulsoup4>=4.12" \
  "ftfy>=6.2" \
  "huggingface-hub==1.9.0" \
  "tenacity>=8.2" \
  "psycopg2-binary==2.9.11" \
  "minio==7.2.20" \
  "pyiceberg[pandas,s3fs]==0.11.1" \
  "confluent-kafka==2.14.0" \
  "redis==7.4.0" \
  "fastapi>=0.115" \
  "uvicorn>=0.32" \
  "pydantic>=2.10" \
  "apache-airflow==3.1.8" \
  "requests>=2.31" \
  "pyarrow>=18.0"
```

**Note:** Airflow is typically installed separately (Docker image or constrained install). Do NOT install Airflow in the same pip environment as your app code unless you use constraint files.

## Docker Compose Services

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: chatsentry
      POSTGRES_USER: pipeline
      POSTGRES_PASSWORD: ${PG_PASSWORD}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: ["miniodata:/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  redpanda:
    image: redpandadata/redpanda:latest
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp 1
      - --memory 1G
      - --reserve-memory 0M
      - --node-id 0
      - --check=false
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://redpanda:9092
    ports: ["9092:9092", "9644:9644"]

  airflow:
    image: apache/airflow:3.1.8
    # ... (see Airflow Docker docs for full compose setup)

volumes:
  pgdata:
  miniodata:
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Emoji handling | emoji 2.15 | Manual Unicode ranges | Fragile; emoji library handles edge cases, skin tones, ZWJ sequences |
| Markdown strip | Regex | mistune 3.2.0 | Overkill for stripping; regex is 10x faster for our use case |
| HTML sanitization | beautifulsoup4 (strip) | bleach 6.3 | bleach is DEPRECATED; we only need stripping, not sanitization |
| PostgreSQL driver | psycopg2-binary | psycopg 3 (psycopg) | psycopg2 is battle-tested; psycopg3 is newer but class labs use psycopg2 |
| Kafka client | confluent-kafka 2.14 | kafka-python | kafka-python is unmaintained; confluent-kafka has AsyncIO support and is actively developed |
| Data versioning | Iceberg (PyIceberg) | DVC | Class-mandated Iceberg; DVC is git-based (not suited for 1.58M row datasets) |
| Data versioning | Iceberg | Plain MinIO paths | Iceberg provides time-travel and schema enforcement; worth the complexity for final training data |
| Airflow | 3.1.8 | 2.11.1 | If class labs use 2.x, downgrade to 2.11.1. Check course materials. |
| HF API client | huggingface-hub | requests (raw API) | huggingface-hub handles auth, retries, rate limiting; no reason to reimplement |

## Known Pitfalls

### 1. Memory pressure on 16GB VM
**Risk:** Loading 1.58M rows with pandas uses ~500MB. Adding Airflow + PostgreSQL + MinIO + Redis + Redpanda can exceed 16GB.
**Mitigation:** Use `pd.read_csv(chunksize=50000)` for incremental processing. Tune Docker memory limits. Stagger service startup.

### 2. PyIceberg catalog setup complexity
**Risk:** PyIceberg needs a catalog (REST, Hive, Nessie). Setting this up on a single VM is non-trivial.
**Mitigation:** Use SQLite-backed REST catalog in Docker. Or start with plain Parquet in MinIO and add Iceberg later.

### 3. HuggingFace API rate limits
**Risk:** Free tier = 1000 requests/day. Synthetic data generation can exhaust this quickly.
**Mitigation:** Batch prompts (multiple examples per request). Cache responses. Use HF Pro token if available.

### 4. Airflow 3.x breaking changes
**Risk:** Airflow 3.0 (Apr 2025) has major changes from 2.x. Class labs may teach 2.x patterns.
**Mitigation:** Check course lab materials. If labs use Airflow 2.x, pin to `apache-airflow==2.11.1`.

### 5. Data leakage in train/test splits
**Risk:** Random splits on synthetic data can leak patterns (same prompt template appearing in both train and eval).
**Mitigation:** Use temporal splits (older data = train, newer = eval) or group splits (by prompt template ID). Document the split strategy.

## Sources

- PyPI: emoji 2.15.0 — https://pypi.org/project/emoji/ (verified 2026-04-03)
- PyPI: bleach 6.3.0 — https://pypi.org/project/bleach/ (DEPRECATED, verified 2026-04-03)
- PyPI: pyiceberg 0.11.1 — https://pypi.org/project/pyiceberg/ (verified 2026-04-03)
- PyPI: apache-airflow 3.1.8 — https://pypi.org/project/apache-airflow/ (verified 2026-04-03)
- PyPI: minio 7.2.20 — https://pypi.org/project/minio/ (verified 2026-04-03)
- PyPI: psycopg2-binary 2.9.11 — https://pypi.org/project/psycopg2-binary/ (verified 2026-04-03)
- PyPI: confluent-kafka 2.14.0 — https://pypi.org/project/confluent-kafka/ (verified 2026-04-03)
- PyPI: huggingface-hub 1.9.0 — https://pypi.org/project/huggingface-hub/ (verified 2026-04-03)
- PyPI: redis 7.4.0 — https://pypi.org/project/redis/ (verified 2026-04-03)
- PyPI: mistune 3.2.0 — https://pypi.org/project/mistune/ (verified 2026-04-03)

---

*Stack research: 2026-04-03*
*All library versions verified against PyPI on research date*
