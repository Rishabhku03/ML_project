# Phase 6: E2E Deployment Testing Design

## Overview

**Goal:** Create a layered E2E test suite that validates the ChatSentry data pipeline works correctly in a production-like Docker environment, including failure scenarios.

**Scope:** Full pipeline E2E testing + chaos testing across all failure modes (database, storage, data corruption, container crashes, resource exhaustion).

**Test Data Strategy:** Subset (1,000 rows) for fast iteration, medium (10,000 rows) for realistic volume, full dataset (1.58M rows) for final validation.

---

## Architecture

### Test Layers

```
tests/e2e/
├── conftest.py                  # Docker fixtures, test data setup
├── test_01_infrastructure/      # Service health, connectivity
│   └── test_services.py
├── test_02_data_flow/           # Pipeline stages in sequence
│   ├── test_ingestion.py
│   ├── test_text_cleaning.py
│   ├── test_compilation.py
│   └── test_splitting.py
├── test_03_data_quality/        # GE validation, quality gates
│   ├── test_ge_validation.py
│   └── test_quality_gates.py
├── test_04_chaos/               # Failure injection
│   ├── test_database_failures.py
│   ├── test_storage_failures.py
│   ├── test_data_corruption.py
│   ├── test_container_crashes.py
│   └── test_resource_exhaustion.py
└── test_05_full_pipeline/       # Complete end-to-end
    ├── test_full_pipeline_small.py
    ├── test_full_pipeline_medium.py
    └── test_pipeline_idempotency.py
```

### Layer Dependencies

- **Layer 1** must pass before Layer 2 runs
- **Layer 2** must pass before Layer 3 runs
- **Layer 3** must pass before Layer 4 runs
- **Layer 4** can run independently (uses clean_state fixture)
- **Layer 5** runs last (full validation)

---

## Detailed Test Cases

### Layer 1: Infrastructure Tests

**Purpose:** Verify Docker services are healthy before running pipeline tests.

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_postgres_health` | Connection, schema exists, tables present | Connection succeeds, all tables exist |
| `test_minio_health` | Connection, buckets exist | Both `zulip-raw-messages` and `zulip-training-data` buckets exist |
| `test_api_health` | GET /health returns 200 | Response status 200, healthy status |
| `test_docker_compose_running` | All containers in "running" state | All 5 containers (postgres, minio, minio-init, adminer, api) running |

### Layer 2: Data Flow Tests

**Purpose:** Validate each pipeline stage produces correct output.

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_ingest_csv_to_minio` | CSV chunks uploaded to correct path | Chunks exist at `zulip-raw-messages/real/combined_dataset/chunk_NNN.csv` |
| `test_text_cleaner_on_real_data` | Cleaning produces expected transformations | Markdown stripped, URLs replaced, PII scrubbed |
| `test_compile_initial_mode` | CSV→MinIO→PostgreSQL→Training snapshot | Messages loaded to PostgreSQL, training snapshot created |
| `test_compile_incremental_mode` | PostgreSQL→Training snapshot with temporal filter | Only messages before moderation decision included |
| `test_stratified_split_proportions` | 70/15/15 split maintained | Train: 65-75%, Val: 10-20%, Test: 10-20% |
| `test_versioned_snapshot_structure` | train/val/test CSVs in versioned folder | Files at `v{timestamp}/train.csv`, `val.csv`, `test.csv` |

### Layer 3: Data Quality Tests

**Purpose:** Ensure GE validation and quality gates catch data issues.

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_ge_catches_error_pattern` | #ERROR! rows flagged | Expectation fails with warning severity |
| `test_ge_catches_short_text` | Texts <10 chars flagged | Expectation fails with warning severity |
| `test_ge_catches_long_text` | Texts >5000 chars flagged | Expectation fails with warning severity |
| `test_ge_validates_labels` | is_suicide/is_toxicity must be 0 or 1 | Expectation passes for valid labels |
| `test_ge_checks_class_balance` | Toxicity ratio within 2-8% | Expectation fails if ratio outside bounds |
| `test_quality_gate_filters_correctly` | Combined quality gate removes issues | #ERROR! rows removed, short texts filtered, long texts capped |
| `test_data_docs_generated` | HTML report created and uploaded to MinIO | HTML file exists at `data-quality/report-{timestamp}.html` |

### Layer 4: Chaos Tests

**Purpose:** Verify pipeline handles failures gracefully.

#### Database Failures

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_postgres_down_during_load` | Pipeline detects failure, doesn't corrupt state | Error logged, no partial writes |
| `test_postgres_reconnection` | Pipeline recovers when DB comes back | Successful reconnection after DB restart |
| `test_partial_write_rollback` | Transaction rollback on mid-load failure | No orphaned rows in database |

#### Storage Failures

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_minio_down_during_upload` | Retry logic, local fallback | Retry attempts logged, fallback to local storage |
| `test_minio_reconnection` | Pipeline recovers when MinIO comes back | Successful upload after MinIO restart |
| `test_chunked_upload_resume` | Can resume interrupted chunk uploads | Chunks uploaded successfully after interruption |

#### Data Corruption

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_malformed_csv_rows` | Encoding errors, duplicate IDs handled | Bad rows skipped with warning, duplicates deduplicated |
| `test_null_values_mid_pipeline` | NULL text/labels don't crash pipeline | NULL values handled gracefully |
| `test_duplicate_message_ids` | Deduplication works correctly | No duplicate message_ids in final output |

#### Container Crashes

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_api_crash_recovery` | API restarts, state preserved in PostgreSQL | API recovers, data intact |
| `test_pipeline_crash_cleanup` | Partial uploads cleaned up on restart | No orphaned objects in MinIO |

#### Resource Exhaustion

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_large_dataset_memory` | 100K rows don't OOM (chunking works) | Memory usage stays within limits |
| `test_concurrent_requests` | Multiple pipeline runs don't conflict | No race conditions, data integrity maintained |

### Layer 5: Full Pipeline Tests

**Purpose:** End-to-end validation with real data.

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_full_pipeline_small` | 1,000 rows, all stages, verify final snapshot | Complete pipeline succeeds |
| `test_full_pipeline_medium` | 10,000 rows, realistic volume | Complete pipeline succeeds |
| `test_full_pipeline_with_failures` | Inject chaos during full run | Pipeline handles failures gracefully |
| `test_pipeline_idempotency` | Running pipeline twice produces same result | Same output on repeated runs |

---

## Test Infrastructure

### Docker Service Management

**Fixture: `docker_services` (session-scoped)**
```python
@pytest.fixture(scope="session")
def docker_services():
    # 1. Check if docker-compose already running
    # 2. If not, start with: docker-compose -f docker/docker-compose.yaml up -d
    # 3. Wait for health checks (max 60s)
    # 4. Yield control to tests
    # 5. Teardown: docker-compose down -v
```

**Fixture: `clean_state` (function-scoped)**
```python
@pytest.fixture
def clean_state(docker_services):
    # 1. Truncate PostgreSQL tables (messages, moderation, users)
    # 2. Clear MinIO buckets (keep buckets, delete objects)
    # 3. Yield
    # 4. No cleanup needed (next test will clean)
```

### Chaos Injection

**Context Manager: `kill_container`**
```python
@contextmanager
def kill_container(service_name: str):
    # 1. docker stop <container>
    # 2. Yield
    # 3. docker start <container>
    # 4. Wait for health check
```

**Context Manager: `corrupt_data`**
```python
@contextmanager
def corrupt_data(data_type: str):
    # Inject malformed data into pipeline
    # Options: "csv_encoding", "null_values", "duplicates"
```

### Test Data Management

**Fixture: `test_dataset_small` (1,000 rows)**
```python
@pytest.fixture
def test_dataset_small():
    # Load 1,000 rows from combined_dataset.csv
    # Ensure includes: toxic rows, suicide rows, mixed labels
    # Return as DataFrame
```

**Fixture: `test_dataset_medium` (10,000 rows)**
```python
@pytest.fixture
def test_dataset_medium():
    # Load 10,000 rows from combined_dataset.csv
    # Stratified sample maintaining label distribution
```

---

## Execution

### pytest Markers

```python
@pytest.mark.infrastructure  # Layer 1
@pytest.mark.data_flow       # Layer 2
@pytest.mark.data_quality    # Layer 3
@pytest.mark.chaos           # Layer 4
@pytest.mark.full_pipeline   # Layer 5
```

### Execution Commands

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific layer
pytest tests/e2e/ -v -m infrastructure

# Run chaos tests only
pytest tests/e2e/ -v -m chaos

# Run with Docker logs
pytest tests/e2e/ -v --docker-logs
```

### CI/CD Integration

**GitHub Actions Workflow:**
```yaml
e2e-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Start Docker services
      run: docker-compose -f docker/docker-compose.yaml up -d
    - name: Wait for services
      run: ./scripts/wait_for_services.sh
    - name: Run E2E tests
      run: pytest tests/e2e/ -v
    - name: Teardown
      run: docker-compose -f docker/docker-compose.yaml down -v
```

---

## Success Criteria

1. **All 5 layers pass** — Infrastructure, Data Flow, Data Quality, Chaos, Full Pipeline
2. **No data loss** — Row counts match at each pipeline stage
3. **Graceful failure handling** — Pipeline doesn't crash on errors, logs appropriately
4. **Idempotency** — Running pipeline twice produces same result
5. **Resource efficiency** — Memory usage stays within limits, no OOM errors
6. **Test coverage** — All pipeline components tested, all failure modes covered

---

## Implementation Order

1. **Phase 1:** Infrastructure tests (Layer 1)
2. **Phase 2:** Data flow tests (Layer 2)
3. **Phase 3:** Data quality tests (Layer 3)
4. **Phase 4:** Chaos tests (Layer 4)
5. **Phase 5:** Full pipeline tests (Layer 5)

---

## Appendix: Web Research Findings

Common production issues in data pipelines:

1. **Encoding errors** — CSV files with mixed encodings (UTF-8, Latin-1)
2. **Network timeouts** — Intermittent connectivity to database/object storage
3. **Partial writes** — Transactions interrupted mid-way
4. **Duplicate data** — Same records ingested multiple times
5. **Memory exhaustion** — Large datasets causing OOM errors
6. **Schema drift** — Database schema changes breaking pipeline
7. **Race conditions** — Concurrent pipeline runs conflicting
8. **Resource leaks** — Connections/files not properly closed
9. **Configuration errors** — Missing environment variables
10. **Dependency failures** — Third-party services unavailable

These findings inform the chaos test scenarios in Layer 4.
