# Testing Patterns

**Analysis Date:** 2026-04-03

## Project State

**Status:** Pre-code — no test files or test framework configured yet. Patterns below are recommendations based on the intended Python/FastAPI stack and project design documents.

**Source references:**
- `Idea.md` — Implementation plan mentioning scripts and pipelines to test
- `MLOps-Project-Report-TeamChatSentry.txt` — Performance targets (<200ms P99 latency)
- `combined_dataset.csv` — 1.5M+ row dataset for testing data pipelines

## Test Framework

**Runner:**
- `pytest` (standard for Python/FastAPI projects)
- Config: `pyproject.toml` `[tool.pytest.ini_options]` section (or `pytest.ini`)

**Assertion Library:**
- `pytest` built-in `assert` (no `unittest.TestCase` needed)
- Use `pytest.raises` for exception testing
- Use `pytest.approx` for floating-point comparisons (model probability scores)

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -x                       # Stop on first failure
pytest tests/test_processor.py  # Single file
pytest -v                       # Verbose output
pytest --cov=src --cov-report=html  # Coverage report
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (standard Python convention)
- Mirror source structure inside `tests/`

**Naming:**
- `test_<module_name>.py` for all test files
- `conftest.py` for shared fixtures at each level

**Structure:**
```
project/
├── src/
│   ├── data/
│   │   ├── ingest.py
│   │   └── processor.py
│   ├── api/
│   │   └── routes.py
│   └── models/
│       └── moderation.py
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── test_ingest.py
│   ├── test_processor.py
│   ├── test_routes.py
│   └── test_moderation.py
└── pyproject.toml
```

## Test Structure

**Suite Organization:**
```python
import pytest
from src.data.processor import clean_text, extract_urls

class TestCleanText:
    """Tests for the clean_text function."""

    def test_removes_markdown(self):
        # arrange
        raw = "**bold** and _italic_"

        # act
        result = clean_text(raw)

        # assert
        assert result == "bold and italic"

    def test_handles_empty_string(self):
        assert clean_text("") == ""

    def test_preserves_plain_text(self):
        assert clean_text("hello world") == "hello world"


class TestExtractUrls:
    """Tests for URL extraction."""

    def test_extracts_single_url(self):
        text = "Check https://example.com for info"
        urls = extract_urls(text)
        assert urls == ["https://example.com"]
```

**Patterns:**
- Use `class TestXxx` to group tests per function/module
- Arrange/Act/Assert pattern for complex tests
- One logical assertion per test (multiple `assert` lines OK if testing same concept)
- Use `@pytest.mark.parametrize` for input variations

## Mocking

**Framework:**
- `pytest` with `unittest.mock` (stdlib)
- Use `monkeypatch` fixture for simple replacements
- Use `MagicMock` / `patch` for complex mocking

**Patterns:**
```python
from unittest.mock import patch, MagicMock
import pytest

# Mock MinIO client
@pytest.fixture
def mock_minio(monkeypatch):
    mock_client = MagicMock()
    mock_client.put_object.return_value = None
    monkeypatch.setattr("src.data.ingest.get_minio_client", lambda: mock_client)
    return mock_client

# Mock database connection
@pytest.fixture
def mock_db(monkeypatch):
    mock_conn = MagicMock()
    mock_conn.execute.return_value = []
    monkeypatch.setattr("src.data.batch.get_db_connection", lambda: mock_conn)
    return mock_conn

# Using mocks in tests
def test_upload_to_minio(mock_minio):
    upload_data("bucket", "key", b"data")
    mock_minio.put_object.assert_called_once()
```

**What to Mock:**
- MinIO/S3 client operations (object storage)
- PostgreSQL database connections and queries
- External HTTP calls (Zulip API, webhook endpoints)
- File system operations for test isolation
- Time-dependent operations (batch windows)

**What NOT to Mock:**
- Text cleaning/normalization functions (pure functions, test directly)
- Data validation logic
- Simple data transformations

## Fixtures and Factories

**Test Data:**
```python
# conftest.py — shared fixtures

import pytest
import pandas as pd

@pytest.fixture
def sample_dataset():
    """Small sample from combined_dataset.csv for testing."""
    return pd.DataFrame({
        "text": [
            "normal message",
            "I want to hurt myself",
            "you are terrible and ugly",
        ],
        "is_suicide": [0, 1, 0],
        "is_toxicity": [0, 0, 1],
    })

@pytest.fixture
def sample_message():
    """A single Zulip message payload."""
    return {
        "message_id": 12345,
        "sender_id": 42,
        "content": "Hello everyone!",
        "timestamp": "2026-04-03T10:00:00Z",
        "stream": "general",
    }

@pytest.fixture
def toxic_message():
    """A message that should trigger moderation."""
    return {
        "message_id": 12346,
        "sender_id": 99,
        "content": "some extremely toxic content here",
        "timestamp": "2026-04-03T10:01:00Z",
        "stream": "general",
    }
```

**Location:**
- `tests/conftest.py` — shared fixtures (dataset samples, mock clients)
- Module-level fixtures in `tests/test_<module>.py` for local test data
- Factory functions for generating variations: `create_message(overrides={})`

## Coverage

**Requirements:**
- Target: 80% line coverage for critical paths (data processing, API routes, moderation logic)
- Coverage for awareness on utility code
- Enforce via CI when pipeline is set up

**Configuration:**
- `pytest-cov` plugin
- Exclude: test files, config scripts, `__init__.py`
- In `pyproject.toml`:
  ```toml
  [tool.coverage.run]
  source = ["src"]
  omit = ["*/tests/*", "*/__init__.py"]
  ```

**View Coverage:**
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Test single functions in isolation (text cleaning, URL extraction, scoring thresholds)
- Mock all external dependencies (MinIO, PostgreSQL, HTTP)
- Fast: each test <100ms
- Priority areas: `processor.py`, threshold decision logic, data validation

**Integration Tests:**
- Test FastAPI routes with `httpx.AsyncClient` and `pytest-asyncio`
- Mock external services but use real application logic
- Test data pipeline end-to-end with in-memory SQLite (not real PostgreSQL)
- Priority areas: API endpoint → processing → response flow

**E2E Tests:**
- Not expected in initial phases
- Manual testing against live Zulip instance on Chameleon

## Common Patterns

**Async Testing (FastAPI routes):**
```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import app

@pytest.mark.asyncio
async def test_moderate_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/messages", json={
            "content": "hello world",
            "sender_id": 1,
        })
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
```

**Error Testing:**
```python
def test_invalid_input_raises():
    with pytest.raises(ValueError, match="empty"):
        clean_text("")

def test_db_connection_failure(mock_db):
    mock_db.execute.side_effect = ConnectionError("db down")
    with pytest.raises(ConnectionError):
        fetch_messages()
```

**Threshold/Decision Testing:**
```python
@pytest.mark.parametrize("score,expected_action", [
    (0.9, "hide"),      # high confidence → auto-hide
    (0.7, "warn"),      # medium confidence → warn user
    (0.4, "approve"),   # low confidence → allow
    (0.35, "alert"),    # self-harm threshold → admin alert
])
def test_moderation_decision(score, expected_action):
    result = decide_action(score, is_self_harm_score=0.35)
    assert result.action == expected_action
```

**Snapshot Testing:**
- Not recommended for this project type
- Prefer explicit assertions on data transformations

---

*Testing analysis: 2026-04-03*
*Established from design documents — update once test infrastructure exists*
