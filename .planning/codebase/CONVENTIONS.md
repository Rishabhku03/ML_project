# Coding Conventions

**Analysis Date:** 2026-04-03

## Project State

**Status:** Pre-code — no source files exist yet. Conventions below are derived from `Idea.md`, project reports, and the intended tech stack (Python, FastAPI, PostgreSQL, MinIO).

**Source references:**
- `Idea.md` — Implementation plan for Data specialist
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report
- `MLOps_-_Project-Presentation-Team-ChatSentry.txt` — Presentation deck

## Naming Patterns

**Files:**
- Use `snake_case` for all Python files (e.g., `ingest_and_expand.py`, `online_processor.py`)
- Use descriptive names matching purpose: `compile_training_data.py`, `synthetic_traffic_generator.py`
- Test files: `test_<module_name>.py` alongside source, or in `tests/` directory

**Functions:**
- `snake_case` for all functions and methods
- Verb-first naming: `process_message()`, `clean_text()`, `upload_to_minio()`
- Async functions: no special prefix, use `async def` naturally

**Variables:**
- `snake_case` for variables
- `UPPER_SNAKE_CASE` for constants and configuration values (e.g., `TOXICITY_THRESHOLD_HIGH = 0.85`)
- No leading underscores for private members unless truly module-internal

**Types:**
- `PascalCase` for classes and Pydantic models (e.g., `ModerationResult`, `MessagePayload`)
- `PascalCase` for type aliases
- Use Pydantic `BaseModel` for request/response schemas in FastAPI

## Code Style

**Formatting:**
- Use `black` for auto-formatting (standard Python)
- Use `ruff` or `flake8` for linting
- 88-character line length (black default)
- Double quotes for strings (black default)
- Type hints on all function signatures

**Linting:**
- Enforce `flake8` or `ruff` with sensible defaults
- No `print()` in production code — use `logging` module
- Run: `ruff check .` or `flake8 .`

**Configuration files to create:**
- `pyproject.toml` — project metadata, dependencies, tool config
- `.flake8` or `ruff.toml` — linting rules

## Import Organization

**Order (PEP 8):**
1. Standard library imports (`os`, `json`, `logging`)
2. Third-party imports (`fastapi`, `pandas`, `minio`, `psycopg2`)
3. Local application imports (`from .processor import clean_text`)

**Grouping:**
- Blank line between each group
- Alphabetical within each group
- `from` imports after `import` statements within each group

## Error Handling

**Patterns:**
- Use custom exception classes for domain errors (e.g., `ModerationError`, `DataIngestionError`)
- Catch specific exceptions, not bare `except:`
- FastAPI: use `HTTPException` for API errors with appropriate status codes
- Log error with context before re-raising

**Error Types:**
- Raise on invalid input, missing dependencies, invariant violations
- Return structured error responses from API endpoints
- Use `logging.exception()` in catch blocks to capture stack traces

## Logging

**Framework:**
- Python `logging` module, configured centrally
- Levels: DEBUG, INFO, WARNING, ERROR (standard Python levels)

**Patterns:**
- Get logger per module: `logger = logging.getLogger(__name__)`
- Structured context: `logger.info("Processing message", extra={"message_id": msg_id})`
- Log at service boundaries: API entry points, MinIO operations, DB queries
- No `print()` statements in committed code

## Comments

**When to Comment:**
- Explain ML/data pipeline decisions (thresholds, window sizes, preprocessing choices)
- Document business rules from the moderation tier matrix
- Explain non-obvious data transformations (PII scrubbing, leakage prevention)
- Avoid obvious comments

**Docstrings:**
- Use Google-style or NumPy-style docstrings for all public functions
- Include `Args`, `Returns`, `Raises` sections
- Document Pydantic model fields with `Field(description=...)`

## Function Design

**Size:**
- Keep functions under 50 lines
- Extract data transformation steps into named helper functions
- One responsibility per function

**Parameters:**
- Max 3-4 positional parameters
- Use Pydantic models or dataclasses for complex inputs
- Destructure where possible

**Return Values:**
- Use Pydantic models for structured return values
- Return early for guard clauses
- Use `Optional[T]` or `Union[T, None]` for nullable returns

## Module Design

**Exports:**
- Use `__init__.py` to expose public API per package
- Keep internal helpers private (leading underscore or not exported)
- Organize by concern: `data/`, `api/`, `models/`, `utils/`

**Expected package structure (based on `Idea.md`):**
- `data/` — ingestion, preprocessing, batch pipelines
- `api/` — FastAPI routes and request handling
- `models/` — Pydantic schemas, ML model wrappers
- `utils/` — shared helpers (text cleaning, MinIO client)

---

*Convention analysis: 2026-04-03*
*Established from design documents — update once code exists*
