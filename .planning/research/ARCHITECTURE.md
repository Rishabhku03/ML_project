# Architecture Patterns — ChatSentry Data Pipeline

**Domain:** Content moderation data pipeline for Zulip chat
**Researched:** 2026-04-03
**Confidence:** HIGH — directly maps to NYU MLOps `data-platform-chi` lab blueprint

## Executive Summary

The ChatSentry data pipeline maps almost 1:1 onto the GourmetGram moderation architecture from the `data-platform-chi` lab. The lab teaches exactly this pattern: PostgreSQL for app state, FastAPI for endpoints, Redpanda for event streaming, Redis for feature store, Airflow for batch orchestration, Iceberg for versioned training data, and MinIO for object storage. We replicate the lab's progression: start with application data, add real-time pipeline, then add batch lakehouse layer.

## Recommended Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ChatSentry Data Pipeline                         │
│                    (Single KVM@TACC VM, Docker Compose)                 │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │ data_        │───▶│ api_v2       │───▶│ PostgreSQL               │  │
│  │ generator    │    │ (FastAPI)    │    │ users, messages, flags,  │  │
│  │ (synthetic   │    │ POST /msgs   │    │ moderation               │  │
│  │  traffic)    │    │ POST /flags  │    └──────────────────────────┘  │
│  └──────────────┘    └──────┬───────┘                                  │
│                             │ emit events                              │
│                             ▼                                          │
│                    ┌──────────────┐    ┌──────────────────────────┐    │
│                    │ Redpanda     │───▶│ stream_consumer          │    │
│                    │ (Kafka)      │    │ - Rolling window counts  │    │
│                    │ Topics:      │    │ - Text preprocessing     │    │
│                    │  messages    │    │ - Moderation triggers    │    │
│                    │  flags       │    └─────────┬────────────────┘    │
│                    │  moderation_ │              │                      │
│                    │  requests    │              ▼                      │
│                    └──────┬───────┘    ┌──────────────────────────┐    │
│                           │            │ Redis                    │    │
│                           ▼            │ Feature store:           │    │
│                    ┌──────────────┐    │ - Rolling text stats     │    │
│                    │ Airflow      │    │ - Preprocessed text cache│    │
│                    │ DAGs:        │    └──────────────────────────┘    │
│                    │ 1. event_agg │                                      │
│                    │ 2. training_ │    ┌──────────────────────────┐    │
│                    │    compile   │───▶│ MinIO                    │    │
│                    └──────┬───────┘    │ Buckets:                 │    │
│                           │            │ - chatsentry-raw         │    │
│                           ▼            │ - chatsentry-training    │    │
│                    ┌──────────────┐    └──────────────────────────┘    │
│                    │ Iceberg      │                                      │
│                    │ Tables:      │    ┌──────────────────────────┐    │
│                    │ event_agg.*  │    │ online_processor         │    │
│                    │ moderation.  │◀──│ - Markdown removal       │    │
│                    │  training_   │    │ - Emoji standardization  │    │
│                    │  data        │    │ - URL extraction         │    │
│                    └──────────────┘    │ - PII scrubbing          │    │
│                                        └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Container Name | Port | Communicates With |
|-----------|---------------|----------------|------|-------------------|
| **PostgreSQL** | Application state: users, messages, flags, moderation decisions | `postgres` | 5432 | api_v2, stream_consumer, Airflow DAGs, Adminer |
| **Adminer** | Browser UI for PostgreSQL inspection | `adminer` | 5050 | PostgreSQL |
| **MinIO** | Object storage: raw messages, cleaned text, training snapshots | `minio` | 9000/9001 | minio-init, Airflow DAGs, training |
| **minio-init** | One-shot job: creates buckets on startup | `minio-init` | — | MinIO |
| **FastAPI (api_v2)** | REST endpoints: `POST /messages`, `POST /flags`. Writes to PostgreSQL AND publishes events to Redpanda | `api_v2` | 8000 | PostgreSQL, Redpanda |
| **data_generator** | Synthetic traffic: sends realistic HTTP requests to api_v2 | `data_generator` | — | api_v2 |
| **Redpanda** | Event stream broker (Kafka-compatible). Topics: `chatsentry.messages`, `chatsentry.flags`, `chatsentry.moderation_requests` | `redpanda` | 19092 | api_v2, stream_consumer, Redpanda Console |
| **Redpanda Console** | Browser UI for inspecting Kafka topics | `redpanda-console` | 8090 | Redpanda |
| **Redis** | In-memory feature store for rolling window counts and preprocessed text cache | `redis` | 6379 | stream_consumer, risk_scoring |
| **Redis Insight** | Browser UI for Redis | `redisinsight` | 8081 | Redis |
| **stream_consumer** | Reads Redpanda events, computes rolling windows, writes features to Redis, publishes moderation requests | `stream_consumer` | — | Redpanda, Redis |
| **risk_scoring_service** | Reads moderation requests, fetches features from Redis + PostgreSQL, writes risk score to PostgreSQL `moderation` table | `risk_scoring_service` | — | Redpanda, Redis, PostgreSQL |
| **Airflow** | Batch orchestration: event aggregation DAG + training data compilation DAG | `airflow-webserver` / `airflow-scheduler` | 8080 | PostgreSQL, MinIO, Iceberg, Redpanda |
| **Nimtable** | Browser UI for Iceberg tables | `nimtable` | 3000 | PostgreSQL (Iceberg catalog), MinIO |

## Data Flow — Three Paths

### Path 1: Ingestion (CSV → Synthetic Data → Endpoints)

This path populates the system with realistic test data before real-time or batch flows run.

```
combined_dataset.csv
       │
       ▼
┌─────────────────────┐    HuggingFace API     ┌─────────────────────┐
│ ingest_and_expand.py │───────────────────────▶│ synthetic_messages  │
│ - Read CSV           │                        │ (Zulip-style text)  │
│ - Sample rows        │                        └─────────┬───────────┘
│ - Generate synthetic │                                  │
│   Zulip convos       │                                  ▼
└─────────────────────┘                        ┌─────────────────────┐
                                               │ MinIO bucket:       │
                                               │ chatsentry-raw      │
                                               │ /synthetic/         │
                                               │ /original/          │
                                               └─────────┬───────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────────┐
                                               │ synthetic_traffic_  │
                                               │ generator.py        │
                                               │ - Pull from dataset │
                                               │ - HTTP POST to      │
                                               │   /messages, /flags │
                                               └─────────┬───────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────────┐
                                               │ api_v2 (FastAPI)    │
                                               │ - Validate payload  │
                                               │ - Write to PG       │
                                               │ - Emit to Redpanda  │
                                               └─────────────────────┘
```

**Build order:** PostgreSQL → MinIO → api_v2 → ingest_and_expand.py → data_generator

### Path 2: Real-time (Events → Features → Scoring)

This path processes messages as they arrive, computing features and making moderation decisions.

```
api_v2 receives message
       │
       ├──────────────────────────┐
       │                          │
       ▼                          ▼
PostgreSQL                   Redpanda
(users, messages,            (chatsentry.messages
 flags tables)                topic: raw event)
       │                          │
       │                          ▼
       │                   ┌──────────────────┐
       │                   │ stream_consumer   │
       │                   │ - Strip markdown  │
       │                   │ - Normalize emojis│
       │                   │ - Extract URLs    │
       │                   │ - Scrub PII       │
       │                   │ - Compute rolling │
       │                   │   window stats    │
       │                   └────────┬─────────┘
       │                            │
       │              ┌─────────────┼─────────────┐
       │              ▼                            ▼
       │         Redis                         Redpanda
       │         (rolling features:          (chatsentry.
       │          text_length_5min,          moderation_requests
       │          msg_velocity,              topic)
       │          flag_count)                     │
       │                                         ▼
       │                                  ┌──────────────────┐
       │                                  │ risk_scoring_    │
       │                                  │ service          │
       │                                  │ - Fetch features │
       │                                  │   from Redis     │
       │                                  │ - Fetch user     │
       │                                  │   history from PG│
       │                                  │ - Score message  │
       │                                  └────────┬─────────┘
       │                                           │
       ▼                                           ▼
PostgreSQL ◀───────────────────────────────────────┘
(moderation table:
 risk_score, model_version,
 trigger_type)
```

**Build order:** Redpanda → Redis → stream_consumer → risk_scoring_service → connect to api_v2

### Path 3: Batch (Production Data → Versioned Training Set)

This path compiles training data from "production" moderation decisions without leakage.

```
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Airflow DAG:      │     │ Airflow DAG:      │     │ MinIO             │
│ event_aggregation │────▶│ training_compile  │────▶│ chatsentry-       │
│                   │     │                   │     │ training bucket   │
│ - Read Redpanda   │     │ - Query PG for    │     │                   │
│   events          │     │   admin decisions │     │ /snapshots/       │
│ - Bin into 5-min  │     │   & user reports  │     │   vYYYYMMDD_HHMMSS│
│   windows         │     │ - 1-week window   │     │                   │
│ - Write to        │     │ - Scrub PII       │     └───────────────────┘
│   Iceberg         │     │ - Strip leakage   │
│                   │     │   metadata        │
└─────────┬─────────┘     │ - Join with event │
          │               │   aggregates      │
          ▼               │ - Write to        │
┌───────────────────┐     │   Iceberg         │
│ Iceberg tables:   │     └─────────┬─────────┘
│ event_aggregations│               │
│ .messages_5min    │               ▼
│ .flags_5min       │     ┌───────────────────┐
│ .mod_requests_5min│     │ Iceberg table:    │
└───────────────────┘     │ moderation.       │
                          │ training_data     │
                          │                   │
                          │ Columns:          │
                          │ text, is_suicide, │
                          │ is_toxicity,      │
                          │ window_features,  │
                          │ snapshot_id       │
                          └───────────────────┘
```

**Build order:** PostgreSQL (with data) → Redpanda (with events) → Airflow DAG 1 (event aggregation) → Iceberg → Airflow DAG 2 (training compilation)

## PostgreSQL Schema Design

Following the lab's `init_sql` pattern with schema initialization at container startup.

```sql
-- init_sql/00_create_app_tables.sql

-- Application users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_test_account BOOLEAN DEFAULT FALSE,
    strike_count INTEGER DEFAULT 0,
    is_banned BOOLEAN DEFAULT FALSE
);

-- Chat messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    raw_text TEXT NOT NULL,
    cleaned_text TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'user_message',
    stream VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CHECK (source IN ('user_message', 'synthetic', 'import'))
);

-- User-reported flags
CREATE TABLE IF NOT EXISTS flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id),
    reporter_id UUID NOT NULL REFERENCES users(id),
    reason TEXT,
    review_status VARCHAR(32) DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    moderation_action_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (review_status IN ('pending', 'reviewed', 'dismissed', 'confirmed'))
);

-- Moderation decisions (model + heuristic)
CREATE TABLE IF NOT EXISTS moderation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type VARCHAR(16) NOT NULL DEFAULT 'message',
    target_id UUID NOT NULL,
    inference_mode VARCHAR(32) NOT NULL,
    model_version VARCHAR(64),
    risk_score FLOAT NOT NULL,
    offensive_score FLOAT,
    self_harm_score FLOAT,
    trigger_type VARCHAR(32),
    action_taken VARCHAR(32),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (target_type IN ('message', 'user')),
    CHECK (inference_mode IN ('heuristic', 'model'))
);

-- Admin decisions (human ground truth for training)
CREATE TABLE IF NOT EXISTS admin_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id),
    admin_id UUID NOT NULL REFERENCES users(id),
    decision VARCHAR(32) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (decision IN ('approve', 'hide', 'delete', 'warn'))
);
```

**Why this schema:**
- `users.strike_count` — enables strike-based banning logic
- `messages.source` — distinguishes synthetic from real for training data filtering
- `moderation.model_version` — tracks which model version produced each score (audit trail)
- `admin_decisions` — separate table for human labels, the ground truth for batch training pipeline
- UUIDs for all IDs — matches lab pattern, enables distributed ID generation

## MinIO Bucket Structure

Following the lab's `minio-init` pattern with `mc mb` commands.

```bash
# docker-compose.yaml minio-init command
mc alias set myminio http://minio:9000 admin chatsentry_minio

# Raw/original data
mc mb --ignore-existing myminio/chatsentry-raw
mc mb --ignore-existing myminio/chatsentry-raw/original
mc mb --ignore-existing myminio/chatsentry-raw/synthetic

# Cleaned/processed data
mc mb --ignore-existing myminio/chatsentry-cleaned

# Training data snapshots (Iceberg warehouse)
mc mb --ignore-existing myminio/chatsentry-training
mc mb --ignore-existing myminio/chatsentry-training/warehouse

# Model artifacts
mc mb --ignore-existing myminio/chatsentry-models
```

**Bucket layout:**
```
chatsentry-raw/
├── original/                    # Original combined_dataset.csv rows
│   └── combined_dataset.parquet
└── synthetic/                   # HuggingFace-generated synthetic messages
    └── batch_001.parquet

chatsentry-cleaned/
├── messages/                    # Cleaned text (markdown stripped, emojis normalized)
│   └── batch_YYYYMMDD.parquet
└── features/                    # Computed feature vectors
    └── batch_YYYYMMDD.parquet

chatsentry-training/warehouse/   # Iceberg warehouse root
├── event_aggregations/
│   ├── messages_5min/           # Iceberg table: 5-min message window aggregates
│   ├── flags_5min/              # Iceberg table: 5-min flag window aggregates
│   └── moderation_requests_5min/
└── moderation/
    └── training_data/           # Iceberg table: versioned training dataset

chatsentry-models/
├── hatebert_v1/
│   ├── model.safetensors
│   ├── config.json
│   └── metadata.json            # Includes snapshot_id from Iceberg
└── hatebert_v2/
    └── ...
```

## Real-time vs Batch Processing Patterns

| Concern | Real-time (stream_consumer) | Batch (Airflow DAGs) |
|---------|---------------------------|---------------------|
| **Trigger** | Every message arrival (event-driven) | Hourly (event aggregation) / Daily (training compile) |
| **Input** | Redpanda event stream | PostgreSQL snapshots + Iceberg window tables |
| **Output** | Redis feature cache, moderation scores in PG | Iceberg training data table |
| **Latency target** | <200ms P99 | Minutes to hours |
| **Feature types** | Rolling windows (5min, 1hr): msg count, flag count, text stats | Aggregated historical: label + features at anchor times |
| **Data freshness** | Current state (what's happening now) | Durable history (what happened) |
| **Failure mode** | Flag for admin review (fail-safe) | Retry with Airflow |

**Key insight from lab:** PostgreSQL keeps *current state* (total counts), but cannot reconstruct *time-anchored features* (what was the flag count 5 minutes after this message was posted?). That's why we need both paths — Redpanda + Redis for real-time features, Iceberg for durable training history.

## Docker Compose Service Order

Following the lab's progressive startup pattern. Services must be brought up in dependency order.

```yaml
# Phase 1: Storage layer
postgres          # healthcheck: pg_isready
adminer           # depends on: postgres
minio             # healthcheck: mc ready
minio-init        # depends on: minio (healthy)

# Phase 2: Application layer
api_v2            # depends on: postgres (healthy), redpanda (healthy)
data_generator    # depends on: api_v2

# Phase 3: Real-time pipeline
redpanda          # healthcheck: rpk cluster health
redpanda-console  # depends on: redpanda
redis             # healthcheck: redis-cli ping
redisinsight      # depends on: redis
stream_consumer   # depends on: redpanda, redis
risk_scoring_service  # depends on: redpanda, redis, postgres

# Phase 4: Batch pipeline
airflow-init      # depends on: postgres, minio
airflow-webserver # depends on: airflow-init
airflow-scheduler # depends on: airflow-init
nimtable          # depends on: postgres, minio
```

## Suggested Build Order (Dependencies)

```
1. PostgreSQL + Adminer + init_sql
   │  Validates: DB schema, table creation, Adminer access
   │
2. MinIO + minio-init
   │  Validates: Buckets created, console accessible at :9001
   │
3. api_v2 (FastAPI)
   │  Validates: POST /messages, POST /flags write to PG
   │
4. ingest_and_expand.py
   │  Validates: CSV read, synthetic generation, MinIO upload
   │
5. data_generator
   │  Validates: HTTP traffic hitting api_v2, data in PG + MinIO
   │
6. Redpanda + Redpanda Console
   │  Validates: Topics visible in console at :8090
   │
7. Redis + Redis Insight
   │  Validates: Keys visible in Insight at :8081
   │
8. stream_consumer
   │  Validates: Events consumed from Redpanda, features in Redis
   │
9. risk_scoring_service
   │  Validates: Moderation rows in PG moderation table
   │
10. online_processor.py (integrated into api_v2 or stream_consumer)
   │  Validates: Text cleaning visible in Redis features
   │
11. Airflow (init + webserver + scheduler)
   │  Validates: DAGs visible at :8080
   │
12. Airflow DAG 1: event_aggregation
   │  Validates: Iceberg tables in Nimtable at :3000
   │
13. Airflow DAG 2: training_compile
   │  Validates: moderation.training_data in Iceberg
   │
14. Nimtable (Iceberg browser)
       Validates: Tables browsable, Parquet + metadata files in MinIO
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct PG queries for real-time features
**What:** Querying PostgreSQL rolling counts at inference time
**Why bad:** Adds load to the serving database, can't reconstruct time-anchored features
**Instead:** Use Redis (via Redpanda stream consumer) for real-time feature computation. PostgreSQL is for durable state, not feature serving.

### Anti-Pattern 2: Storing raw events only in PostgreSQL
**What:** Writing every view/event as a separate PG row
**Why bad:** PostgreSQL is optimized for current-state queries, not event history. Table bloat from high-frequency events (views can be 15/sec).
**Instead:** Events go to Redpanda first. PostgreSQL stores aggregated state (total counts). Iceberg stores durable event history for training.

### Anti-Pattern 3: Monolithic preprocessing script
**What:** One giant script that does ingestion + cleaning + feature computation + storage
**Why bad:** Can't independently scale or debug stages. Changes to cleaning logic require re-running everything.
**Instead:** Separate concerns: `ingest_and_expand.py` (CSV→synthetic), `online_processor.py` (real-time text cleaning), Airflow DAGs (batch feature computation).

### Anti-Pattern 4: Training directly from PostgreSQL
**What:** Querying PG at training time to build feature vectors
**Why bad:** Inconsistent with online features (different query logic), adds load to serving DB, can't reproduce exact training state.
**Instead:** Airflow DAG materializes training features to Iceberg. Training reads from Iceberg snapshot (reproducible, versioned, no PG load).

## Scalability Considerations (Single VM)

| Concern | At 300 users (current) | At risk if... |
|---------|----------------------|---------------|
| PostgreSQL | Sufficient — 4 vCPU, 16GB RAM | >1000 concurrent users, >10M rows |
| Redpanda | 1GB memory, dev-container mode | Sustained >50 RPS across topics |
| Redis | Default config | Feature keys exceed available memory |
| Airflow | Single scheduler | DAG run times exceed scheduling interval |
| MinIO | Local disk storage | Training data exceeds VM disk |
| Iceberg | Catalog in PostgreSQL, files in MinIO | Snapshots exceed available storage |

**Mitigation:** Docker Compose `deploy.resources.limits` on each service to prevent one service from consuming all VM resources.

## Sources

- `data-platform-chi` lab — primary architecture blueprint (HIGH confidence)
  - https://teaching-on-testbeds.github.io/data-platform-chi/
- `data-persist-chi` lab — MinIO bucket patterns (HIGH confidence)
  - https://teaching-on-testbeds.github.io/data-persist-chi/
- `Idea.md` — project-specific component list (HIGH confidence)
- `MLOps-Project-Report-TeamChatSentry.txt` — requirements, thresholds, constraints (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md` — existing design document (HIGH confidence)
