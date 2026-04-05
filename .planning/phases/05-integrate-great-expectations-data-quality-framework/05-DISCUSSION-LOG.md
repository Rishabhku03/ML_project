# Phase 5: Integrate Great Expectations data quality framework - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 05-integrate-great-expectations-data-quality-framework
**Areas discussed:** Integration scope, Expectation Suite design, Validation failure behavior, Data Docs & reporting, Config integration with Phase 4

---

## Integration Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Replace entirely | Delete apply_quality_gate(). GE Expectation Suite handles all 3 checks plus new ones. Single validation point. | ✓ |
| Wrap as post-check | Keep apply_quality_gate() as-is. Add GE validation AFTER it as a separate quality report step. | |
| Hybrid: GE validates output | Keep apply_quality_gate() for fast filtering, GE validates the result. | |

**User's choice:** Replace entirely (Recommended)
**Notes:** Clean replacement — no redundant checks, single quality validation point.

---

## Expectation Suite Design

| Option | Description | Selected |
|--------|-------------|----------|
| Column schema | Column exists, is string type, not null | ✓ |
| Text length bounds | Value lengths between 10 and 5000 chars (replaces D-22, D-23) | ✓ |
| No #ERROR! pattern | Values don't match '#ERROR!' regex (replaces D-21) | ✓ |
| Label validity | is_suicide and is_toxicity values are 0 or 1 only | ✓ |
| Class balance ratio | is_toxicity=1 proportion between 2% and 8% | ✓ |
| Null checks | No nulls in cleaned_text, is_suicide, is_toxicity, source | ✓ |

**User's choice:** All 6 expectation types selected
**Notes:** Comprehensive suite covering both existing quality gate checks and new GE-enabled validations.

---

## Validation Failure Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Halt pipeline | GE validation failure raises exception, pipeline stops before MinIO upload. | |
| Warn and continue | Log warnings, generate Data Docs report, but continue upload. | ✓ |
| Mixed: halt on critical, warn on soft | Halt on critical checks (nulls, schema), warn on soft checks (class balance, text length). | |

**User's choice:** Warn and continue
**Notes:** Pipeline continues on validation failure. ML team reviews Data Docs separately.

---

## Data Docs & Reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Local filesystem HTML | GE auto-generates HTML files locally. No extra infra. | |
| MinIO bucket | Upload Data Docs HTML to MinIO bucket for team access. | ✓ |
| Logging only | Skip Data Docs HTML, just log validation results to stdout/filesystem. | |

**User's choice:** MinIO bucket
**Notes:** Data Docs uploaded to MinIO for team access and demo video recording.

---

## Config Integration with Phase 4

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse pipeline.yaml | GE expectations read thresholds from the same pipeline.yaml. Single source of truth. | ✓ |
| Separate GE config dir | GE has its own config directory. Separate from Phase 4 YAML config. | |
| Hardcode in suite | GE suite is entirely Python-defined. Thresholds are hardcoded. | |

**User's choice:** Reuse pipeline.yaml (Recommended)
**Notes:** Single source of truth for quality thresholds. No config duplication.

---

## Agent's Discretion

Areas where user deferred to the agent:
- GE Context root directory location
- Checkpoint vs ValidationOperator approach
- MinIO bucket for Data Docs (new vs existing)
- Data Docs upload frequency
- SQL quality gate removal in compile_initial()

