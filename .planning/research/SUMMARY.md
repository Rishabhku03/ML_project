# Project Research Summary

**Project:** ChatSentry Data Pipeline
**Domain:** Content moderation data pipeline for Zulip chat (toxic/self-harm text classification)
**Researched:** 2026-04-03
**Confidence:** HIGH

## Executive Summary

ChatSentry is a batch-and-stream data pipeline that ingests chat messages, preprocesses text for ML consumption, and produces versioned training datasets for a HateBERT-based content moderation model. The architecture maps directly onto the NYU MLOps `data-platform-chi` lab blueprint — PostgreSQL for app state, FastAPI for endpoints, Redpanda for event streaming, Redis for feature caching, Airflow for batch orchestration, Iceberg for versioned training data, and MinIO for object storage. This is not a custom design; it is a deliberate reproduction of a well-documented lab pattern that course staff already know and grade against.

The recommended stack is Python 3.12 with Docker Compose on a single KVM@TACC VM (4 vCPU, 16GB RAM, no GPU). All class-mandated technologies are incorporated: PostgreSQL 16, MinIO, Redpanda, Redis 7, FastAPI, Apache Airflow 3.1.8, and Apache Iceberg via PyIceberg 0.11.1. Text preprocessing uses regex-based markdown stripping, the `emoji` library for standardization, `beautifulsoup4` for HTML stripping (not the deprecated `bleach`), and `ftfy` for Unicode repair. Synthetic data generation calls HuggingFace Inference API via `huggingface-hub` — no local GPU needed.

The critical risks are: (1) data leakage through point-in-time violations in batch training data compilation, (2) preprocessing inconsistency between the online and batch code paths, and (3) synthetic data distribution shift that makes the model brittle on real inputs. All three are preventable with disciplined architecture: shared preprocessing module, temporal join enforcement, and source-tagged synthetic data with distribution validation. The pipeline is buildable in 4 phases following the architecture's dependency graph, with the critical path being MinIO setup → ingestion → batch pipeline → training data output.

## Key Findings

### Recommended Stack

**Core technologies:**
- **Python 3.12**: Application code — PyIceberg, Airflow 3.x, and all dependencies have prebuilt wheels. Avoid 3.13 (limited wheel coverage).
- **PostgreSQL 16**: Application state (users, messages, flags, moderation decisions) — class-mandated, battle-tested. Use `COPY` for bulk inserts (10x faster).
- **MinIO**: Object storage for raw data, cleaned snapshots, training artifacts — class-mandated, S3-compatible, bucket UI at :9001 for grading.
- **Redpanda**: Kafka-compatible event broker — lighter than Kafka (single binary, no JVM), critical for the real-time streaming path.
- **Redis 7**: Feature store for rolling window counts and preprocessed text cache — class-mandated, fast in-memory reads.
- **FastAPI + uvicorn**: REST endpoints accepting synthetic traffic — class-mandated, async, Pydantic validation, auto-generated OpenAPI docs.
- **Apache Airflow 3.1.8**: Batch DAG orchestration (event aggregation → training compilation) — class-mandated. Check if class labs use 2.x; if so, pin to 2.11.1.
- **PyIceberg 0.11.1**: Versioned table format for final training datasets — class-mandated, provides time-travel queries. Use plain Parquet in MinIO for interim data; reserve Iceberg for the final training snapshot.

**Text preprocessing stack:**
- `emoji 2.15.0` — emoji detection and standardization to `:shortcode:` format
- `regex >=2024` — advanced Unicode pattern matching (drop-in `re` replacement with `\p{Emoji}`)
- `beautifulsoup4 >=4.12` — HTML tag stripping (`bleach` is DEPRECATED as of Jan 2023)
- `ftfy >=6.2` — fixes broken Unicode/mojibake in scraped Reddit data
- Regex-based markdown stripping — 10x faster than full Markdown parser for stripping (not parsing)

**Synthetic data generation:**
- `huggingface-hub 1.9.0` — Inference API client for calling HF-hosted LLMs (e.g., Llama-3.1-8B-Instruct)
- `tenacity >=8.2` — exponential backoff retry for HF API rate limits (free tier = 1000 req/day)
- `confluent-kafka 2.14.0` — Python Kafka client with AsyncIO support (kafka-python is unmaintained)

### Expected Features

**Must have (table stakes):**
- CSV ingestion (1.58M rows, chunked reading to avoid OOM on 16GB VM)
- MinIO bucket setup and data upload (zulip-raw, zulip-training buckets)
- Text preprocessing pipeline: markdown stripping, emoji standardization, URL extraction, PII scrubbing, Unicode normalization, whitespace collapsing, HTML entity decoding
- Synthetic data generation via HuggingFace API (toxic + benign Zulip-style messages)
- Synthetic HTTP traffic generator hitting dummy FastAPI endpoints
- Batch training data compilation with temporal splits and data leakage prevention
- Versioned training snapshots in MinIO (immutable, tagged)
- Schema validation at every pipeline boundary (Pydantic for API, assertions for batch)
- Class balance reporting before/after every pipeline stage
- Data design document with schemas, flow diagrams, field definitions

**Should have (high-value differentiators, pick 2-3):**
- Configurable pipeline parameters (YAML/JSON config, not hardcoded) — low effort, high perceived quality
- Reproducible pipeline with deterministic seeds — low effort, shows MLOps maturity
- Data quality metrics report (null rates, duplicate rates, text length distribution) — medium effort, directly addresses reference paper
- DVC or Iceberg for data versioning — medium effort, demonstrates reproducibility

**Defer (mention in design doc, don't build):**
- Active learning sampling for rare events — too complex for scope
- Airflow orchestration beyond basic DAGs — CLI scripts sufficient for demos
- Data drift detection — requires production traffic not yet available
- Real-time Kafka/Redpanda streaming infrastructure — the pipeline is fundamentally batch-oriented; real-time adds complexity with no deliverable benefit

### Architecture Approach

Three-path architecture on a single Docker Compose VM, following the `data-platform-chi` lab blueprint exactly.

**Major components:**
1. **Ingestion path** (CSV → synthetic data → FastAPI endpoints → PostgreSQL): Populates the system. `ingest_and_expand.py` reads CSV, calls HF API for synthetic expansion, uploads to MinIO. `data_generator.py` sends HTTP POST traffic to `api_v2`.
2. **Real-time path** (Redpanda → stream_consumer → Redis → risk_scoring): Processes messages as they arrive. `stream_consumer` strips markdown, normalizes emojis, computes rolling window features in Redis. `risk_scoring_service` writes moderation scores to PostgreSQL.
3. **Batch path** (PostgreSQL → Airflow DAGs → Iceberg → MinIO): Compiles versioned training data. Two DAGs: `event_aggregation` (5-min window bins to Iceberg) and `training_compile` (queries PG, strips leakage metadata, writes versioned training snapshot).

**Build order (from architecture dependency graph):**
1. PostgreSQL + Adminer + init_sql
2. MinIO + minio-init (bucket creation)
3. api_v2 (FastAPI endpoints)
4. ingest_and_expand.py (CSV + synthetic generation)
5. data_generator (synthetic HTTP traffic)
6. Redpanda + Console
7. Redis + Redis Insight
8. stream_consumer
9. risk_scoring_service
10. online_processor (text preprocessing — shared module)
11. Airflow (init + webserver + scheduler)
12. Airflow DAG 1: event_aggregation → Iceberg
13. Airflow DAG 2: training_compile → versioned snapshots
14. Nimtable (Iceberg browser UI)

### Critical Pitfalls

1. **Data leakage through point-in-time violations** — SQL joins between messages and moderation decisions without temporal constraints cause the model to see future information during training. *Prevention:* Enforce `WHERE created_at < decided_at` on all training queries. Strip post-submission metadata. Use temporal train/eval splits.
2. **Preprocessing inconsistency between batch and online paths** — Two separate code paths (batch compile vs. real-time processor) drift silently. *Prevention:* Extract `text_cleaner.py` shared module used by BOTH paths. Golden dataset tests (100 hand-curated texts, both paths must produce identical output).
3. **Synthetic data distribution shift** — LLM-generated text is formulaic and doesn't capture real toxicity patterns (misspellings, slang, emoji usage). *Prevention:* Mix synthetic with real data, never train on 100% synthetic. Track real:synthetic ratio. Validate class distribution per source.
4. **Training data snapshot overwrites** — Writing to a fixed path without version tags means you can't reproduce what the model trained on. *Prevention:* Immutable snapshots with timestamps: `s3://bucket/training_data/v20260403-142301/`.
5. **Over-cleaning text data** — Aggressive preprocessing strips emojis, caps, and punctuation that carry toxicity signal. `"I HATE you 😡😡😡"` → `"i hate you"` loses ALL emotional signal. *Prevention:* Standardize emojis (don't remove), extract `caps_ratio` and `punctuation_count` as features.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Infrastructure & Ingestion
**Rationale:** Everything depends on storage being available and data flowing into the system. This is the critical path first step.
**Delivers:** Docker Compose with PostgreSQL, MinIO, Redis running. CSV ingestion working. Synthetic data generated and uploaded. FastAPI endpoints accepting traffic.
**Addresses:** DATA-01 (design doc), DATA-02 (MinIO setup), DATA-03 (ingestion + synthetic), DATA-04 (traffic generator)
**Avoids:** CSV parsing issues (Pitfall 14) — use `quoting=csv.QUOTE_ALL` and validate row count. HF rate limits (Pitfall 12) — implement retry with tenacity.
**Stack used:** PostgreSQL 16, MinIO, FastAPI, pandas, huggingface-hub, tenacity

### Phase 2: Real-time Processing Pipeline
**Rationale:** Depends on Redpanda and Redis being available, plus data flowing from Phase 1. Implements the online processing path.
**Delivers:** Redpanda event streaming, stream_consumer with rolling window features, Redis feature cache, online text preprocessing module.
**Addresses:** DATA-05 (online processor), real-time path components
**Avoids:** Preprocessing inconsistency (Pitfall 3) — build shared `text_cleaner.py` module NOW, before batch path. Over-cleaning (Pitfall 6) — keep emojis standardized, not removed.
**Stack used:** Redpanda, confluent-kafka, Redis, redis-py, emoji, regex, beautifulsoup4, ftfy

### Phase 3: Batch Pipeline & Training Data Compilation
**Rationale:** Requires data in PostgreSQL from Phase 1 and preprocessing module from Phase 2. This is the pipeline's primary output.
**Delivers:** Airflow DAGs (event_aggregation + training_compile), Iceberg tables, versioned training snapshots in MinIO, schema validation, class balance reporting.
**Addresses:** DATA-06 (batch pipeline), schema validation, data quality controls
**Avoids:** Data leakage (Pitfall 1) — temporal joins, strip post-submission metadata. Versioning failures (Pitfall 4) — immutable timestamped snapshots. Label noise (Pitfall 5) — track source_dataset column.
**Stack used:** Apache Airflow 3.1.8, PyIceberg 0.11.1, psycopg2-binary, pyarrow

### Phase 4: Polish, Config & Demo
**Rationale:** Core pipeline is functional. This phase adds differentiators and demo-ready quality.
**Delivers:** Configurable pipeline parameters (YAML config), deterministic seeds, data quality metrics report, design document finalization, demo video recording.
**Addresses:** Differentiators (config, reproducibility, quality metrics), DATA-01 finalization
**Avoids:** Non-reproducible demo state (Pitfall 13) — seeded randomness, fixed ports, command logs.
**Stack used:** PyYAML (config), existing pipeline with added logging

### Phase Ordering Rationale

- **Phase 1 first** because MinIO and PostgreSQL are prerequisites for everything. No data storage = no pipeline.
- **Phase 2 before Phase 3** because the shared preprocessing module (`text_cleaner.py`) must exist before the batch path uses it — building it in Phase 2 and reusing in Phase 3 prevents the #1 silent bug (preprocessing inconsistency).
- **Phase 3 last among core phases** because it depends on data flowing (Phase 1) and preprocessing being stable (Phase 2). Iceberg/Airflow setup is the most complex infrastructure work.
- **Phase 4 last** because polish and differentiators only matter when the core pipeline works. Config and reproducibility are low-effort, high-impact additions.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Batch Pipeline):** PyIceberg REST catalog setup on a single VM is non-trivial. May need to research SQLite-backed catalog or Nessie Docker setup. Check class lab materials for Iceberg patterns.
- **Phase 2 (Real-time):** Redpanda topic configuration and consumer group setup. Check if class labs cover this or if documentation diving is needed.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** Docker Compose + PostgreSQL + MinIO is well-documented in class labs. The `data-platform-chi` lab covers this exactly.
- **Phase 4 (Polish):** YAML config and deterministic seeds are standard Python patterns. No domain research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All library versions verified against PyPI on 2026-04-03. Class-mandated technologies confirmed. |
| Features | HIGH | Grounded in project architecture docs, DATA-01 through DATA-06 deliverables, and reference paper (arxiv:2208.03274). |
| Architecture | HIGH | Directly maps to `data-platform-chi` lab blueprint. Component boundaries, build order, and data flow patterns are from verified lab materials. |
| Pitfalls | HIGH | Data leakage and preprocessing inconsistency are well-documented in MadeWithML curriculum and OpenAI paper. Synthetic distribution shift is universally understood. |

**Overall confidence:** HIGH

### Gaps to Address

- **Airflow 3.x vs 2.x:** Course labs may teach Airflow 2.x patterns. If so, pin to `apache-airflow==2.11.1`. *Handle during Phase 3 planning by checking lab materials.*
- **PyIceberg catalog complexity:** REST catalog setup on single VM may require trial-and-error. *Handle by starting with plain Parquet in MinIO and adding Iceberg incrementally.*
- **HF API rate limits at scale:** Free tier = 1000 req/day. For 10K+ synthetic rows, may need HF Pro or batch optimization. *Handle by caching responses and using template-based fallback generation.*
- **Combined dataset label alignment:** The merged Reddit + Jigsaw dataset may have inconsistent labeling criteria between sources. *Handle by tracking `source_dataset` column and analyzing per-source label distributions during Phase 1 ingestion.*

## Sources

### Primary (HIGH confidence)
- `data-platform-chi` lab — architecture blueprint, Docker Compose patterns, PostgreSQL schema design
- PyPI verification (2026-04-03) — all library versions confirmed
- arxiv:2208.03274 — "A Holistic Approach to Undesired Content Detection in the Real World" (OpenAI, AAAI-23)

### Secondary (MEDIUM confidence)
- MadeWithML by Anyscale — preprocessing patterns, versioning best practices, testing curriculum
- Zulip API documentation — webhook payload format for dummy endpoint modeling
- HuggingFace Inference API docs — rate limits, client usage

### Tertiary (LOW confidence)
- PyIceberg 0.11.1 REST catalog setup — may need adjustment based on class lab specifics
- Airflow 3.x compatibility — new release (Apr 2025), class materials may lag

---
*Research completed: 2026-04-03*
*Ready for roadmap: yes*
