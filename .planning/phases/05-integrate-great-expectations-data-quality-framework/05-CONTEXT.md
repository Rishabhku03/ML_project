# Phase 5: Integrate Great Expectations data quality framework - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace hand-coded quality gate in `compile_training_data.py` with Great Expectations declarative Expectation Suites. GE validates training data before MinIO snapshot upload, generates Data Docs for quality reporting (uploaded to MinIO), and reads thresholds from Phase 4 YAML config. Validation failures log warnings but pipeline continues.

</domain>

<decisions>
## Implementation Decisions

### Integration Scope
- **D-01:** Replace `apply_quality_gate()` entirely — delete the function and its SQL counterpart in `compile_initial()`. GE Expectation Suite handles all quality checks (text length, #ERROR! filtering, class balance, schema, nulls).

### Expectation Suite Design
- **D-02:** Suite includes 6 expectation types:
  - Column schema: `cleaned_text` exists, is string type
  - Text length bounds: value lengths between 10 and 5000 chars (replaces D-22, D-23 from Phase 3)
  - No `#ERROR!` pattern: values don't match `#ERROR!` regex (replaces D-21 from Phase 3)
  - Label validity: `is_suicide` and `is_toxicity` values are 0 or 1 only
  - Class balance ratio: `is_toxicity=1` proportion between 2% and 8% (catches synthetic data skew from 23:1 ratio)
  - Null checks: no nulls in `cleaned_text`, `is_suicide`, `is_toxicity`, `source` columns

### Validation Failure Behavior
- **D-03:** Validation failures log warnings and generate Data Docs, but pipeline continues to MinIO upload. Does not halt — ML team reviews Data Docs separately for quality trends.

### Data Docs & Reporting
- **D-04:** Data Docs uploaded to a MinIO bucket (new bucket or prefix in existing bucket) for team access and demo video recording.

### Config Integration with Phase 4
- **D-05:** GE expectations read thresholds from the same `config/pipeline.yaml` created in Phase 4. Single source of truth — no separate GE config directory. GE imports `config.pipeline.quality_min_text_length`, `config.pipeline.quality_max_text_length`, etc.

### Agent's Discretion
- GE Context root directory location (local `great_expectations/` vs temp dir)
- Whether to use GE Checkpoint or direct ValidationOperator
- MinIO bucket for Data Docs: new `zulip-data-quality` bucket vs prefix in `zulip-training-data`
- Data Docs upload frequency: every run vs only on failure
- Whether to keep the SQL quality gate in `compile_initial()` or remove it too (recommendation: remove — GE validates after load)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data Quality Analysis
- `data/DATA_ISSUES.md` — 7 data quality issues in combined_dataset.csv. GE suite encodes solutions to Issues 4 (duplicates), 5 (extreme lengths), and 1 (class imbalance).

### Requirements
- `.planning/REQUIREMENTS.md` — v2 requirements QUALITY-01 (quality metrics report) and QUALITY-02 (class balance reporting) are effectively delivered by this phase via GE Data Docs.

### Prior Phase Context
- `.planning/phases/03-batch-pipeline/03-CONTEXT.md` — Decisions D-20 through D-23 (quality gate thresholds being replaced), D-24 (audit logging)
- `.planning/phases/04-design-doc-config/04-CONTEXT.md` — Decisions D-06, D-30, D-31 (YAML config structure with pipeline quality thresholds)

### Existing Code (integration points)
- `src/data/compile_training_data.py` — `apply_quality_gate()` (lines 48-78) to be replaced. Also SQL quality gate in `compile_initial()` (lines 344-371) to be removed. GE validation inserted before `upload_snapshot()` calls.
- `src/utils/config.py` — Config dataclass to be extended with GE threshold fields from pipeline.yaml (Phase 4 dependency).
- `src/utils/minio_client.py` — `get_minio_client()` factory for Data Docs upload.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/compile_training_data.py` — `compile_initial()` and `compile_incremental()` both call `apply_quality_gate()` at lines 374 and 429 respectively. GE validation replaces these calls.
- `src/utils/minio_client.py` — `get_minio_client()` + `put_object()` pattern already used for training snapshot upload. Same pattern for Data Docs upload.
- `src/utils/config.py` — Will gain GE-relevant threshold fields via Phase 4 YAML extraction.

### Established Patterns
- `logging.getLogger(__name__)` per module — GE integration uses same pattern
- MinIO `put_object` with `io.BytesIO` — reuse for Data Docs HTML upload
- Module-level `__main__` entry point with argparse — GE validation could be runnable standalone or integrated into existing compile script

### Integration Points
- `apply_quality_gate()` calls at line 374 (initial) and line 429 (incremental) — both replaced with GE validation
- SQL quality gate at lines 344-371 in `compile_initial()` — removed (redundant with GE)
- `upload_snapshot()` called after quality gate — GE validation inserted between quality gate replacement and upload
- `requirements.txt` / `pyproject.toml` — add `great-expectations` dependency

</code_context>

<specifics>
## Specific Ideas

- GE suite file: `great_expectations/expectations/training_data_quality.json` (or .yml)
- Validation runs on the DataFrame AFTER `select_output_columns()` and BEFORE `upload_snapshot()` — validates exactly what gets uploaded
- Class balance check (2-8% is_toxicity) directly addresses DATA_ISSUES.md Issue 1 (23:1 imbalance) — if synthetic generation over-corrects, GE catches it
- Data Docs HTML can be recorded in demo video showing pass/fail status per expectation
- Consider a `validate_training_data()` wrapper function that calls GE and returns (success_bool, results) for clean integration

</specifics>

<deferred>
## Deferred Ideas

- Custom GE Expectations for ChatSentry-specific checks (e.g., text contains no URLs after cleaning)
- GE Profiling to auto-generate initial suite from data statistics
- CI/CD integration — run GE validation in GitHub Actions before merge
- Automated alerting on validation failure (email, Slack)
- GE metrics dashboard over time (tracking quality trends across versions)

</deferred>

---

*Phase: 05-integrate-great-expectations-data-quality-framework*
*Context gathered: 2026-04-05*
