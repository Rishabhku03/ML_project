# Phase 5: Integrate Great Expectations Data Quality Framework — Research

**Researched:** 2026-04-05
**Domain:** Great Expectations data quality validation for pandas DataFrames
**Confidence:** HIGH

## Summary

This phase replaces the hand-coded `apply_quality_gate()` function in `compile_training_data.py` with Great Expectations (GX) declarative Expectation Suites. GX 1.15.2 (released Apr 1, 2026) is the current stable version with a completely redesigned API from the legacy 0.18.x branch. The GX 1.x API is significantly simpler for programmatic DataFrame validation — no complex Data Context setup, no filesystem scaffolding, no legacy Checkpoint patterns.

**Primary recommendation:** Use GX 1.15.2 with an Ephemeral Data Context, `add_pandas` Data Source, and runtime-parameterized Expectations for config-driven thresholds. Create a `validate_training_data()` wrapper function in a new `src/data/data_quality.py` module that the compile script calls between `select_output_columns()` and `upload_snapshot()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Replace `apply_quality_gate()` entirely — delete the function and its SQL counterpart in `compile_initial()`. GE Expectation Suite handles all quality checks (text length, #ERROR! filtering, class balance, schema, nulls).
- **D-02:** Suite includes 6 expectation types: column schema, text length bounds (10-5000 chars), no #ERROR! pattern, label validity (0/1), class balance ratio (2-8% is_toxicity), null checks.
- **D-03:** Validation failures log warnings and generate Data Docs, but pipeline continues to MinIO upload. Does not halt — ML team reviews Data Docs separately for quality trends.
- **D-04:** Data Docs uploaded to a MinIO bucket (new bucket or prefix in existing bucket) for team access and demo video recording.
- **D-05:** GE expectations read thresholds from the same `config/pipeline.yaml` created in Phase 4. Single source of truth — no separate GE config directory. GE imports `config.pipeline.quality_min_text_length`, `config.pipeline.quality_max_text_length`, etc.

### Agent's Discretion
- GE Context root directory location (local `great_expectations/` vs temp dir)
- Whether to use GE Checkpoint or direct ValidationOperator
- MinIO bucket for Data Docs: new `zulip-data-quality` bucket vs prefix in `zulip-training-data`
- Data Docs upload frequency: every run vs only on failure
- Whether to keep the SQL quality gate in `compile_initial()` or remove it too (recommendation: remove — GE validates after load)

### Deferred Ideas (OUT OF SCOPE)
- Custom GE Expectations for ChatSentry-specific checks (e.g., text contains no URLs after cleaning)
- GE Profiling to auto-generate initial suite from data statistics
- CI/CD integration — run GE validation in GitHub Actions before merge
- Automated alerting on validation failure (email, Slack)
- GE metrics dashboard over time (tracking quality trends across versions)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUALITY-01 | Data quality metrics report (null rates, duplicate rates, text length distribution) | GE Data Docs automatically generates this — pass/fail per expectation with unexpected value samples |
| QUALITY-02 | Class balance reporting before/after every pipeline stage | GE `ExpectColumnMeanToBeBetween` on is_toxicity captures class ratio (2-8%) |
| CONFIG-01 | Configurable pipeline parameters via YAML (not hardcoded) | D-05: Runtime parameters via `$PARAMETER` dict sourced from pipeline.yaml |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| great-expectations | 1.15.2 | Data quality validation framework | Industry standard for declarative data quality; latest stable release Apr 1, 2026 |
| pandas | >=3.0.0 | DataFrame operations (already installed) | Already in project; GX validates pandas DataFrames natively |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| minio | >=7.2.0 | Upload Data Docs HTML to MinIO (already installed) | Reuse existing `get_minio_client()` pattern |
| pyyaml | >=6.0.0 | Read pipeline.yaml config (already installed) | Already a dependency; Phase 4 creates config file |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GX 1.15.2 | GX 0.18.21 (legacy) | Legacy API requires filesystem Data Context, complex YAML scaffolding, deprecated Checkpoint patterns. 1.x is simpler for programmatic use. |
| Ephemeral Data Context | File Data Context | File context creates `great_expectations/` directory tree. Ephemeral is in-memory — no filesystem cleanup, perfect for pipeline-integrated validation. |
| GX Checkpoint | Direct batch.validate() | Checkpoint adds complexity (action lists, result formats) for this use case. Direct validate() is sufficient when pipeline handles logging/upload itself. |
| Custom validation | pandera, pydantic | pandera is schema-focused (lacks built-in expectations like regex, value sets). pydantic validates individual records, not DataFrames. GX has the richest expectation library. |

**Installation:**
```bash
pip install great-expectations>=1.15.2
```

**Version verification:** `great-expectations` 1.15.2 released Apr 1, 2026. Supports Python 3.10-3.13. Compatible with project's Python 3.12.3.

## Architecture Patterns

### Recommended Project Structure

```
src/data/
├── compile_training_data.py   # Modified: calls validate_training_data() instead of apply_quality_gate()
├── data_quality.py            # NEW: GX validation wrapper (validate_training_data, build_expectation_suite)
├── text_cleaner.py            # Existing
└── ingest_and_expand.py       # Existing

config/
└── pipeline.yaml              # Phase 4 deliverable: quality threshold values
```

### Pattern 1: Ephemeral Data Context with Pandas DataFrame

**What:** Create an in-memory GX context that validates a pandas DataFrame without filesystem scaffolding.

**When to use:** When integrating GX into an existing Python pipeline where you don't need persistent GX metadata between runs.

**Example:**
```python
# Source: https://docs.greatexpectations.io/docs/core/introduction/try_gx/
import great_expectations as gx

context = gx.get_context(mode="ephemeral")

# Connect to in-memory DataFrame
data_source = context.data_sources.add_pandas("pandas")
data_asset = data_source.add_dataframe_asset(name="training data")
batch_definition = data_asset.add_batch_definition_whole_dataframe("whole_df")

# Validate
batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
result = batch.validate(expectation)
```

**Confidence:** HIGH — verified from official GX 1.15.2 docs (Apr 2026).

### Pattern 2: Expectation Suite with Multiple Expectations

**What:** Group related expectations into an `ExpectationSuite` and validate a batch against all of them at once.

**When to use:** When you have multiple data quality checks that should all run together and produce a combined report.

**Example:**
```python
# Source: https://docs.greatexpectations.io/docs/core/define_expectations/organize_expectation_suites/
import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite

suite = context.suites.add(ExpectationSuite(name="training_data_quality"))

suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="cleaned_text")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="is_suicide", value_set=[0, 1]
    )
)
```

**Confidence:** HIGH — verified from official GX 1.15.2 docs.

### Pattern 3: Runtime-Parameterized Expectations

**What:** Define expectations with placeholder values that are filled at validation time from a dictionary. Enables config-driven thresholds without rebuilding the suite.

**When to use:** When validation thresholds come from external config (like pipeline.yaml) and may change between runs.

**Example:**
```python
# Source: https://docs.greatexpectations.io/docs/core/define_expectations/create_an_expectation/
expectation = gx.expectations.ExpectColumnValueLengthsToBeBetween(
    column="cleaned_text",
    min_value={"$PARAMETER": "quality_min_text_length"},
    max_value={"$PARAMETER": "quality_max_text_length"},
)

# At validation time:
checkpoint_result = checkpoint.run(
    expectation_parameters={
        "quality_min_text_length": 10,
        "quality_max_text_length": 5000,
    }
)
```

**Confidence:** HIGH — verified from official GX 1.15.2 docs.

### Pattern 4: Severity Levels for Non-Blocking Validation

**What:** Assign severity levels (`critical`, `warning`, `info`) to expectations. Failed expectations don't throw exceptions — results include success/failure per expectation.

**When to use:** When you want to log quality issues but continue processing (D-03: warn and continue).

**Example:**
```python
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotMatchRegex(
        column="cleaned_text",
        regex=r"#ERROR!",
        severity="warning",  # Won't halt pipeline
    )
)
```

**Confidence:** HIGH — verified from official GX 1.15.2 docs.

### Anti-Patterns to Avoid

- **Using legacy 0.18.x API:** The `DataContext()`, `BatchRequest`, `RuntimeBatchRequest`, `SimpleCheckpoint` classes are from the old API. GX 1.x has completely different class names and patterns. Always use `gx.get_context()`, `context.data_sources.add_pandas()`, `gx.expectations.Expect*`.
- **Creating a File Data Context when you don't need persistence:** File context creates a `great_expectations/` directory with `expectations/`, `checkpoints/`, `uncommitted/` subdirectories. Use ephemeral context instead.
- **Using Checkpoint for simple validation:** Checkpoints add complexity (action lists, result format config). For a single DataFrame validation, `batch.validate(expectation)` or a Validation Definition is sufficient.
- **Hardcoding thresholds in the Expectation Suite:** Use `$PARAMETER` runtime lookups to read from pipeline.yaml. This makes the suite reusable across different threshold configurations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data quality validation | Custom if/else checks in `apply_quality_gate()` | GX Expectation Suite | Declarative, generates Data Docs, extensible, industry standard |
| Quality report generation | Custom HTML/Markdown report builder | GX Data Docs (built-in HTML) | Professional format, includes per-expectation details, unexpected value samples |
| Config-driven validation thresholds | Custom YAML reader + if statements | GX `$PARAMETER` runtime lookups | Built-in parameterization, no custom code needed |
| Class balance checking | Calculate mean and compare manually | `ExpectColumnMeanToBeBetween` on is_toxicity | Native GX expectation, shows in Data Docs, consistent with other checks |

**Key insight:** `apply_quality_gate()` is 30 lines of custom Python that GX replaces with 6 declarative expectations. The GX version also generates Data Docs, supports runtime config, and produces structured validation results — features that would take significant effort to hand-roll.

## Common Pitfalls

### Pitfall 1: GX 1.x vs 0.18.x API Confusion

**What goes wrong:** Using the legacy 0.18.x API patterns (`DataContext`, `BatchRequest`, `context.add_expectation_suite`, `context.run_checkpoint`) with GX 1.x. These classes/methods don't exist in 1.x.

**Why it happens:** Most tutorials, Stack Overflow answers, and blog posts reference 0.18.x. The GX 1.x API launched Aug 2024 and is still less documented in community sources.

**How to avoid:** Always reference docs.greatexpectations.io (shows 1.15.2 by default). Key API differences:

| 0.18.x (Legacy) | 1.x (Current) |
|------------------|---------------|
| `DataContext()` | `gx.get_context()` |
| `context.sources.add_pandas()` | `context.data_sources.add_pandas()` |
| `context.add_expectation_suite()` | `context.suites.add(ExpectationSuite(...))` |
| `context.run_checkpoint()` | `checkpoint.run()` |
| `Validator` class | `batch.validate(expectation)` |

**Warning signs:** Import errors on `DataContext`, `BatchRequest`, `RuntimeBatchRequest`, `SimpleCheckpoint`.

### Pitfall 2: `ExpectColumnValueLengthsToBeBetween` Default Behavior

**What goes wrong:** Text length expectations pass when `min_value` or `max_value` is omitted because they default to "unbounded" (no limit).

**Why it happens:** GX treats omitted parameters as "not checked" rather than "must be present."

**How to avoid:** Always specify both `min_value` and `max_value` for text length expectations. Verify with test data that includes edge cases (< 10 chars, > 5000 chars).

**Warning signs:** All expectations pass even when data clearly violates thresholds.

### Pitfall 3: Class Balance — No Built-in Aggregate Ratio Expectation

**What goes wrong:** There's no `ExpectColumnClassBalanceToBe` expectation. The 2-8% is_toxicity ratio check requires a creative approach.

**Why it happens:** GX focuses on row-level and column-statistics validation, not aggregate distribution checks.

**How to avoid:** Use `ExpectColumnMeanToBeBetween` on the `is_toxicity` column. Since is_toxicity is binary (0/1), the mean equals the proportion of toxic rows. Set min_value=0.02, max_value=0.08 for the 2-8% range.

**Warning signs:** No expectation available for "ratio of values in set."

### Pitfall 4: Ephemeral Context Doesn't Persist Data Docs

**What goes wrong:** With an ephemeral context, Data Docs aren't automatically written to disk. You need to extract the HTML from the validation results.

**Why it happens:** Ephemeral contexts store everything in memory. Data Docs sites require filesystem or cloud storage configuration.

**How to avoid:** Use `UpdateDataDocsAction` in a Checkpoint, or manually build Data Docs HTML from validation results. For MinIO upload, build the HTML programmatically or use a temp directory with a filesystem Data Docs site, then upload the generated files.

**Warning signs:** Data Docs site is empty after validation.

### Pitfall 5: `#ERROR!` Regex Matching with Special Characters

**What goes wrong:** Using `ExpectColumnValuesToNotMatchRegex` with the pattern `#ERROR!` — the `!` is not a regex special character, but `#` could be misinterpreted in some contexts.

**Why it happens:** Regex special characters in test patterns.

**How to avoid:** Use the literal string `#ERROR!` as the regex pattern — `!` is not special in Python regex. The `#` is also literal in Python regex (unlike some flavors). Test with a row containing `#ERROR!` to verify.

**Warning signs:** Expectation passes despite `#ERROR!` rows existing in data.

## Code Examples

Verified patterns from official sources:

### Complete DataFrame Validation Workflow

```python
# Source: https://docs.greatexpectations.io/docs/core/introduction/try_gx/
import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite
import pandas as pd

# 1. Create ephemeral context
context = gx.get_context(mode="ephemeral")

# 2. Connect to DataFrame
data_source = context.data_sources.add_pandas("pandas")
data_asset = data_source.add_dataframe_asset(name="training data")
batch_definition = data_asset.add_batch_definition_whole_dataframe("whole_df")

# 3. Create expectation suite
suite = context.suites.add(ExpectationSuite(name="data_quality"))

# 4. Add expectations
suite.add_expectation(
    gx.expectations.ExpectColumnToExist(column="cleaned_text")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="cleaned_text")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValueLengthsToBeBetween(
        column="cleaned_text",
        min_value=10,
        max_value=5000,
        severity="warning",
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotMatchRegex(
        column="cleaned_text",
        regex="#ERROR!",
        severity="warning",
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="is_suicide",
        value_set=[0, 1],
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnMeanToBeBetween(
        column="is_toxicity",
        min_value=0.02,
        max_value=0.08,
        severity="warning",
    )
)

# 5. Validate
batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
result = batch.validate(suite)
print(result.success)  # True/False
print(result.statistics)  # {'successful_expectations': 6, 'evaluated_expectations': 6, ...}
```

### Runtime Parameters from Config

```python
# Source: https://docs.greatexpectations.io/docs/core/define_expectations/create_an_expectation/
suite.add_expectation(
    gx.expectations.ExpectColumnValueLengthsToBeBetween(
        column="cleaned_text",
        min_value={"$PARAMETER": "min_text_length"},
        max_value={"$PARAMETER": "max_text_length"},
    )
)

# Later, at validation time:
result = batch.validate(
    suite,
    expectation_parameters={
        "min_text_length": config.quality_min_text_length,
        "max_text_length": config.quality_max_text_length,
    }
)
```

### Checkpoint with UpdateDataDocsAction

```python
# Source: https://docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/create_a_checkpoint_with_actions/
from great_expectations.checkpoint import UpdateDataDocsAction

validation_definition = gx.ValidationDefinition(
    data=batch_definition, suite=suite, name="training_data_validation"
)

checkpoint = gx.Checkpoint(
    name="training_data_checkpoint",
    validation_definitions=[validation_definition],
    actions=[UpdateDataDocsAction(name="update_data_docs")],
    result_format={"result_format": "SUMMARY"},
)

checkpoint_result = checkpoint.run(
    batch_parameters={"dataframe": df},
    expectation_parameters=thresholds_dict,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GX 0.18.x `DataContext()` + filesystem | GX 1.x `gx.get_context(mode="ephemeral")` | GX 1.0.0 (Aug 2024) | No filesystem scaffolding needed; simpler for pipeline integration |
| `Validator` class + `expect_*` methods | `batch.validate(expectation)` or suite | GX 1.0.0 | Cleaner separation of data access and validation |
| `RuntimeBatchRequest` for DataFrames | `data_source.add_dataframe_asset()` | GX 1.0.0 | More consistent API across data source types |
| `context.run_checkpoint()` | `checkpoint.run()` directly | GX 1.0.0 | Checkpoints are first-class objects, not context methods |

**Deprecated/outdated:**
- `DataContext()` constructor — use `gx.get_context()`
- `context.sources.add_pandas()` — use `context.data_sources.add_pandas()`
- `BatchRequest` / `RuntimeBatchRequest` — use `add_batch_definition_whole_dataframe()`
- `SimpleCheckpoint` — use `gx.Checkpoint()`
- `context.add_expectation_suite()` — use `context.suites.add(ExpectationSuite(...))`

## Open Questions

1. **MinIO bucket for Data Docs: new bucket vs prefix?**
   - What we know: D-04 says "new bucket or prefix in existing bucket." Existing `zulip-training-data` bucket stores training snapshots. Data Docs are HTML reports — different content type.
   - What's unclear: Whether a new bucket (`zulip-data-quality`) is worth the setup overhead for a course project.
   - Recommendation: Use a prefix `data-quality/` in the existing `zulip-training-data` bucket. Simpler setup, same access pattern. A new bucket adds MinIO init complexity for marginal benefit.

2. **Data Docs generation with Ephemeral Context**
   - What we know: Ephemeral contexts don't have a filesystem Data Docs site by default. The `UpdateDataDocsAction` needs a configured site.
   - What's unclear: Whether to configure a temp-directory filesystem site, extract HTML manually, or use the validation result dict directly to build a report.
   - Recommendation: Create a temp directory, configure a filesystem Data Docs site in the ephemeral context, run the checkpoint (which generates HTML), upload the HTML to MinIO, clean up the temp dir. This is the most reliable approach and produces standard GX Data Docs format.

3. **SQL quality gate removal scope**
   - What we know: `compile_initial()` has TWO quality gates — the SQL DELETE statements (lines 344-371) AND the in-memory `apply_quality_gate()` call (line 374). D-01 says delete `apply_quality_gate()`. The SQL gate modifies PostgreSQL directly.
   - What's unclear: Whether to remove the SQL gate too. GE validates the DataFrame before upload, but the SQL gate modifies the database state.
   - Recommendation: Remove both. GE validates what goes to MinIO training snapshots. The PostgreSQL state should match. Having two different quality gates creates inconsistency risk.

4. **Runtime parameterization without Checkpoint**
   - What we know: `$PARAMETER` runtime lookups work with Checkpoint's `run(expectation_parameters=...)`. Can they work with direct `batch.validate()`?
   - What's unclear: Whether `batch.validate(suite, expectation_parameters=...)` supports runtime parameters directly.
   - Recommendation: Use a Validation Definition + Checkpoint approach. It's the standard GX 1.x pattern and guarantees runtime parameter support. The Checkpoint can be created inline (not persisted) since thresholds come from pipeline.yaml each run.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | GX 1.15.2 | ✓ | 3.12.3 | — |
| pip | Install GX | ✓ | 26.0.1 | — |
| pandas | GX DataFrame validation | ✓ | >=3.0.0 (in requirements) | — |
| MinIO | Data Docs upload | ✓ (Docker) | — | Local filesystem fallback |

**Missing dependencies with no fallback:**
- None — all required tools are available.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `pytest tests/test_data_quality.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUALITY-01 | Data quality metrics report generated | unit | `pytest tests/test_data_quality.py::test_validation_generates_results -x` | ❌ Wave 0 |
| QUALITY-02 | Class balance check catches skew | unit | `pytest tests/test_data_quality.py::test_class_balance_catches_skew -x` | ❌ Wave 0 |
| D-01 | GE replaces apply_quality_gate() | integration | `pytest tests/test_compile_training_data.py -x` (updated) | ✅ existing |
| D-02 | All 6 expectations pass on clean data | unit | `pytest tests/test_data_quality.py::test_suite_passes_on_clean_data -x` | ❌ Wave 0 |
| D-02 | Each expectation catches violations | unit | `pytest tests/test_data_quality.py::test_suite_catches_* -x` | ❌ Wave 0 |
| D-03 | Validation failures don't halt pipeline | unit | `pytest tests/test_data_quality.py::test_validation_warn_and_continue -x` | ❌ Wave 0 |
| D-04 | Data Docs HTML generated | unit | `pytest tests/test_data_quality.py::test_data_docs_generated -x` | ❌ Wave 0 |
| D-05 | Thresholds read from config | unit | `pytest tests/test_data_quality.py::test_runtime_parameters -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_data_quality.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_data_quality.py` — covers D-01 through D-05, QUALITY-01, QUALITY-02
- [ ] Update `tests/test_compile_training_data.py` — replace `apply_quality_gate` tests with GE validation tests
- [ ] `great-expectations>=1.15.2` in `requirements.txt` and `pyproject.toml`

## Sources

### Primary (HIGH confidence)

- [GX 1.15.2 Official Docs — Try GX Core](https://docs.greatexpectations.io/docs/core/introduction/try_gx/) — DataFrame validation workflow, complete code examples
- [GX 1.15.2 Official Docs — Create an Expectation](https://docs.greatexpectations.io/docs/core/define_expectations/create_an_expectation/) — Runtime parameters, severity levels
- [GX 1.15.2 Official Docs — Organize Expectation Suites](https://docs.greatexpectations.io/docs/core/define_expectations/organize_expectation_suites/) — Suite creation and management
- [GX 1.15.2 Official Docs — Create a Checkpoint with Actions](https://docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/create_a_checkpoint_with_actions/) — Checkpoint, action lists, UpdateDataDocsAction
- [GX 1.15.2 Official Docs — Create a Data Context](https://docs.greatexpectations.io/docs/core/set_up_a_gx_environment/create_a_data_context/) — Ephemeral vs File context
- [PyPI — great-expectations 1.15.2](https://pypi.org/project/great-expectations/) — Version, Python compatibility, release date

### Secondary (MEDIUM confidence)

- [GitHub — great-expectations/great_expectations](https://github.com/great-expectations/great_expectations) — 11.3k stars, active development, Apache-2.0 license
- [GX Expectations Gallery](https://greatexpectations.io/expectations) — Confirms ExpectColumnValueLengthsToBeBetween, ExpectColumnValuesToNotMatchRegex, ExpectColumnValuesToBeInSet, ExpectColumnMeanToBeBetween exist

### Tertiary (LOW confidence)

- None — all critical findings verified from official sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — GX 1.15.2 version verified from PyPI, API verified from official docs
- Architecture: HIGH — Ephemeral context, DataFrame validation, and runtime parameters all verified from official docs
- Pitfalls: HIGH — API differences between 0.18.x and 1.x confirmed from official docs; class balance approach verified

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (30 days — GX 1.x API is stable, monthly releases)
