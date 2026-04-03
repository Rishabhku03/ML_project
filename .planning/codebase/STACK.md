# Technology Stack

**Analysis Date:** 2025-04-03

## Project Status

**Pre-implementation phase.** No application code exists yet. This document captures the **planned** technology stack as described in project documentation (`Idea.md`, `MLOps-Project-Report-TeamChatSentry.txt`, `MLOps_-_Project-Presentation-Team-ChatSentry.txt`).

## Languages

**Primary:**
- Python 3.x - All application code (ML inference, data pipelines, API server, infrastructure provisioning)

**Secondary:**
- SQL - PostgreSQL queries for data retrieval and storage
- YAML/Bash - Infrastructure configuration and deployment scripts

## Runtime

**Environment:**
- Python 3.x runtime
- Docker containers for service isolation

**Package Manager:**
- pip (assumed, no `requirements.txt` or `pyproject.toml` present yet)
- Lockfile: Not present

## Frameworks

**Core:**
- FastAPI - Asynchronous inference API server for message moderation
  - Handles webhook callbacks from Zulip
  - Performance target: <200ms P99 latency, 15-20 RPS

**ML/AI:**
- HuggingFace Transformers - HateBERT model serving
  - Base model: English BERT base uncased (0.1B parameters, FP-32)
  - Fine-tuned on Jigsaw Toxic Comment Classification and suicide detection datasets

**Infrastructure:**
- python-chi - Chameleon Cloud infrastructure provisioning (IaC)
- Docker - Containerization for all services

**Testing:**
- Not yet specified in documentation

## Key Dependencies

**Critical:**
- `fastapi` - Web framework for inference API
- `transformers` (HuggingFace) - ML model loading and inference
- `psycopg2` or `asyncpg` - PostgreSQL database client
- `minio` (MinIO Python SDK) - Object storage client
- `python-chi` - Chameleon Cloud infrastructure management

**Infrastructure:**
- `uvicorn` - ASGI server for FastAPI
- `pandas` - Dataset processing (`combined_dataset.csv`)
- `pydantic` - Request/response validation (FastAPI dependency)

## Data

**Training Datasets:**
- `combined_dataset.csv` - Combined suicide detection and toxicity dataset
  - Columns: `text`, `is_suicide`, `is_toxicity`
  - Source datasets:
    - Jigsaw Toxic Comment Classification Challenge (27.62 MB, 200k rows, Wikipedia)
    - Suicide and Depression Detection (166.9 MB, 230k rows, Reddit)

**Data Labels:**
- Toxicity: `toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate` (one-hot encoding)
- Self-harm: `suicide`, `non-suicide` (binary)

## Configuration

**Environment:**
- Configuration via environment variables (not yet defined)
- Planned: PostgreSQL connection strings, MinIO credentials, Zulip webhook secrets

**Build:**
- No build configuration files present yet

## Platform Requirements

**Development:**
- Python 3.x environment
- Docker for local service containers
- Access to Chameleon Cloud (KVM@TACC) for MinIO and VM provisioning

**Production:**
- Single VM: 4 vCPU / 16GB RAM on Chameleon Cloud
- Runs: Zulip app, PostgreSQL, ML inference API (isolated containers)
- Model retraining: Dynamically provisions temporary VM via CI/CD pipeline
- User uploads: Routed to S3-compatible bucket (MinIO)

## Planned Architecture Components

**Data Specialist (Rishabh Narayan):**
- `ingest_and_expand.py` - Data ingestion and synthetic data generation
- `online_processor.py` - Real-time text preprocessing (markdown removal, emoji standardization, URL extraction)
- `compile_training_data.py` - Batch training data compilation from PostgreSQL

**Serving (Purvansh Arora):**
- FastAPI endpoints: `POST /messages`, `POST /flags`
- Tiered decision matrix based on model confidence scores

**DevOps (Nitish KS):**
- Infrastructure as Code via python-chi
- CI/CD pipelines for deployment and model retraining
- Model freshness triggers: 200 new verified flags or weekly fallback

---

*Stack analysis: 2025-04-03*
*Note: Pre-implementation phase - stack based on project documentation, not actual code*
