---
phase: 03-batch-pipeline
plan: 01
subsystem: data
tags: [pandas, scikit-learn, minio, postgresql, stratified-split, temporal-leakage, batch-pipeline]

# Dependency graph
requires:
  - phase: 01-infrastructure-ingestion
    provides: PostgreSQL schema, MinIO buckets, Config, db/minio utils
  - phase: 02-real-time-processing
    provides: TextCleaner pipeline class
provides:
  - Batch training data compiler with initial and incremental modes
  - Quality gate (error rows, noise filter, outlier cap)
  - Temporal leakage prevention (created_at < decided_at)
  - Stratified 70/15/15 train/val/test split with 4-class labels
  - Versioned CSV snapshots uploaded to MinIO zulip-training-data bucket
affects: [training-phase, serving-phase]

# Tech tracking
tech-stack:
  added: [scikit-learn>=1.8.0]
  patterns: [stratified-split, quality-gate-pipeline, versioned-snapshots, temporal-leakage-prevention]

key-files:
  created:
    - src/data/compile_training_data.py
    - tests/test_compile_training_data.py
  modified:
    - pyproject.toml

key-decisions:
  - "Two-step split (70/30 then 50/50) for clean 70/15/15 ratios instead of single 3-way split"
  - "Combined 4-class label (is_suicide_is_toxicity) for stratification preserves rare class proportions"
  - "Defense-in-depth: temporal leakage filter in both SQL WHERE clause and Python post-query"
  - "UTC timestamp versioning (vYYYYMMDD-HHMMSS) via datetime.now(timezone.utc) — not deprecated utcnow()"

patterns-established:
  - "Quality gate pattern: chain of named filter functions returning filtered DataFrames"
  - "Versioned snapshot naming: immutable v-timestamp folders in MinIO"
  - "Stratified split: create combined label, filter empty classes, split, drop label column"

requirements-completed: [BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05]

# Metrics
duration: ~20min (resumed from interrupted session)
completed: 2026-04-04
---

# Phase 03: Batch Pipeline Summary

**Batch training data compiler with quality gates, temporal leakage prevention, stratified 70/15/15 splits, and versioned MinIO snapshots — 9 unit tests passing**

## Performance

- **Duration:** ~20 min (implementation resumed from interrupted executor session)
- **Started:** 2026-04-04T22:03:00Z
- **Completed:** 2026-04-04T22:25:00Z
- **Tasks:** 3
- **Files created:** 2 (compile_training_data.py, test_compile_training_data.py)
- **Files modified:** 1 (pyproject.toml)

## Accomplishments
- Batch pipeline with two modes: `--mode initial` (CSV from MinIO → PostgreSQL) and `--mode incremental` (PostgreSQL query with temporal filter)
- Quality gate: removes `#ERROR!` rows, filters texts < 10 chars, caps at 5000 chars
- Temporal leakage prevention: `created_at < decided_at` enforced in SQL and Python
- Stratified 70/15/15 split using 4-class combined label, empty class filtering
- Versioned snapshot upload to MinIO `zulip-training-data` bucket
- 9 unit tests covering all BATCH-01 through BATCH-05 requirements

## Task Commits

1. **Task 1: Add scikit-learn dependency** - `5476fdb` (chore)
2. **Task 2: Create compile_training_data.py + tests** - `3d09759` (test/RED), `ac83735` (feat/GREEN)
3. **Task 3: Run full test suite and verify** — all 9 tests pass, lint clean

## Files Created/Modified
- `src/data/compile_training_data.py` — Batch pipeline with 8 exported functions: `compile_initial()`, `compile_incremental()`, `apply_quality_gate()`, `filter_temporal_leakage()`, `select_output_columns()`, `stratified_split()`, `upload_snapshot()`, `generate_version()`
- `tests/test_compile_training_data.py` — 9 tests covering quality gate, temporal leakage, output schema, stratified split, and version format
- `pyproject.toml` — Added `scikit-learn>=1.8.0` dependency

## Decisions Made
- Two-step split (70/30 then 50/50) produces cleaner ratios than single `train_test_split` with 3 outputs
- Combined 4-class label `"{is_suicide}_{is_toxicity}"` for stratification — filters empty classes before split to handle rare combinations (1_1 has 0 rows per DATA_ISSUES.md)
- Defense-in-depth temporal leakage prevention: SQL WHERE clause + Python post-query filter
- UTC timestamps via `datetime.now(timezone.utc)` per modern Python best practices

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
- Executor agent was interrupted before SUMMARY.md creation — resumed manually, verified all code existed and tests pass
- 4 ruff E501 line-length warnings in docstrings/argparse help — fixed before final commit

## Next Phase Readiness
- Batch pipeline complete — ML training team can consume versioned train/val/test datasets from MinIO
- Phase 4 (verification/end-to-end) can now run

---
*Phase: 03-batch-pipeline*
*Completed: 2026-04-04*
