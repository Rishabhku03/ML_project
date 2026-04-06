# Phase 6: E2E Production Testing - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a layered E2E test suite that validates the ChatSentry data pipeline works correctly in a production-like Docker environment. Tests replicate real deployment scenarios — not syntax or unit tests, but live deployment tests. Includes data flow validation, data quality checks, and chaos testing across all failure modes (database, storage, data corruption, container crashes, resource exhaustion).

Test data strategy: subset (1,000 rows) for fast iteration, medium (10,000 rows) for realistic volume, full dataset (1.58M rows) for final validation.

</domain>

<decisions>
## Implementation Decisions

### Test Architecture
- **D-01:** Layered test suite with 5 layers: Infrastructure → Data Flow → Data Quality → Chaos → Full Pipeline. Each layer builds on the previous; Layer 1 must pass before Layer 2 runs, etc.
- **D-02:** Tests run against live Docker Compose services (PostgreSQL, MinIO, API). No mocked services — real deployment replication.

### Test Structure
- **D-03:** Test directory: `tests/e2e/` with subdirectories per layer (`test_01_infrastructure/`, `test_02_data_flow/`, etc.)
- **D-04:** pytest markers per layer: `@pytest.mark.infrastructure`, `@pytest.mark.data_flow`, `@pytest.mark.data_quality`, `@pytest.mark.chaos`, `@pytest.mark.full_pipeline`

### Docker Service Management
- **D-05:** Session-scoped `docker_services` fixture starts docker-compose, waits for health checks (max 60s), tears down after all tests.
- **D-06:** Function-scoped `clean_state` fixture truncates PostgreSQL tables and clears MinIO objects between tests.

### Chaos Injection
- **D-07:** Context managers for failure injection: `kill_container(service_name)` for container crashes, `corrupt_data(data_type)` for data corruption scenarios.
- **D-08:** Chaos test categories: database failures, storage failures, data corruption, container crashes, resource exhaustion.

### Test Data
- **D-09:** Three test data tiers: small (1,000 rows), medium (10,000 rows), full (1.58M rows). Small for fast iteration, medium for realistic volume, full for final validation.
- **D-10:** Test datasets loaded from `combined_dataset.csv` with stratified sampling to maintain label distribution.

### Agent's Discretion
- Whether to use docker-compose directly or testcontainers library
- Specific retry/backoff parameters for reconnection tests
- Memory limit thresholds for resource exhaustion tests
- Whether chaos tests run in parallel or sequentially
- Whether to add `--docker-logs` flag for debugging

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Spec
- `docs/superpowers/specs/2026-04-05-phase6-e2e-testing-design.md` — Full design document with all test cases, architecture, and success criteria.

### Existing Test Infrastructure
- `tests/conftest.py` — Existing fixtures (api_client, minio_client, pg_conn). E2E conftest extends these.
- `scripts/smoke_test_integration.py` — Existing integration smoke test. E2E tests build on this pattern but add chaos testing.
- `tests/test_text_cleaner.py`, `tests/test_compile_training_data.py`, `tests/test_data_quality.py` — Existing unit tests. E2E tests validate same components in live environment.

### Pipeline Components Under Test
- `src/data/ingest_and_expand.py` — CSV ingestion to MinIO (chunked upload)
- `src/data/text_cleaner.py` — Text cleaning pipeline (5 steps)
- `src/data/compile_training_data.py` — Training data compilation (initial + incremental modes)
- `src/data/data_quality.py` — Great Expectations validation
- `src/api/main.py` — FastAPI health endpoint

### Infrastructure
- `docker/docker-compose.yaml` — Docker services (postgres, minio, minio-init, adminer, api, ge-viewer)
- `docker/init_sql/` — PostgreSQL schema initialization

### Data
- `combined_dataset.csv` — 1.58M row dataset with suicide detection and toxicity labels

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/smoke_test_integration.py` — Pattern for checking PostgreSQL/MinIO reachability, TextCleaner pipeline, GE validation, quality gate, temporal leakage, stratified split, MinIO snapshot upload. E2E tests extend this with Docker lifecycle management and chaos injection.
- `tests/conftest.py` — Fixtures for API client, MinIO client, PostgreSQL connection. E2E conftest adds Docker service management.
- `src/utils/minio_client.py` — `get_minio_client()` factory pattern reused for test fixtures.
- `src/utils/db.py` — `get_db_connection()` factory pattern reused for test fixtures.

### Established Patterns
- `logging.getLogger(__name__)` per module — E2E tests use same pattern
- pytest fixtures with setup/teardown — E2E fixtures follow same pattern
- MinIO `put_object`/`get_object` with `io.BytesIO` — reused in test data setup
- pandas DataFrame for data manipulation — reused in test assertions

### Integration Points
- Docker Compose health checks: `pg_isready` for PostgreSQL, `curl -f http://localhost:9000/minio/health/live` for MinIO
- PostgreSQL schema: `init_sql/` directory contains table definitions
- MinIO buckets: `zulip-raw-messages` (raw data), `zulip-training-data` (training snapshots + data docs)

</code_context>

<specifics>
## Specific Ideas

### Layer 1: Infrastructure Tests
- Verify all 5 containers running: `docker compose ps --format json`
- PostgreSQL: connect, query `SELECT 1`, verify tables exist (`messages`, `moderation`, `users`)
- MinIO: connect, verify buckets exist (`zulip-raw-messages`, `zulip-training-data`)
- API: GET `/health` returns 200

### Layer 2: Data Flow Tests
- `test_ingest_csv_to_minio`: Run `ingest_csv()` with 1,000-row subset, verify chunks at `real/combined_dataset/chunk_000.csv`
- `test_text_cleaner_on_real_data`: Apply TextCleaner to sample rows, verify markdown stripped, URLs replaced, PII scrubbed
- `test_compile_initial_mode`: Run `compile_initial()`, verify messages in PostgreSQL, training snapshot in MinIO
- `test_compile_incremental_mode`: Insert moderation records, run `compile_incremental()`, verify temporal filter applied
- `test_stratified_split_proportions`: Verify 70/15/15 split with 5% tolerance

### Layer 3: Data Quality Tests
- Inject #ERROR! rows, verify GE catches them (warning severity)
- Inject short texts (<10 chars), verify GE catches them
- Inject invalid labels (not 0 or 1), verify GE catches them
- Verify Data Docs HTML generated and uploaded to MinIO

### Layer 4: Chaos Tests
- Database: `kill_container("postgres")` during data load, verify error logged, no partial writes
- Storage: `kill_container("minio")` during upload, verify retry logic
- Data: inject malformed CSV rows, verify pipeline handles gracefully
- Container: kill API during request, verify recovery on restart
- Resource: load 100K rows, verify memory stays within limits (chunking works)

### Layer 5: Full Pipeline Tests
- Run complete pipeline with 1,000 rows: ingest → clean → compile → snapshot
- Verify row counts match at each stage
- Run pipeline twice, verify idempotency (same output)
- Inject chaos during full run, verify graceful handling

</specifics>

<deferred>
## Deferred Ideas

- Parallel chaos test execution (may cause Docker conflicts)
- Custom pytest plugin for Docker log capture
- Performance benchmarking (P99 latency, throughput)
- CI/CD integration (GitHub Actions workflow)
- Automated test report generation
- Chaos testing with network partition simulation

</deferred>

---

*Phase: 06-end-to-end-production-testing*
*Context gathered: 2026-04-05*
