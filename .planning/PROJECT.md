# ChatSentry — Data Pipeline

## What This Is

ChatSentry is an AI-powered content moderation system for Zulip chat. This project covers the **Data Specialist** (Rishabh Narayan) deliverables: a complete, reproducible data pipeline running on Chameleon Cloud that ingests toxic/suicide detection data, expands it synthetically, serves real-time text preprocessing, and compiles versioned training data for the ML team. The pipeline produces 6 demo videos showing each component end-to-end.

## Core Value

Deliver a self-contained, reproducible data pipeline with versioned training data on Chameleon that the ML training team can consume — all demonstrated via 6 recorded demo videos.

## Requirements

### Validated

- **INFRA-01**: PostgreSQL schema with tables — validated in Phase 01 (gap closure fixed source columns on all 4 tables)
- **INFRA-02**: MinIO buckets created — validated in Phase 01
- **INFRA-03**: FastAPI dummy endpoints POST /messages, POST /flags — validated in Phase 01
- **INFRA-04**: Docker Compose orchestration — validated in Phase 01 (gap closure added HF_TOKEN)
- **INGEST-01**: CSV ingestion script — validated in Phase 01
- **INGEST-02**: Synthetic data generation via HuggingFace API — validated in Phase 01
- **INGEST-03**: Data uploaded to MinIO with source tagging — validated in Phase 01

### Active

- [ ] **DATA-01**: High-level data design document with schemas, data repositories, and data flow diagrams
- [ ] **DATA-02**: Live MinIO object storage bucket on Chameleon (browsable by course staff)
- [ ] **DATA-03**: Ingestion pipeline that reads `combined_dataset.csv`, generates synthetic data via HuggingFace API, and uploads to MinIO
- [ ] **DATA-04**: Synthetic data generator that hits dummy FastAPI endpoints with realistic Zulip-style messages
- [ ] **DATA-05**: Online feature computation — real-time text preprocessing (markdown removal, emoji standardization, URL extraction) integrate-able with serving
- [ ] **DATA-06**: Batch pipeline that compiles versioned training/evaluation datasets from "production" data, avoiding data leakage

### Out of Scope

- **ML model training** — handled by Training specialist (Aadarsh)
- **Model serving/inference** — handled by Serving specialist (Purvansh)
- **Infrastructure provisioning (Kubernetes, CI/CD)** — handled by DevOps specialist (Nitish)
- **Zulip integration** — we use dummy FastAPI endpoints, not real Zulip webhooks
- **Production deployment** — this is an initial implementation for course deliverables

## Context

- **Course**: NYU MLOps (Spring 2026)
- **Team**: 4 members, each on separate Chameleon VMs
- **Dataset**: `combined_dataset.csv` — 1,586,127 rows, columns: `text` (string), `is_suicide` (binary), `is_toxicity` (binary). Sources: Jigsaw Toxic Comment Classification + Suicide and Depression Detection (Reddit)
- **Reference paper**: arxiv:2208.03274 — "A Holistic Approach to Undesired Content Detection in the Real World" (OpenAI, AAAI-23). Key insight: data quality control, active learning for rare events (suicide is rare), and data leakage prevention are critical
- **Class materials**: python-chi, PostgreSQL, MinIO, Docker Compose, FastAPI, Redpanda (Kafka), Redis, Airflow, Iceberg, PyIceberg — all from NYU MLOps labs
- **Synthetic data approach**: HuggingFace API for LLM-generated Zulip-style conversations (KVM@TACC has no GPU for local LLM inference)

## Constraints

- **Tech stack**: Python 3.x, Docker Compose, tools from NYU MLOps labs only
- **Infrastructure**: Single KVM@TACC VM (m1.xlarge), no GPU
- **External dependencies**: HuggingFace API for synthetic text generation (no GPU on KVM)
- **Deliverables**: 6 demo videos + repository artifacts (code that runs the pipeline)
- **Dataset size**: ~1.58M rows, under 5GB threshold — requires synthetic expansion per course requirements
- **Timeline**: Course project deadline

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| KVM@TACC (no GPU) | Standard VM site for data pipeline; GPU not needed for data work | Validated Phase 01 |
| HuggingFace API for synthetic data | No local GPU; external API enables LLM text generation | Validated Phase 01 |
| Separate VMs per team member | Each specialist owns their infrastructure independently | — Pending |
| Docker Compose for orchestration | Matches course lab patterns (data-platform-chi) | Validated Phase 01 |
| Dummy FastAPI endpoints | Simulate Zulip without real chat platform dependency | Validated Phase 01 |
| Mistral-7B-Instruct via featherless-ai | Free-tier HF Inference API provider for synthetic generation | Settled Phase 01 |
| 50K-row CSV chunks to MinIO (no Parquet) | Simplicity; course requirement for object storage ingestion | Settled Phase 01 |
| Prompt-guided labeling (D-13) | Labels from prompt instruction, not post-hoc classification | Settled Phase 01 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-03 after Phase 01 completion (infrastructure + ingestion + gap closure)*
