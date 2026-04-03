---
phase: 01-infrastructure-ingestion
plan: 03
subsystem: data
tags: [csv, pandas, minio, chunked-upload, ingestion]

# Dependency graph
requires:
  - phase: 01-infrastructure-ingestion
    provides: MinIO client factory (src/utils/minio_client.py), Config with BUCKET_RAW
provides:
  - CSV ingestion script (ingest_and_expand.py) with chunked upload to MinIO
  - CSV chunking test suite verifying dataset structure
  - MinIO upload integration tests
affects: [02-synthetic-expansion, 03-online-processor, 04-batch-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [chunked-csv-upload, minio-put-object, memory-cleanup]

key-files:
  created:
    - src/data/ingest_and_expand.py - CSV ingestion script with chunked MinIO upload
    - tests/test_csv_chunking.py - 4 unit tests for CSV structure and chunking
    - tests/test_minio_upload.py - 2 integration tests for MinIO bucket and imports
  modified: []

key-decisions:
  - "Actual CSV has 391,645 rows (not 1.58M) due to embedded newlines in text column — wc -l overcounts. Updated test assertions to match reality."

patterns-established:
  - "Pattern: Chunked CSV upload — pd.read_csv(chunksize=N) → to_csv() → BytesIO → put_object()"
  - "Pattern: Memory cleanup — del csv_bytes after each upload to prevent OOM on large datasets"

requirements-completed: [INGEST-01, INGEST-03]

# Metrics
duration: 3min
completed: 2026-04-03
---

# Phase 01 Plan 03: CSV Ingestion Script Summary

**Chunked CSV ingestion script that reads combined_dataset.csv in 50K-row batches and uploads to MinIO as zulip-raw-messages/real/combined_dataset/chunk_NNN.csv**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-03T21:16:12Z
- **Completed:** 2026-04-03T21:19:14Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `src/data/ingest_and_expand.py` — chunked CSV ingestion with `pd.read_csv(chunksize=50000)`, MinIO upload via `put_object()`, memory cleanup, and progress logging
- Created `tests/test_csv_chunking.py` — 4 unit tests verifying CSV file existence, expected columns (text, is_suicide, is_toxicity), chunk count (8), and total row count (391,645)
- Created `tests/test_minio_upload.py` — 2 integration tests for MinIO bucket access and script importability
- All 4 chunking tests + 1 import test pass; MinIO integration test awaits Docker services

## Task Commits

1. **Task 1: Create CSV ingestion script** - `9e779d5` (feat)
2. **Task 2: Create tests for CSV chunking and MinIO upload paths** - `a9f84b2` (test)

**Plan metadata:** (committed with final metadata)

## Files Created/Modified
- `src/data/ingest_and_expand.py` — CSV ingestion script: reads in 50K chunks, uploads to MinIO as chunk_NNN.csv, logs progress, frees memory per chunk
- `tests/test_csv_chunking.py` — 4 unit tests: file exists, columns, chunk count (8), total rows (391,645)
- `tests/test_minio_upload.py` — 2 integration tests: MinIO bucket accessible, ingest script importable

## Decisions Made
- Updated test assertions from plan's assumed 1,586,127 rows / 32 chunks to actual 391,645 rows / 8 chunks — the CSV text column contains embedded newlines which `wc -l` overcounts but pandas correctly parses

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect CSV row count assertions**
- **Found during:** Task 2 (CSV chunking tests)
- **Issue:** Plan assumed 1,586,127 rows and 32 chunks based on `wc -l` output. Actual pandas parse shows 391,645 rows and 8 chunks — the text column contains embedded newlines that `wc -l` counts as separate lines.
- **Fix:** Updated test_csv_chunking_produces_expected_chunks to expect 8 chunks and test_csv_total_row_count to expect 391,645 rows. Added explanatory comment about the discrepancy.
- **Files modified:** tests/test_csv_chunking.py
- **Verification:** `pytest tests/test_csv_chunking.py -v` → 4 passed
- **Committed in:** a9f84b2 (Task 2 commit)

**2. [Conventions] Replaced print() with logging in __main__ block**
- **Found during:** Task 1 (ingestion script creation)
- **Issue:** Plan's template code used `print()` in the `if __name__ == "__main__"` block. AGENTS.md conventions require no `print()` in committed code.
- **Fix:** Changed `print(f"Done: {count} chunks uploaded")` to `logging.getLogger(__name__).info("Done: %d chunks uploaded", count)`
- **Files modified:** src/data/ingest_and_expand.py
- **Verification:** Grep confirms no `print()` in the file
- **Committed in:** 9e779d5 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 convention fix)
**Impact on plan:** Both fixes are necessary for correctness and convention compliance. No scope creep.

## Issues Encountered
- CSV row count mismatch: `wc -l` reported ~1.58M lines but pandas found 391,645 rows due to embedded newlines in the text column. This is a known behavior of `wc -l` with quoted CSV fields containing newlines.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ingestion script ready to run once MinIO services are available
- Test infrastructure in place for CSV chunking verification
- `ingest_csv()` function signature matches downstream consumption patterns

---

*Phase: 01-infrastructure-ingestion*
*Completed: 2026-04-03*
