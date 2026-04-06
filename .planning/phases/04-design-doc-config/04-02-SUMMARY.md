---
phase: 04-design-doc-config
plan: 02
subsystem: config
tags: [yaml, dataclass, pipeline-config, env-vars, pyyaml]

# Dependency graph
requires:
  - phase: 01-infrastructure-ingestion
    provides: base Config dataclass, pipeline scripts with hardcoded params
  - phase: 03-batch-pipeline
    provides: compile_training_data.py with quality gates and stratified splits
provides:
  - YAML-backed configuration for all pipeline tunables
  - Config dataclass with YAML loading and env var override
  - 10 tunable parameters externalized from code
  - Phase 5 (Great Expectations) depends on config/pipeline.yaml existing
affects: [05-integrate-great-expectations-data-quality-framework]

# Tech tracking
tech-stack:
  added: [pyyaml]
  patterns: [yaml-to-dataclass mapping, env-var-at-instantiation, frozen-config-singleton]

key-files:
  created:
    - config/pipeline.yaml
    - tests/test_config.py
  modified:
    - src/utils/config.py
    - src/data/ingest_and_expand.py
    - src/data/compile_training_data.py
    - src/data/synthetic_traffic_generator.py

key-decisions:
  - "Used explicit _YAML_TO_CONFIG mapping instead of auto-flattening (YAML section names don't match Config field names consistently)"
  - "Env vars evaluated at instantiation time via _env_kwargs() instead of dataclass defaults (allows monkeypatch testing, cleaner separation)"
  - "Config fields kept as plain string defaults; env/yaml values applied via **kwargs at singleton creation"

patterns-established:
  - "YAML config pattern: _load_yaml_defaults → _yaml_to_kwargs → Config(**kwargs)"
  - "Env override pattern: _env_kwargs() reads env at call time, applied after YAML kwargs"

requirements-completed: [CONFIG-01]

# Metrics
duration: 5min
completed: 2026-04-06
---

# Phase 04 Plan 02: YAML Configuration Extraction Summary

**YAML-backed frozen Config dataclass with 10 tunable parameters externalized from hardcoded Python constants, enabling pipeline parameter changes without code edits**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-06T01:00:00Z
- **Completed:** 2026-04-06T01:05:41Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created `config/pipeline.yaml` with all 10 tunable parameters across 6 sections (ingestion, quality, split, buckets, traffic, batch)
- Updated `src/utils/config.py` with YAML loading, explicit key mapping, and env-var-at-instantiation support
- Replaced all hardcoded tunable values in 3 pipeline scripts with `config.*` references
- Added 6 passing tests covering YAML load, missing file fallback, key mapping, env override, immutability, and full parameter loading

## Task Commits

1. **Task 1: Create pipeline.yaml and update Config** - `faf656b` (feat)
2. **Task 2: Replace hardcoded values in pipeline scripts** - `f3c7496` (refactor)

## Files Created/Modified
- `config/pipeline.yaml` — 10 tunable parameters across 6 YAML sections
- `src/utils/config.py` — Added `_load_yaml_defaults`, `_yaml_to_kwargs`, `_YAML_TO_CONFIG` mapping, `_env_kwargs`; env vars read at instantiation time
- `tests/test_config.py` — 6 tests: yaml_loads, missing_file_fallback, yaml_to_kwargs_mapping, env_var_override, config_is_frozen, all_tunable_params_present
- `src/data/ingest_and_expand.py` — `CHUNK_SIZE = config.CHUNK_SIZE` (was `50_000`)
- `src/data/compile_training_data.py` — Quality gate uses `config.QUALITY_*`, splits use `config.*_SPLIT_RATIO`, `config.RANDOM_STATE`
- `src/data/synthetic_traffic_generator.py` — `TARGET_RPS = config.RPS_TARGET` (was `15`)

## Decisions Made
- Used explicit `_YAML_TO_CONFIG` mapping dictionary instead of auto-flattening because YAML section names (e.g., `ingestion`, `buckets`, `batch`) don't follow a consistent prefix pattern with Config field names (e.g., `batch.upload_size` → `MINIO_BATCH_UPLOAD_SIZE`)
- Env vars evaluated at instantiation time via `_env_kwargs()` instead of dataclass field defaults — enables monkeypatch testing and cleaner separation of YAML (pipeline tunables) vs env vars (infrastructure secrets)
- Priority order: env vars (secrets) > YAML (tunables) > dataclass defaults (hardcoded fallback)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed YAML nested-to-flat key mapping**
- **Found during:** Task 1 (Config singleton creation)
- **Issue:** Plan's `_normalize_keys()` only uppercased keys but YAML has nested sections (`ingestion.chunk_size`). After normalization, Config received `{"INGESTION": {"CHUNK_SIZE": 50000}}` instead of flat `{"CHUNK_SIZE": 50000}`
- **Fix:** Added `_yaml_to_kwargs()` with explicit `_YAML_TO_CONFIG` mapping that translates `("ingestion", "chunk_size")` → `"CHUNK_SIZE"`. Also added `_flatten_yaml()` attempt (abandoned because section names don't consistently prefix Config fields)
- **Files modified:** `src/utils/config.py`, `tests/test_config.py`
- **Verification:** All 6 tests pass, `Config(**_yaml_to_kwargs(load_yaml()))` works
- **Committed in:** `faf656b` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed env var override not working with monkeypatch**
- **Found during:** Task 1 (test_env_var_override failure)
- **Issue:** Config dataclass had `MINIO_ENDPOINT: str = os.environ.get(...)` — env vars evaluated at class definition time (module import), so `monkeypatch.setenv()` after import had no effect
- **Fix:** Moved env var reading to `_env_kwargs()` function that reads at call time. Config dataclass uses plain string defaults. Singleton created with `{**_yaml_to_kwargs(_yaml), **_env_kwargs()}` so env vars override YAML
- **Files modified:** `src/utils/config.py`, `tests/test_config.py`
- **Verification:** `test_env_var_override` passes with monkeypatch
- **Committed in:** `faf656b` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both bugs were implementation details not visible in the plan's high-level design. Fix approach was cleaner than original plan's `os.environ.get` in dataclass defaults.

## Issues Encountered
- None — plan executed smoothly after initial mapping issues were resolved

## Next Phase Readiness
- `config/pipeline.yaml` exists — Phase 5 (Great Expectations) can reference it for validation schemas
- All pipeline parameters now configurable without code changes
- CONFIG-01 requirement complete

---
*Phase: 04-design-doc-config*
*Completed: 2026-04-06*
