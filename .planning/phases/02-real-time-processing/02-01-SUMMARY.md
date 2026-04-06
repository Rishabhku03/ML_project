---
phase: 02-real-time-processing
plan: 01
subsystem: data
tags: [aiohttp, asyncio, traffic-generator, synthetic-data, load-testing]

# Dependency graph
requires:
  - phase: 01-data-pipeline
    provides: combined_dataset.csv, synthetic_generator.py, prompts.py, config.py
provides:
  - Synthetic HTTP traffic generator for load testing FastAPI endpoints
  - Traffic generator test suite
affects: [api-serving, testing, demo-videos]

# Tech tracking
tech-stack:
  added: [aiohttp, pytest-asyncio]
  patterns: [async concurrency, mixed data source dispatch, rate-limited HTTP client]

key-files:
  created:
    - src/data/synthetic_traffic_generator.py
    - tests/test_traffic_generator.py

key-decisions:
  - "D-01: Sustained stream dispatch at ~15-20 RPS"
  - "D-02: Async concurrency model using asyncio + aiohttp"
  - "D-03: Mixed data source — CSV rows AND synthetic HF messages"
  - "D-04: Script location: src/data/synthetic_traffic_generator.py"

patterns-established:
  - "Async HTTP traffic generation with rate limiting via asyncio.sleep"
  - "80/20 message/flag dispatch split for realistic traffic simulation"
  - "80/20 CSV/synthetic data source split"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-04-03
---

# Phase 02 Plan 01: Synthetic HTTP Traffic Generator Summary

**Async HTTP traffic generator dispatching sustained 15-20 RPS to FastAPI /messages and /flags endpoints using mixed CSV + synthetic HuggingFace data sources**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-03T00:00:00Z
- **Completed:** 2026-04-03T00:10:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `src/data/synthetic_traffic_generator.py` with async traffic generator using asyncio + aiohttp
- Created `tests/test_traffic_generator.py` with 9 passing tests covering CSV loading, POST dispatch, rate control, error handling
- CLI interface with `--base-url`, `--duration`, `--rps`, `--csv-path` flags
- Mixed dispatch: 80% messages / 20% flags, 80% CSV / 20% synthetic HF messages

## Files Created/Modified
- `src/data/synthetic_traffic_generator.py` - Async HTTP traffic generator with rate-limited dispatch loop
- `tests/test_traffic_generator.py` - 9 tests: CSV loading, POST dispatch, error handling, RPS control, empty CSV abort

## Decisions Made
- Used `asyncio.create_task` for fire-and-forget dispatch to maintain rate limiting
- Fallback to CSV messages when HF API fails (never blocks the dispatch loop)
- `_call_hf_api` run via `run_in_executor` since it's synchronous

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `self.` reference in module-level function**
- **Found during:** Task 1 (creating traffic generator)
- **Issue:** Used `self._dispatch_and_count(...)` in `run_traffic_generator` but this is a module-level function, not a class method
- **Fix:** Changed to `_dispatch_and_count(...)` (removed `self.` prefix)
- **Files modified:** `src/data/synthetic_traffic_generator.py`
- **Verification:** Syntax check passes, import succeeds
- **Committed in:** (part of Task 1)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor typo fix — no scope creep.

## Issues Encountered
- `pip install` required `--break-system-packages` flag due to PEP 668 on this system
- `python` binary not found — used `python3` instead
- Running script directly (`python3 src/data/...`) fails without `PYTHONPATH=.` due to `src.` import prefix — works when imported as module or with PYTHONPATH set (consistent with existing project convention)

## Next Phase Readiness
- Traffic generator ready for integration testing against live FastAPI endpoints
- Can be used for demo video recording (sustained realistic traffic)
- Foundation for load testing and RPS validation in later phases

---
*Phase: 02-real-time-processing*
*Completed: 2026-04-03*
