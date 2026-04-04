---
phase: quick
plan: "260404-rky"
subsystem: data
tags: [smoke-test, integration, pipeline, validation]
dependency_graph:
  requires:
    - src.utils.config
    - src.utils.db
    - src.utils.minio_client
    - src.data.text_cleaner
    - src.data.compile_training_data
  provides:
    - scripts/smoke_test_integration.py
  affects: []
tech_stack:
  added:
    - None (reuses existing stack)
  patterns:
    - Phase-gated smoke test (skip downstream if Docker is down)
    - Lazy imports for graceful degradation
    - Structured result tracking (PASSED/FAILED counters)
key_files:
  created:
    - scripts/smoke_test_integration.py
  modified: []
decisions:
  - "Used lazy imports inside check functions to avoid import-time failures when Docker services are unavailable"
  - "Module-level pandas import is safe since it has no Docker dependency"
  - "Phase gate pattern: PostgreSQL/MinIO failures set DOCKER_AVAILABLE=False, skipping downstream checks"
metrics:
  duration: "~5 min"
  completed: "2026-04-04"
  tasks: 3
  files: 1
---

# Quick Task 260404-rky: Integration Smoke Test Script — Summary

**One-liner:** End-to-end integration smoke test validating all 3 pipeline phases (ingestion, real-time processing, batch compilation) against live Docker services with phase-gated check ordering.

## What Was Built

A single-file smoke test (`scripts/smoke_test_integration.py`) that runs 7 checks in order:

| # | Check | What It Validates |
|---|-------|-------------------|
| 1 | PostgreSQL reachable | `get_db_connection()` → `SELECT 1` |
| 2 | MinIO reachable + buckets | `get_minio_client()` → `bucket_exists()` for raw + training |
| 3 | TextCleaner pipeline | Strips markdown, URLs, emails, `@username` mentions |
| 4 | Quality gate | Removes `#ERROR!` rows and texts < 10 chars |
| 5 | Temporal leakage filter | Drops rows where `created_at >= decided_at` |
| 6 | Stratified split | ~70/15/15 proportions, no `label_combo` column in output |
| 7 | MinIO snapshot upload | Uploads 2-row snapshot, verifies train/val/test CSVs exist |

## Structure

- `check(name, condition, detail)` — helper that increments PASSED/FAILED counters and logs
- `check_postgres()` / `check_minio()` — Docker service connectivity (phase gate)
- `check_text_cleaner()` through `check_minio_snapshot()` — pipeline logic
- `main()` — orchestrates checks, returns 0 (all pass) or 1 (any failure)
- Uses `logging.getLogger("smoke_test")` — no `print()` per project conventions

## Verification Results

**Syntax check:** ✅ `python3 -c "import ast; ast.parse(...)"` — no errors

**Docker-down behavior:** ✅
```
FAIL: PostgreSQL reachable — connection refused
FAIL: MinIO reachable + buckets exist — connection refused
WARNING: Docker services not fully available — skipping live pipeline checks
Results: 0 passed, 2 failed
EXIT_CODE=1
```

**Pipeline logic (independent):** ✅ All 4 non-Docker checks verified:
- TextCleaner: `"**bold** visit https://example.com email me@test.org and @john"` → `"bold visit [URL] email [EMAIL] and [USER]"`
- Quality gate: 5 rows → 2 rows (removed 1 `#ERROR!` + 2 short texts)
- Temporal leakage: 3 rows → 2 rows (dropped 1 leaked row)
- Stratified split: 1000 rows → exact 70.0%/15.0%/15.0%

## Commit

```
2046f09 feat(quick-260404-rky): add integration smoke test for all 3 pipeline phases
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- ✅ `scripts/smoke_test_integration.py` exists
- ✅ Valid Python syntax
- ✅ `main()` function returns 0/1
- ✅ 7 check functions present (check_postgres, check_minio, check_text_cleaner, check_quality_gate, check_temporal_leakage, check_stratified_split, check_minio_snapshot)
- ✅ Uses `logging` module (no `print()`)
- ✅ Phase gates skip downstream checks when Docker is down
- ✅ Committed to git (2046f09)
