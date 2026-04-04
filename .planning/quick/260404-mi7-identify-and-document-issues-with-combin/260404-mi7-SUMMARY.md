---
phase: quick
plan: 260404-mi7
subsystem: data
tags: [data-quality, documentation, analysis]
requires: []
provides: "Structured catalog of data quality issues for pipeline and ML teams"
key_files:
  created:
    - path: data/DATA_ISSUES.md
      lines: 70
  modified: []
tech_stack: [markdown]
decisions:
  - "Documented all 7 issues from deep analysis (260404-me5) with severity ratings from HIGH to LOW"
  - "Used exact numeric evidence from sample_dataset.py output for each issue description"
  - "Included summary table for quick scanning by pipeline and ML teams"
metrics:
  duration: ~1min
  completed: "2026-04-04"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 260404-mi7: Document Data Quality Issues Summary

Created `data/DATA_ISSUES.md` — a structured catalog of all data quality problems found in `combined_dataset.csv` (391,645 rows) so downstream pipeline and ML training teams can reference it before training.

## What Was Built

`data/DATA_ISSUES.md` — 70-line structured issue catalog covering:

1. **Severe toxicity class imbalance (23×)** — is_toxicity=1 at 4% vs 96%. HIGH severity.
2. **Label mutual exclusivity (zero overlap)** — suicide and toxicity labels are completely disjoint. HIGH severity.
3. **Suicide text length as leakage signal** — suicide texts 2.87× longer (mean 1050 vs 366). MEDIUM severity.
4. **262 duplicate rows (#ERROR! artifacts)** — all duplicates contain pipeline error strings. MEDIUM severity.
5. **Extreme text lengths (3 to 40,297 chars)** — ultra-short noise and ultra-long outliers. MEDIUM severity.
6. **Suicide/non-suicide imbalance (70/30)** — moderate imbalance. LOW-MEDIUM severity.
7. **Minimal non-ASCII content (~0.5%)** — handled by existing cleaner. LOW severity.

Each issue includes severity, evidence (with numbers), impact assessment, and recommended action. Summary table at bottom for quick scanning.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `data/DATA_ISSUES.md` exists (70 lines > 40 minimum)
- [x] All 7 issues documented with severity, evidence, impact, and recommended action
- [x] Summary table present at bottom
- [x] No placeholders or TODOs
- [x] Commit `6d802a6` exists
- [x] References source analysis from `sample_dataset.py` output
