---
phase: 04-design-doc-config
plan: 01
subsystem: documentation
tags: [design-doc, postgresql, minio, mermaid, fastapi, data-pipeline]

# Dependency graph
requires:
  - phase: 01-infrastructure-ingestion
    provides: PostgreSQL schema, MinIO buckets, FastAPI dummy endpoints, Docker Compose
  - phase: 02-real-time-processing
    provides: TextCleaner pipeline, online preprocessing middleware
  - phase: 03-batch-pipeline
    provides: Batch training data compiler with quality gates and stratified splits
provides:
  - Data design document at docs/data-design.md covering full data pipeline architecture
  - PostgreSQL schema reference with all 4 tables
  - MinIO bucket structure documentation
  - 3 Mermaid data flow diagrams
  - API endpoint schemas for POST /messages and POST /flags
  - TextCleaner pipeline documentation
  - 6 architectural decisions with rationale
affects:
  - ML training team (reference for data formats)
  - Demo videos (talking points for design walkthrough)

# Tech tracking
tech-stack:
  added: []
  patterns: [documentation-as-code, schema-anchored-docs, mermaid-flow-diagrams]

key-files:
  created:
    - docs/data-design.md — Complete data pipeline design document (239 lines, 7 sections)
  modified: []

key-decisions:
  - "Anchored all schema docs to actual 00_create_tables.sql DDL — no approximation or paraphrasing"
  - "Documented TextCleaner pipeline with exact function names and PII regex patterns from source"
  - "API schemas derived from actual Pydantic models (MessagePayload, FlagPayload) in src/api/models.py"

patterns-established:
  - "Schema-anchored documentation: all table definitions match source DDL exactly"
  - "Mermaid diagrams for data flow visualization (3 diagrams: ingestion, online preprocessing, batch pipeline)"
  - "Architecture Decision Records: each decision includes 1-2 sentence rationale"

requirements-completed: [DESIGN-01]

# Metrics
duration: 15min
completed: 2026-04-06
---

# Phase 04 Plan 01: Data Design Document Summary

**Data pipeline design document with PostgreSQL schemas, MinIO bucket layouts, 3 Mermaid flow diagrams, API endpoint specs, and TextCleaner pipeline documentation anchored to actual codebase.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-06T01:00:00Z
- **Completed:** 2026-04-06T01:15:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `docs/data-design.md` with 7 sections covering the full data pipeline architecture
- Documented all 4 PostgreSQL tables with exact column definitions from source DDL
- Documented MinIO bucket structure for both `zulip-raw-messages` and `zulip-training-data`
- Included 3 Mermaid flow diagrams (ingestion, online preprocessing, batch pipeline)
- Documented POST /messages and POST /flags API endpoints with Pydantic-derived request/response schemas
- Documented 6 key architectural decisions with rationale
- Documented TextCleaner 5-step pipeline with examples and PII regex patterns

## Task Commits

1. **Task 1: Write data design document** - `297ffb1` (feat)

**Plan metadata:** `297ffb1` (feat: complete plan)

## Files Created/Modified
- `docs/data-design.md` - Complete data pipeline design document (239 lines)

## Decisions Made
- Anchored all schema documentation to actual `00_create_tables.sql` DDL — no approximation or paraphrasing of column types or constraints
- API endpoint schemas derived from actual Pydantic models in `src/api/models.py` (MessagePayload, MessageResponse, FlagPayload, FlagResponse)
- TextCleaner pipeline documented with exact function names and PII regex patterns from `src/text_cleaner.py`
- MinIO bucket structure documented with real folder layouts matching `ingest_and_expand.py` and `compile_training_data.py`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - single task executed cleanly with all verification criteria passing.

## Next Phase Readiness
- Design document ready for demo video walkthroughs and ML team reference
- Data design artifact satisfies DESIGN-01 requirement
- Plan 04-02 (synthetic traffic generator) can proceed independently

---
*Phase: 04-design-doc-config*
*Completed: 2026-04-06*
