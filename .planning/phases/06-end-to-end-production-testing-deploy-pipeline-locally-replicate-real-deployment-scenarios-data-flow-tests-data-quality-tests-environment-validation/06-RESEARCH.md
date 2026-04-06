# Phase 6 Research: E2E Production Testing

**Researched:** 2026-04-05
**Phase:** 06 — End-to-end production testing

## Research Summary

Phase 6 builds a layered E2E test suite that validates the ChatSentry data pipeline against live Docker services. Research confirms the design spec's approach is sound and identifies implementation patterns from the existing codebase.

## Technical Approach

### Test Framework: pytest + subprocess

**Decision:** Use `pytest` with `subprocess.run` for Docker operations (not testcontainers library).

**Rationale:**
- Already in project dependencies (existing tests use pytest)
- `docker compose` CLI is simpler and more transparent than testcontainers Python API
- Session-scoped fixtures handle lifecycle; function-scoped fixtures handle state cleanup
- No additional dependency needed

### Docker Service Management Pattern

**Session-scoped fixture (`docker_services`):**
```
1. subprocess.run(["docker", "compose", "-f", "docker/docker-compose.yaml", "up", "-d"])
2. Poll health endpoints: pg_isready + MinIO /minio/health/live (max 60s, 2s interval)
3. Yield
4. subprocess.run(["docker", "compose", "down", "-v"]) — teardown
```

**Function-scoped fixture (`clean_state`):**
```
1. TRUNCATE messages, moderation, users (CASCADE)
2. Delete all objects in zulip-raw-messages and zulip-training-data buckets
3. Yield
```

### Chaos Injection Pattern

**Context managers using subprocess:**
```python
@contextmanager
def kill_container(service_name: str):
    subprocess.run(["docker", "stop", service_name])
    try:
        yield
    finally:
        subprocess.run(["docker", "start", service_name])
        # Wait for health check
```

**Data corruption via DataFrame manipulation:**
```python
@contextmanager
def corrupt_data(data_type: str):
    # Injects malformed data: "csv_encoding", "null_values", "duplicates"
    # Returns corrupted DataFrame for test to feed into pipeline
```

### Test Data Strategy

**Three tiers from `combined_dataset.csv`:**
- Small: 1,000 rows (stratified sample, ~10 seconds to process)
- Medium: 10,000 rows (stratified sample, ~60 seconds)
- Full: 391,645 rows (actual count after embedded newline correction)

**Stratified sampling:** Use `pandas.sample(frac=...)` with groupby on label columns to maintain `is_suicide` and `is_toxicity` distribution.

### pytest Markers

```python
pytest_plugins = []
# Markers registered in pyproject.toml or conftest.py:
# infrastructure, data_flow, data_quality, chaos, full_pipeline
```

## Existing Codebase Patterns to Reuse

| Asset | How E2E Uses It |
|-------|-----------------|
| `src/utils/db.py:get_db_connection()` | Fixture for PostgreSQL connections |
| `src/utils/minio_client.py:get_minio_client()` | Fixture for MinIO operations |
| `src/utils/config.py:config` | Bucket names, DB connection string |
| `src/data/text_cleaner.py:TextCleaner` | Data flow test assertions |
| `src/data/compile_training_data.py` | `apply_quality_gate()`, `filter_temporal_leakage()`, `stratified_split()`, `upload_snapshot()` |
| `src/data/data_quality.py` | `validate_training_data()`, `upload_data_docs()` |
| `scripts/smoke_test_integration.py` | Check pattern, result tracking |
| `docker/docker-compose.yaml` | Service definitions, health checks |
| `docker/init_sql/00_create_tables.sql` | Table names for TRUNCATE |

## Key Implementation Decisions

1. **No testcontainers** — subprocess + docker compose CLI is simpler and already available
2. **Layer ordering enforced via pytest marks** — `-m infrastructure` runs only Layer 1; full suite runs all layers in order
3. **Clean state between tests** — TRUNCATE + MinIO object deletion ensures test isolation
4. **Chaos tests are sequential** — parallel execution would conflict with Docker stop/start
5. **Test data loaded from CSV** — no synthetic generation in tests; uses existing `combined_dataset.csv`
6. **Memory monitoring via `tracemalloc`** — for resource exhaustion tests

## Potential Pitfalls

1. **Docker health check timing** — PostgreSQL may take 5-10s to accept connections after container start. Use polling with timeout.
2. **MinIO bucket init race** — `minio-init` container creates buckets; tests must wait for it.
3. **Port conflicts** — If developer already has services running on 5432/9000/8000, tests may connect to wrong instance. Use `docker compose ps` to verify.
4. **Large dataset memory** — Full dataset (391K rows) may exceed memory in chunked operations. Verify chunking is actually used.
5. **Test ordering dependency** — Layer 2 depends on Layer 1 passing. pytest markers enforce this at invocation level; within a layer, tests should be independent.

## No New Dependencies Required

All required libraries already in project:
- `pytest` — test framework
- `pandas` — data manipulation
- `psycopg2` / `asyncpg` — PostgreSQL client
- `minio` — MinIO SDK
- `subprocess` — Docker CLI (stdlib)
- `tracemalloc` — memory monitoring (stdlib)

## RESEARCH COMPLETE
