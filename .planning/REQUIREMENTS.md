# Requirements: ChatSentry Data Pipeline

**Defined:** 2026-04-03
**Core Value:** Deliver a complete, reproducible data pipeline with versioned training data on Chameleon that the ML training team can consume — all demonstrated via 6 recorded demo videos.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: PostgreSQL schema with tables: users, messages, flags, moderation (UUIDs, source tracking, timestamps)
- [x] **INFRA-02**: MinIO buckets created: zulip-raw-messages, zulip-training-data (browsable at :9001)
- [ ] **INFRA-03**: FastAPI dummy endpoints: POST /messages, POST /flags (accepting synthetic traffic)
- [x] **INFRA-04**: Docker Compose file orchestrating all services on single KVM@TACC VM

### Ingestion

- [x] **INGEST-01**: Ingestion script reads combined_dataset.csv (1.58M rows, chunked to avoid OOM)
- [x] **INGEST-02**: Synthetic data generation via HuggingFace API (toxic + benign Zulip-style messages)
- [x] **INGEST-03**: Ingested + synthetic data uploaded to MinIO with source tagging (real vs synthetic)
- [ ] **INGEST-04**: Data generator sends synthetic HTTP traffic to FastAPI endpoints

### Online Processing

- [ ] **ONLINE-01**: Markdown removal from message text
- [ ] **ONLINE-02**: Emoji standardization to :shortcode: format
- [ ] **ONLINE-03**: URL extraction from message text
- [ ] **ONLINE-04**: PII scrubbing (email, phone, username patterns)
- [ ] **ONLINE-05**: Unicode normalization (fix mojibake via ftfy)
- [ ] **ONLINE-06**: Shared text_cleaner.py module used by both online and batch paths

### Batch Pipeline

- [ ] **BATCH-01**: Batch pipeline compiles versioned training/evaluation datasets from PostgreSQL "production" data
- [ ] **BATCH-02**: Temporal data leakage prevention (WHERE created_at < decided_at on all training queries)
- [ ] **BATCH-03**: Versioned snapshots in MinIO (immutable, timestamp-tagged: v20260403-142301/)
- [ ] **BATCH-04**: Post-submission metadata stripped before training data export
- [ ] **BATCH-05**: Dataset split into train/test/validation sets (stratified by is_suicide and is_toxicity labels)

### Design & Config

- [x] **DESIGN-01**: High-level data design document with schemas, data repositories, and data flow diagrams
- [x] **CONFIG-01**: Configurable pipeline parameters via YAML (not hardcoded)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Data Quality

- **QUALITY-01**: Data quality metrics report (null rates, duplicate rates, text length distribution)
- **QUALITY-02**: Class balance reporting before/after every pipeline stage

### Advanced Features

- **ADV-01**: Deterministic seeds for reproducible pipeline runs
- **ADV-02**: Redpanda event streaming for real-time pipeline
- **ADV-03**: Redis feature store for rolling window counts
- **ADV-04**: Airflow DAG orchestration (event_aggregation + training_compile)
- **ADV-05**: Iceberg tables for versioned training data

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML model training | Handled by Training specialist (Aadarsh) |
| Model serving/inference | Handled by Serving specialist (Purvansh) |
| Infrastructure (K8s, CI/CD) | Handled by DevOps specialist (Nitish) |
| Real Zulip integration | Use dummy FastAPI endpoints instead |
| GPU-based LLM generation | KVM@TACC has no GPU; use HuggingFace API |
| Active learning sampling | Too complex for initial scope |
| Data drift detection | Requires production traffic not yet available |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Complete |
| INGEST-01 | Phase 1 | Complete |
| INGEST-02 | Phase 1 | Complete |
| INGEST-03 | Phase 1 | Complete |
| INGEST-04 | Phase 2 | Pending |
| ONLINE-01 | Phase 2 | Pending |
| ONLINE-02 | Phase 2 | Pending |
| ONLINE-03 | Phase 2 | Pending |
| ONLINE-04 | Phase 2 | Pending |
| ONLINE-05 | Phase 2 | Pending |
| ONLINE-06 | Phase 2 | Pending |
| BATCH-01 | Phase 3 | Pending |
| BATCH-02 | Phase 3 | Pending |
| BATCH-03 | Phase 3 | Pending |
| BATCH-04 | Phase 3 | Pending |
| BATCH-05 | Phase 3 | Pending |
| DESIGN-01 | Phase 4 | Complete |
| CONFIG-01 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-03*
*Last updated: 2026-04-03 after initial definition*
