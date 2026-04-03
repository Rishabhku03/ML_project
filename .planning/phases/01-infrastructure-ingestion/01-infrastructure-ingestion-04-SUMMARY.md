---
phase: 01-infrastructure-ingestion
plan: 04
subsystem: data
tags: [synthetic-data, huggingface, mistral, prompts, minio, retry-logic]

# Dependency graph
requires:
  - phase: 01-infrastructure-ingestion
    provides: Config (HF_TOKEN, BUCKET_RAW), MinIO client factory
provides:
  - Prompt templates for toxic/suicide/benign Zulip-style message generation
  - Synthetic data generator with HuggingFace InferenceClient and retry logic
  - Unit tests for prompt structure and text parsing
affects: [batch-pipeline, training]

# Tech tracking
tech-stack:
  added: [huggingface_hub InferenceClient]
  patterns: [prompt-guided labeling, exponential backoff retry, frozen dataclass configs]

key-files:
  created:
    - src/data/prompts.py
    - src/data/synthetic_generator.py
    - tests/test_synthetic_gen.py
  modified: []

key-decisions:
  - "Used frozen dataclass GenerationPrompt to encapsulate system/user prompts with label metadata"
  - "Exponential backoff retry: 5s/10s/20s with 3 retries per Pitfall 4"
  - "Label distribution rebalanced: 30% toxic, 30% suicide, 40% benign (oversamples minorities per D-11)"

patterns-established:
  - "Prompt-guided labeling: labels assigned from prompt instruction, not post-hoc classification (D-13)"
  - "In-memory CSV upload via BytesIO (no temp files)"

requirements-completed: [INGEST-02, INGEST-03]

# Metrics
duration: 15min
completed: 2026-04-03
---

# Phase 01 Plan 04: Synthetic Data Generator Summary

**Prompt templates + HuggingFace Mistral-7B synthetic data generator with exponential backoff retry, producing ~10K rebalanced Zulip-style training messages uploaded to MinIO**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-03T21:20:00Z
- **Completed:** 2026-04-03T21:35:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created `src/data/prompts.py` with 3 prompt templates (toxic, suicide, benign) using frozen dataclass `GenerationPrompt`
- Created `src/data/synthetic_generator.py` with `generate_synthetic_data()` function using HuggingFace InferenceClient
- Created `tests/test_synthetic_gen.py` with 8 unit tests — all passing
- Exponential backoff retry logic (5s/10s/20s) for HuggingFace API rate limits per Pitfall 4

## Task Commits

Each task was committed atomically:

1. **Task 1: Create prompt templates** - `3780ab5` (feat)
2. **Task 2: Create synthetic data generator** - `ce9f7ad` (feat)
3. **Task 3: Create tests for synthetic generation** - `ab07fbb` (test)

**Lint fixes:** `8a9f499` (fix: ruff E501 line-length violations)

**Plan metadata:** (included in final commit)

## Files Created/Modified
- `src/data/prompts.py` - Prompt templates (toxic/suicide/benign) with label distribution config
- `src/data/synthetic_generator.py` - Synthetic data generator: HF API calls, text parsing, MinIO upload
- `tests/test_synthetic_gen.py` - 8 unit tests for prompt structure, label flags, distribution, text parsing

## Decisions Made
- Used `InferenceClient(provider="featherless-ai")` per D-09 (Mistral-7B-Instruct-v0.2 available via Featherless AI)
- Label distribution rebalanced to 30/30/40 (toxic/suicide/benign) to oversample minority classes per D-11
- Labels assigned from prompt instruction (D-13) — no post-hoc classification needed
- source='synthetic_hf' on all generated rows (D-14)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 line-length violations**
- **Found during:** Post-verification lint check
- **Issue:** 5 lines exceeded 88-char limit (ruff E501)
- **Fix:** Wrapped long log strings and extracted fieldnames variable
- **Files modified:** src/data/prompts.py, src/data/synthetic_generator.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 8a9f499

---

**Total deviations:** 1 auto-fixed (lint cleanup)
**Impact on plan:** Cosmetic fix only. No behavioral changes.

## Issues Encountered
- `python` command not available — used `python3` throughout
- `ruff` not installed — installed via `pip3 install --break-system-packages ruff`

## User Setup Required

**HuggingFace API token required for synthetic data generation.**

Set `HF_TOKEN` environment variable before running:
```bash
export HF_TOKEN="hf_..."
```
Get token from: HuggingFace Settings → Access Tokens → New token (read access)

Without this token, `generate_synthetic_data()` will fail at API call time. Unit tests run without the token (no API calls).

## Next Phase Readiness
- Synthetic data generator ready — requires HF_TOKEN and running MinIO to execute end-to-end
- Prompt templates can be extended with additional label types or Zulip-specific conversation patterns
- Integration with batch pipeline (compile_training_data.py) deferred to later phase

## Self-Check: PASSED

- `src/data/prompts.py` — FOUND
- `src/data/synthetic_generator.py` — FOUND
- `tests/test_synthetic_gen.py` — FOUND
- Commit `3780ab5` — FOUND
- Commit `ce9f7ad` — FOUND
- Commit `ab07fbb` — FOUND
- Commit `8a9f499` — FOUND
- All 8 tests passing — VERIFIED

---
*Phase: 01-infrastructure-ingestion*
*Completed: 2026-04-03*
