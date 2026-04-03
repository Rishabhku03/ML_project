<!-- GSD:project-start source:PROJECT.md -->
## Project

**ChatSentry — Data Pipeline**

ChatSentry is an AI-powered content moderation system for Zulip chat. This project covers the **Data Specialist** (Rishabh Narayan) deliverables: a complete, reproducible data pipeline running on Chameleon Cloud that ingests toxic/suicide detection data, expands it synthetically, serves real-time text preprocessing, and compiles versioned training data for the ML team. The pipeline produces 6 demo videos showing each component end-to-end.

**Core Value:** Deliver a self-contained, reproducible data pipeline with versioned training data on Chameleon that the ML training team can consume — all demonstrated via 6 recorded demo videos.

### Constraints

- **Tech stack**: Python 3.x, Docker Compose, tools from NYU MLOps labs only
- **Infrastructure**: Single KVM@TACC VM (m1.xlarge), no GPU
- **External dependencies**: HuggingFace API for synthetic text generation (no GPU on KVM)
- **Deliverables**: 6 demo videos + repository artifacts (code that runs the pipeline)
- **Dataset size**: ~1.58M rows, under 5GB threshold — requires synthetic expansion per course requirements
- **Timeline**: Course project deadline
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Project Status
## Languages
- Python 3.x - All application code (ML inference, data pipelines, API server, infrastructure provisioning)
- SQL - PostgreSQL queries for data retrieval and storage
- YAML/Bash - Infrastructure configuration and deployment scripts
## Runtime
- Python 3.x runtime
- Docker containers for service isolation
- pip (assumed, no `requirements.txt` or `pyproject.toml` present yet)
- Lockfile: Not present
## Frameworks
- FastAPI - Asynchronous inference API server for message moderation
- HuggingFace Transformers - HateBERT model serving
- python-chi - Chameleon Cloud infrastructure provisioning (IaC)
- Docker - Containerization for all services
- Not yet specified in documentation
## Key Dependencies
- `fastapi` - Web framework for inference API
- `transformers` (HuggingFace) - ML model loading and inference
- `psycopg2` or `asyncpg` - PostgreSQL database client
- `minio` (MinIO Python SDK) - Object storage client
- `python-chi` - Chameleon Cloud infrastructure management
- `uvicorn` - ASGI server for FastAPI
- `pandas` - Dataset processing (`combined_dataset.csv`)
- `pydantic` - Request/response validation (FastAPI dependency)
## Data
- `combined_dataset.csv` - Combined suicide detection and toxicity dataset
- Toxicity: `toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate` (one-hot encoding)
- Self-harm: `suicide`, `non-suicide` (binary)
## Configuration
- Configuration via environment variables (not yet defined)
- Planned: PostgreSQL connection strings, MinIO credentials, Zulip webhook secrets
- No build configuration files present yet
## Platform Requirements
- Python 3.x environment
- Docker for local service containers
- Access to Chameleon Cloud (KVM@TACC) for MinIO and VM provisioning
- Single VM: 4 vCPU / 16GB RAM on Chameleon Cloud
- Runs: Zulip app, PostgreSQL, ML inference API (isolated containers)
- Model retraining: Dynamically provisions temporary VM via CI/CD pipeline
- User uploads: Routed to S3-compatible bucket (MinIO)
## Planned Architecture Components
- `ingest_and_expand.py` - Data ingestion and synthetic data generation
- `online_processor.py` - Real-time text preprocessing (markdown removal, emoji standardization, URL extraction)
- `compile_training_data.py` - Batch training data compilation from PostgreSQL
- FastAPI endpoints: `POST /messages`, `POST /flags`
- Tiered decision matrix based on model confidence scores
- Infrastructure as Code via python-chi
- CI/CD pipelines for deployment and model retraining
- Model freshness triggers: 200 new verified flags or weekly fallback
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Project State
- `Idea.md` — Implementation plan for Data specialist
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report
- `MLOps_-_Project-Presentation-Team-ChatSentry.txt` — Presentation deck
## Naming Patterns
- Use `snake_case` for all Python files (e.g., `ingest_and_expand.py`, `online_processor.py`)
- Use descriptive names matching purpose: `compile_training_data.py`, `synthetic_traffic_generator.py`
- Test files: `test_<module_name>.py` alongside source, or in `tests/` directory
- `snake_case` for all functions and methods
- Verb-first naming: `process_message()`, `clean_text()`, `upload_to_minio()`
- Async functions: no special prefix, use `async def` naturally
- `snake_case` for variables
- `UPPER_SNAKE_CASE` for constants and configuration values (e.g., `TOXICITY_THRESHOLD_HIGH = 0.85`)
- No leading underscores for private members unless truly module-internal
- `PascalCase` for classes and Pydantic models (e.g., `ModerationResult`, `MessagePayload`)
- `PascalCase` for type aliases
- Use Pydantic `BaseModel` for request/response schemas in FastAPI
## Code Style
- Use `black` for auto-formatting (standard Python)
- Use `ruff` or `flake8` for linting
- 88-character line length (black default)
- Double quotes for strings (black default)
- Type hints on all function signatures
- Enforce `flake8` or `ruff` with sensible defaults
- No `print()` in production code — use `logging` module
- Run: `ruff check .` or `flake8 .`
- `pyproject.toml` — project metadata, dependencies, tool config
- `.flake8` or `ruff.toml` — linting rules
## Import Organization
- Blank line between each group
- Alphabetical within each group
- `from` imports after `import` statements within each group
## Error Handling
- Use custom exception classes for domain errors (e.g., `ModerationError`, `DataIngestionError`)
- Catch specific exceptions, not bare `except:`
- FastAPI: use `HTTPException` for API errors with appropriate status codes
- Log error with context before re-raising
- Raise on invalid input, missing dependencies, invariant violations
- Return structured error responses from API endpoints
- Use `logging.exception()` in catch blocks to capture stack traces
## Logging
- Python `logging` module, configured centrally
- Levels: DEBUG, INFO, WARNING, ERROR (standard Python levels)
- Get logger per module: `logger = logging.getLogger(__name__)`
- Structured context: `logger.info("Processing message", extra={"message_id": msg_id})`
- Log at service boundaries: API entry points, MinIO operations, DB queries
- No `print()` statements in committed code
## Comments
- Explain ML/data pipeline decisions (thresholds, window sizes, preprocessing choices)
- Document business rules from the moderation tier matrix
- Explain non-obvious data transformations (PII scrubbing, leakage prevention)
- Avoid obvious comments
- Use Google-style or NumPy-style docstrings for all public functions
- Include `Args`, `Returns`, `Raises` sections
- Document Pydantic model fields with `Field(description=...)`
## Function Design
- Keep functions under 50 lines
- Extract data transformation steps into named helper functions
- One responsibility per function
- Max 3-4 positional parameters
- Use Pydantic models or dataclasses for complex inputs
- Destructure where possible
- Use Pydantic models for structured return values
- Return early for guard clauses
- Use `Optional[T]` or `Union[T, None]` for nullable returns
## Module Design
- Use `__init__.py` to expose public API per package
- Keep internal helpers private (leading underscore or not exported)
- Organize by concern: `data/`, `api/`, `models/`, `utils/`
- `data/` — ingestion, preprocessing, batch pipelines
- `api/` — FastAPI routes and request handling
- `models/` — Pydantic schemas, ML model wrappers
- `utils/` — shared helpers (text cleaning, MinIO client)
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Event-driven moderation: messages intercepted at submission, scored, and routed
- Dual-path data flow: real-time inference path + asynchronous batch training path
- Containerized deployment on Chameleon Cloud VMs
- Webhook-coupled integration with Zulip chat platform
- Tiered decision matrix based on confidence thresholds
## Layers
- Purpose: Accept incoming messages, run model inference, return moderation decisions
- Contains: FastAPI endpoints, model loading, inference logic, decision routing
- Planned location: `src/serving/` or `src/api/`
- Depends on: Model artifacts (hateBERT), online processing layer
- Used by: Zulip webhooks (outgoing webhook → POST /messages)
- Team owner: Purvansh Arora
- Purpose: Clean and normalize raw messages before inference
- Contains: Markdown removal, emoji standardization, URL extraction, PII scrubbing
- Planned location: `src/data/online_processor.py`
- Depends on: Raw message payloads
- Used by: Inference layer
- Team owner: Rishabh Narayan
- Purpose: Retrain hateBERT model on curated datasets
- Contains: Model fine-tuning, evaluation, artifact export
- Planned location: `src/training/`
- Depends on: Batch pipeline output (versioned training data from MinIO)
- Used by: CI/CD pipeline (triggered by 200 new verified flags or weekly schedule)
- Team owner: Aadarsh Lakshmi Narasiman
- Purpose: Compile training data from production without leakage
- Contains: PostgreSQL queries, PII scrubbing, noise filtering, versioned snapshots
- Planned location: `src/data/compile_training_data.py`
- Depends on: PostgreSQL (admin decisions, flagged messages), MinIO (storage)
- Used by: Training layer
- Team owner: Rishabh Narayan
- Purpose: Provision, deploy, and manage all components
- Contains: IaC scripts, CI/CD pipelines, container orchestration
- Planned location: `infra/` or `deploy/`
- Depends on: Chameleon Cloud API (python-chi), Docker
- Used by: All other layers
- Team owner: Nitish KS
- Purpose: Persistent state and object storage
- Contains: PostgreSQL (application state), MinIO (raw/cleaned data, model artifacts)
- Planned location: External services (not application code)
- Depends on: Chameleon VM provisioning
- Used by: All layers
## Data Flow
- PostgreSQL: Synchronous writes for users, messages, moderation flags, bot decisions, strike counts
- MinIO: Asynchronous writes for raw messages, cleaned text, training dataset snapshots, model artifacts
- No in-memory state persistence — all state externalized
## Key Abstractions
- Purpose: Represents a single chat message flowing through the system
- Contains: raw text, cleaned text, timestamp, user ID, moderation scores, decision outcome
- Pattern: Data transfer object between layers
- Purpose: Encodes the routing decision for a scored message
- Contains: action (hide/warn/pass), confidence score, admin queue flag, strike increment
- Pattern: Strategy pattern based on threshold matrix
- Purpose: Versioned training data artifact
- Contains: cleaned text rows, labels (is_suicide, is_toxicity), version tag, generation timestamp
- Pattern: Immutable snapshot stored in MinIO
- Purpose: Text normalization pipeline for real-time inference
- Contains: markdown stripper, emoji normalizer, URL extractor, PII scrubber
- Pattern: Chain of responsibility (sequential transformations)
- Purpose: Simulates realistic Zulip user traffic for testing
- Contains: message templates, HTTP request dispatching, rate control
- Pattern: Generator/producer pattern
## Entry Points
- Location: `src/serving/main.py` (not yet created)
- Triggers: Zulip outgoing webhooks (POST /messages, POST /flags)
- Responsibilities: Receive messages, invoke processing + inference, return moderation actions
- Location: `src/data/compile_training_data.py` (not yet created)
- Triggers: Cron schedule or flag-count threshold (200 verified flags)
- Responsibilities: Query PostgreSQL, clean data, save to MinIO
- Location: `src/data/ingest_and_expand.py` (not yet created)
- Triggers: Manual execution
- Responsibilities: Read `combined_dataset.csv`, augment with synthetic data, upload to MinIO
- Location: `src/data/synthetic_traffic_generator.py` (not yet created)
- Triggers: Manual execution for load testing
- Responsibilities: Generate synthetic HTTP requests against dummy endpoints
- Location: `infra/` scripts using python-chi (not yet created)
- Triggers: Manual execution or CI/CD
- Responsibilities: Provision Chameleon VMs, deploy Docker containers, configure MinIO/PostgreSQL
## Error Handling
- Model inference timeout → queue message for manual review, do not display until cleared
- Database connection failure → retry with exponential backoff, log error
- MinIO upload failure → persist to local filesystem as fallback, alert DevOps
- Webhook delivery failure → Zulip retry mechanism (built-in)
## Cross-Cutting Concerns
- Approach: Structured logging (JSON format) for all inference decisions
- Audit trail: Every moderation action logged with confidence score and timestamp
- Approach: Input validation at API boundary (FastAPI Pydantic models)
- Text length limits, required fields, score range checks
- Approach: Zulip webhook authentication tokens
- API key validation on all incoming requests
- Model drift detection via retraining trigger thresholds
- Latency tracking for P99 < 200ms target
- Throughput monitoring for 15–20 RPS capacity
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
