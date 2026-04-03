# Architecture

**Analysis Date:** 2026-04-03

## Pattern Overview

**Overall:** ML Microservice Pipeline (Pre-implementation — architecture defined, no source code yet)

**Key Characteristics:**
- Event-driven moderation: messages intercepted at submission, scored, and routed
- Dual-path data flow: real-time inference path + asynchronous batch training path
- Containerized deployment on Chameleon Cloud VMs
- Webhook-coupled integration with Zulip chat platform
- Tiered decision matrix based on confidence thresholds

**Current State:** Planning phase only. No source code, no entry points, no runnable application. The project has a design document (`Idea.md`), presentation/report artifacts, and a combined dataset CSV (~1.58M rows).

## Layers

**Inference Layer (Serving):**
- Purpose: Accept incoming messages, run model inference, return moderation decisions
- Contains: FastAPI endpoints, model loading, inference logic, decision routing
- Planned location: `src/serving/` or `src/api/`
- Depends on: Model artifacts (hateBERT), online processing layer
- Used by: Zulip webhooks (outgoing webhook → POST /messages)
- Team owner: Purvansh Arora

**Online Processing Layer (Data - Real-time):**
- Purpose: Clean and normalize raw messages before inference
- Contains: Markdown removal, emoji standardization, URL extraction, PII scrubbing
- Planned location: `src/data/online_processor.py`
- Depends on: Raw message payloads
- Used by: Inference layer
- Team owner: Rishabh Narayan

**Training Layer:**
- Purpose: Retrain hateBERT model on curated datasets
- Contains: Model fine-tuning, evaluation, artifact export
- Planned location: `src/training/`
- Depends on: Batch pipeline output (versioned training data from MinIO)
- Used by: CI/CD pipeline (triggered by 200 new verified flags or weekly schedule)
- Team owner: Aadarsh Lakshmi Narasiman

**Batch Pipeline Layer (Data - Async):**
- Purpose: Compile training data from production without leakage
- Contains: PostgreSQL queries, PII scrubbing, noise filtering, versioned snapshots
- Planned location: `src/data/compile_training_data.py`
- Depends on: PostgreSQL (admin decisions, flagged messages), MinIO (storage)
- Used by: Training layer
- Team owner: Rishabh Narayan

**Infrastructure Layer (DevOps):**
- Purpose: Provision, deploy, and manage all components
- Contains: IaC scripts, CI/CD pipelines, container orchestration
- Planned location: `infra/` or `deploy/`
- Depends on: Chameleon Cloud API (python-chi), Docker
- Used by: All other layers
- Team owner: Nitish KS

**Data Storage Layer:**
- Purpose: Persistent state and object storage
- Contains: PostgreSQL (application state), MinIO (raw/cleaned data, model artifacts)
- Planned location: External services (not application code)
- Depends on: Chameleon VM provisioning
- Used by: All layers

## Data Flow

**Real-time Inference Path:**

1. User sends message in Zulip
2. Zulip outgoing webhook triggers POST to FastAPI endpoint
3. Online processor cleans text (remove markdown, standardize emojis, extract URLs, scrub PII)
4. Cleaned text passed to hateBERT inference endpoint
5. Model returns two probability scores: [offensive_score, self_harm_score]
6. Decision matrix routes the message:
   - High offensive (>0.85): Auto-hide + record strike + route to admin queue
   - Medium offensive (0.60–0.85): Private warning + obscure message + flag for moderator
   - Low-medium self-harm (>0.30): Immediate admin alert + DM mental health resources (do NOT delete)
   - Below thresholds: Message passes through normally
7. Manual user reporting enabled as fail-safe for false negatives

**Batch Training Path:**

1. Scheduled job or trigger (200 verified flags / weekly fallback) initiates batch pipeline
2. Query PostgreSQL for recent admin decisions and user-reported messages (1-week candidate window)
3. Filter noise: remove bot notifications, spam, unresolved admin logs
4. Scrub PII using LLM-based detection
5. Strip post-submission metadata to prevent target leakage
6. Save versioned snapshot to MinIO (optionally Iceberg format)
7. Training layer consumes snapshot, fine-tunes hateBERT
8. New model artifact deployed via CI/CD pipeline

**Synthetic Data Generation Path:**

1. Ingestion script reads `combined_dataset.csv`
2. Synthetic data generation augments dataset (template-based or LLM-generated Zulip-style conversations)
3. Traffic generator dispatches synthetic HTTP requests to dummy FastAPI endpoints
4. Populates PostgreSQL with realistic test data

**State Management:**
- PostgreSQL: Synchronous writes for users, messages, moderation flags, bot decisions, strike counts
- MinIO: Asynchronous writes for raw messages, cleaned text, training dataset snapshots, model artifacts
- No in-memory state persistence — all state externalized

## Key Abstractions

**Message:**
- Purpose: Represents a single chat message flowing through the system
- Contains: raw text, cleaned text, timestamp, user ID, moderation scores, decision outcome
- Pattern: Data transfer object between layers

**ModerationDecision:**
- Purpose: Encodes the routing decision for a scored message
- Contains: action (hide/warn/pass), confidence score, admin queue flag, strike increment
- Pattern: Strategy pattern based on threshold matrix

**DatasetSnapshot:**
- Purpose: Versioned training data artifact
- Contains: cleaned text rows, labels (is_suicide, is_toxicity), version tag, generation timestamp
- Pattern: Immutable snapshot stored in MinIO

**OnlineProcessor:**
- Purpose: Text normalization pipeline for real-time inference
- Contains: markdown stripper, emoji normalizer, URL extractor, PII scrubber
- Pattern: Chain of responsibility (sequential transformations)

**SyntheticTrafficGenerator:**
- Purpose: Simulates realistic Zulip user traffic for testing
- Contains: message templates, HTTP request dispatching, rate control
- Pattern: Generator/producer pattern

## Entry Points

**FastAPI Application (Planned):**
- Location: `src/serving/main.py` (not yet created)
- Triggers: Zulip outgoing webhooks (POST /messages, POST /flags)
- Responsibilities: Receive messages, invoke processing + inference, return moderation actions

**Batch Pipeline (Planned):**
- Location: `src/data/compile_training_data.py` (not yet created)
- Triggers: Cron schedule or flag-count threshold (200 verified flags)
- Responsibilities: Query PostgreSQL, clean data, save to MinIO

**Ingestion Script (Planned):**
- Location: `src/data/ingest_and_expand.py` (not yet created)
- Triggers: Manual execution
- Responsibilities: Read `combined_dataset.csv`, augment with synthetic data, upload to MinIO

**Traffic Generator (Planned):**
- Location: `src/data/synthetic_traffic_generator.py` (not yet created)
- Triggers: Manual execution for load testing
- Responsibilities: Generate synthetic HTTP requests against dummy endpoints

**Infrastructure Provisioning (Planned):**
- Location: `infra/` scripts using python-chi (not yet created)
- Triggers: Manual execution or CI/CD
- Responsibilities: Provision Chameleon VMs, deploy Docker containers, configure MinIO/PostgreSQL

## Error Handling

**Strategy:** Fail-safe moderation — on inference failure, default to flagging for admin review rather than allowing potentially harmful content through

**Patterns:**
- Model inference timeout → queue message for manual review, do not display until cleared
- Database connection failure → retry with exponential backoff, log error
- MinIO upload failure → persist to local filesystem as fallback, alert DevOps
- Webhook delivery failure → Zulip retry mechanism (built-in)

## Cross-Cutting Concerns

**Logging:**
- Approach: Structured logging (JSON format) for all inference decisions
- Audit trail: Every moderation action logged with confidence score and timestamp

**Validation:**
- Approach: Input validation at API boundary (FastAPI Pydantic models)
- Text length limits, required fields, score range checks

**Authentication:**
- Approach: Zulip webhook authentication tokens
- API key validation on all incoming requests

**Monitoring:**
- Model drift detection via retraining trigger thresholds
- Latency tracking for P99 < 200ms target
- Throughput monitoring for 15–20 RPS capacity

---

*Architecture analysis: 2026-04-03*
*Project is in pre-implementation planning phase — architecture reflects design documents, not deployed system*
