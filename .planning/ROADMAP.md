# Roadmap: ChatSentry Data Pipeline

## Overview

Four-phase buildout of the ChatSentry data pipeline on a single KVM@TACC VM. Phase 1 establishes infrastructure and ingests real + synthetic data. Phase 2 builds real-time text preprocessing. Phase 3 compiles versioned training datasets with leakage prevention. Phase 4 documents the design and adds YAML configuration. Each phase produces a demo-video-ready deliverable.

## Phases

- [~] **Phase 1: Infrastructure & Ingestion** - Docker Compose stack running, CSV ingested, synthetic data generated and uploaded to MinIO — 4 gaps need closure
- [ ] **Phase 2: Real-time Processing** - Messages processed through shared text preprocessing module in real-time
- [ ] **Phase 3: Batch Pipeline** - Versioned training datasets compiled from production data without leakage
- [ ] **Phase 4: Design Doc & Config** - Pipeline documented with schemas/diagrams and configurable via YAML

## Phase Details

### Phase 1: Infrastructure & Ingestion
**Goal**: Data flows into the system — all services running, CSV ingested, synthetic data generated
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INGEST-01, INGEST-02, INGEST-03
**Success Criteria** (what must be TRUE):
  1. `docker compose up` brings up PostgreSQL, MinIO, FastAPI, and supporting services on the KVM VM
  2. PostgreSQL schema has tables for users, messages, flags, and moderation with UUIDs, source tracking, and timestamps
  3. MinIO buckets `zulip-raw-messages` and `zulip-training-data` are created and browsable at :9001
  4. Ingestion script reads `combined_dataset.csv` (~1.58M rows, chunked) and uploads to MinIO
  5. Synthetic data generated via HuggingFace API with source tagging (real vs synthetic) and uploaded to MinIO
**Plans**: 5 plans

Plans:
- [ ] 01-01: Docker Compose & service scaffolding (PostgreSQL, MinIO, FastAPI)
- [x] 01-02: PostgreSQL schema init & MinIO bucket creation
- [x] 01-03: CSV ingestion script (chunked reading, MinIO upload)
- [ ] 01-04: Synthetic data generator (HuggingFace API, source tagging)
- [x] 01-05: Gap closure — HF_TOKEN, source columns, lint fixes

### Phase 2: Real-time Processing
**Goal**: Messages processed in real-time with clean, standardized text via a shared preprocessing module
**Depends on**: Phase 1
**Requirements**: INGEST-04, ONLINE-01, ONLINE-02, ONLINE-03, ONLINE-04, ONLINE-05, ONLINE-06
**Success Criteria** (what must be TRUE):
  1. Synthetic HTTP traffic generator sends messages to FastAPI endpoints (POST /messages, POST /flags)
  2. Message text is cleaned: markdown stripped, emojis standardized to :shortcode:, URLs extracted
  3. PII (emails, phone numbers, usernames) is scrubbed from message text
  4. Unicode normalization fixes mojibake in scraped Reddit data via ftfy
  5. `text_cleaner.py` shared module exists and is used by both online and batch processing paths
**Plans**: TBD

Plans:
- [ ] 02-01: Synthetic traffic generator hitting FastAPI endpoints
- [ ] 02-02: text_cleaner.py shared module (markdown, emoji, URL, PII, Unicode)
- [ ] 02-03: Online preprocessing integration with FastAPI message ingestion

### Phase 3: Batch Pipeline
**Goal**: Versioned training datasets compiled from production data without data leakage
**Depends on**: Phase 1, Phase 2
**Requirements**: BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05
**Success Criteria** (what must be TRUE):
  1. Batch pipeline queries PostgreSQL and produces versioned training/evaluation datasets
  2. Temporal data leakage is prevented — training queries enforce `WHERE created_at < decided_at`
  3. Immutable versioned snapshots stored in MinIO with timestamp tags (e.g., `v20260403-142301/`)
  4. Post-submission metadata is stripped before training data export
  5. Dataset split into train/test/validation sets, stratified by is_suicide and is_toxicity labels
**Plans**: TBD

Plans:
- [ ] 03-01: Batch compilation script (PostgreSQL query → training dataset)
- [ ] 03-02: Temporal leakage prevention & metadata stripping
- [ ] 03-03: Stratified train/test/validation split
- [ ] 03-04: Versioned snapshot upload to MinIO

### Phase 4: Design Doc & Config
**Goal**: Pipeline documented with schemas/flow diagrams and configurable via YAML
**Depends on**: Phase 1, Phase 2, Phase 3
**Requirements**: DESIGN-01, CONFIG-01
**Success Criteria** (what must be TRUE):
  1. High-level data design document exists with schemas, data repositories, and data flow diagrams
  2. All pipeline parameters (paths, chunk sizes, API keys, bucket names) are configurable via YAML — no hardcoded values
**Plans**: TBD

Plans:
- [ ] 04-01: Data design document (schemas, repositories, flow diagrams)
- [ ] 04-02: YAML configuration extraction for all pipeline parameters

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Ingestion | 4/5 | Gap closure | - |
| 2. Real-time Processing | 0/3 | Not started | - |
| 3. Batch Pipeline | 0/4 | Not started | - |
| 4. Design Doc & Config | 0/2 | Not started | - |
