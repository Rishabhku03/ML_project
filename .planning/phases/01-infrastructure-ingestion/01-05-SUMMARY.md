---
phase: 01-infrastructure-ingestion
plan: 05
subsystem: infra
tags: [docker, postgresql, ruff, schema, gap-closure]

requires:
  - phase: 01-infrastructure-ingestion
    provides: Docker Compose stack, PostgreSQL schema, ingestion script, Pydantic models
provides:
  - HF_TOKEN passthrough to API container
  - Source column on all 4 PostgreSQL tables with CHECK constraint
  - ruff-clean source code (zero E501 violations)
affects:
  - Phase 02 (synthetic generation depends on HF_TOKEN)
  - Phase 03 (batch pipeline queries all tables with source tracking)

tech-stack:
  added: []
  patterns: []

key-files:
  modified:
    - docker/docker-compose.yaml
    - docker/init_sql/00_create_tables.sql
    - src/api/models.py
    - src/data/ingest_and_expand.py

key-decisions: []

requirements-completed: [INFRA-01, INFRA-04]

duration: 5min
completed: 2026-04-03
---

# Phase 01 Plan 05: Gap Closure Summary

**Closed 4 verification gaps: HF_TOKEN passthrough, missing source columns on flags/moderation tables, and 2 ruff E501 line-length violations**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-03T21:20:00Z
- **Completed:** 2026-04-03T21:25:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added `HF_TOKEN=${HF_TOKEN}` to api service environment in docker-compose so synthetic_generator.py can authenticate with HuggingFace API
- Added `source VARCHAR(32) NOT NULL DEFAULT 'real' CHECK (source IN ('real', 'synthetic_hf'))` to flags and moderation tables — all 4 tables now have source tracking (D-14)
- Fixed 2 ruff E501 violations by breaking long lines in models.py and ingest_and_expand.py — `ruff check src/` now passes clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Add HF_TOKEN to docker-compose.yaml** - `5e38a78` (fix)
2. **Task 2: Add source columns to flags/moderation tables** - `0f87bc2` (fix)
3. **Task 3: Fix ruff E501 violations** - `8753583` (fix)

## Files Created/Modified
- `docker/docker-compose.yaml` - Added HF_TOKEN env var to api service
- `docker/init_sql/00_create_tables.sql` - Added source column + CHECK to flags and moderation tables
- `src/api/models.py` - Broke Field(...) across 3 lines to fix E501
- `src/data/ingest_and_expand.py` - Broke logging.basicConfig() across 4 lines to fix E501

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Verification Results
- `ruff check src/` — ✅ zero errors (was 2 E501 violations)
- `grep -c "source VARCHAR" sql` — ✅ 4 tables (was 2)
- `grep -q "HF_TOKEN" docker-compose.yaml` — ✅ present
- `pytest tests/test_api_health.py tests/test_csv_chunking.py tests/test_synthetic_gen.py` — ✅ 15 passed

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 1 verification gaps closed
- HF_TOKEN available in API container for synthetic data generation (Phase 02 dependency unblocked)
- Source tracking consistent across all 4 tables for data provenance
- Codebase ruff-clean, ready for CI lint gates

## Self-Check: PASSED

All 4 modified files exist on disk. All 3 task commits verified in git log.

---
*Phase: 01-infrastructure-ingestion*
*Completed: 2026-04-03*
