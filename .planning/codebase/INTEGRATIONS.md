# External Integrations

**Analysis Date:** 2025-04-03

## Project Status

**Pre-implementation phase.** No application code exists yet. This document captures the **planned** integrations as described in project documentation (`Idea.md`, `MLOps-Project-Report-TeamChatSentry.txt`, `MLOps_-_Project-Presentation-Team-ChatSentry.txt`).

## APIs & External Services

**Chat Platform:**
- Zulip - Open-source communication platform being moderated
  - Integration method: Outgoing webhooks (intercepts messages at submission)
  - Endpoints: `POST /messages`, `POST /flags`
  - Auth: Webhook secrets (env vars, not yet defined)

**ML Model Registry:**
- HuggingFace - HateBERT model source
  - Model: `HateBERT` (English BERT base uncased, fine-tuned on 1M+ Reddit posts from banned communities)
  - Integration: `transformers` library for model loading
  - Parameters: 0.1B, FP-32 precision
  - Output: Two probability scores (offensive 0-1, self-harm 0-1)

**Synthetic Data Generation:**
- Local LLM (planned) - For augmenting training data
  - Purpose: Generate synthetic Zulip conversations (benign + toxic)
  - Integration: Referenced in `llm-chi` lab materials

## Data Storage

**Databases:**
- PostgreSQL - Application state database
  - Stores: Users, messages/comments, moderation flags, bot decisions
  - Connection: Via env var (not yet defined)
  - Write path: Synchronous via Zulip/FastAPI
  - Used by: `compile_training_data.py` for batch training data queries

**Object Storage / Data Lake:**
- MinIO (on Chameleon Cloud) - S3-compatible object storage
  - Buckets planned:
    - `zulip-raw-messages` - Raw unstructured text payloads
    - `zulip-training-data` - Cleaned messages and training dataset snapshots
  - Connection: MinIO Python SDK
  - Auth: MinIO credentials (env vars, not yet defined)
  - UI: Port 9001 (exposed via security groups for course staff)
  - Provisioning: Docker container on Chameleon VM via `python-chi`

**Versioned Data Layer:**
- Apache Iceberg / DVC - Versioned dataset snapshots
  - Purpose: Prevent data leakage, associate model versions with exact data states
  - Storage: Backed by MinIO
  - Versioning: Distinct version tags for each training data snapshot

## Authentication & Identity

**Zulip Integration:**
- Zulip outgoing webhooks for message interception
  - Auth: Webhook token/secret (env var, not yet defined)

**Chameleon Cloud:**
- python-chi SDK for infrastructure provisioning
  - Auth: Chameleon credentials (env vars, not yet defined)
  - Scope: KVM@TACC site

## Model Serving & Inference

**Tiered Decision Matrix:**
- High Confidence (Offensive > 0.85):
  - Action: Auto-hide message + record user strike
  - Review: Route to admin queue
- Medium Confidence (Offensive 0.60-0.85):
  - Action: Private warning to user + obscure message
  - Review: Flag for moderator validation (no strike yet)
- Self-Harm Detection (> 0.30):
  - Protocol: Do NOT delete (avoids isolation)
  - Action: Immediate admin alert + DM mental health resources
  - Lower threshold prioritizes user safety
- Fail-Safe: Manual user reporting for edge cases/false negatives

## Data Flow

**Real-time Inference Path:**
1. **Arrival:** Raw user message intercepted at submission via Zulip webhook
2. **Processing:** Text cleaning - remove markdown, standardize emojis, extract URLs, scrub PII
3. **Inference:** Model scores cleaned text for toxicity and self-harm
4. **Routing:** Apply moderation based on tiered decision matrix

**Batch Training Pipeline:**
1. **Collection:** Async collection of human admin decisions and user-reported messages
2. **Candidate Window:** Data from recent one-week period only
3. **Privacy:** LLM-based PII scrubbing
4. **Noise Reduction:** Filter bot notifications, spam, unresolved admin logs
5. **Leakage Prevention:** Strip metadata generated post-message
6. **Storage:** Curated snapshot saved to MinIO with version tag

## Monitoring & Observability

**Not yet specified in documentation.**

Planned based on system requirements:
- Error tracking: Not defined
- Logging: Container stdout/stderr
- Metrics: Latency (<200ms P99 target), throughput (15-20 RPS target)

## CI/CD & Deployment

**Hosting:**
- Chameleon Cloud (KVM@TACC) - Single VM deployment
  - VM spec: 4 vCPU / 16GB RAM
  - Services: Zulip app, PostgreSQL, ML inference API (Docker containers)

**CI Pipeline:**
- Infrastructure as Code via python-chi
- Model retraining triggers:
  - 200 new verified flags
  - Weekly fallback schedule
- Dynamic VM provisioning for retraining (provision, train, save artifacts, destroy)

## Environment Configuration

**Required env vars (planned):**
- PostgreSQL connection string
- MinIO credentials (access key, secret key, endpoint)
- Zulip webhook secrets
- Chameleon Cloud credentials

**Secrets location:**
- Not yet defined (likely `.env` file or Chameleon secrets management)

## Webhooks & Callbacks

**Incoming:**
- Zulip outgoing webhooks → FastAPI endpoints
  - Endpoint: `POST /messages` (new message interception)
  - Endpoint: `POST /flags` (user-reported messages)
  - Verification: Webhook signature validation (not yet implemented)

**Outgoing:**
- Zulip API calls for moderation actions:
  - Hide offensive messages
  - Send warnings to users
  - Alert admins for self-harm detection
  - DM mental health resources

## Scaling Limits

**Current capacity modeling:**
- Total users: 300 (student organization)
- Steady-state: 30-40 concurrent users
- Peak load: ~100 concurrent users, ~15 messages/sec
- Target throughput: 15-20 RPS

---

*Integration audit: 2025-04-03*
*Note: Pre-implementation phase - integrations based on project documentation, not actual code*
