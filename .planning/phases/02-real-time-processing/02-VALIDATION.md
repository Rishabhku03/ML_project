---
phase: 02
slug: real-time-processing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_text_cleaner.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_text_cleaner.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | INGEST-04 | integration | `pytest tests/test_traffic_generator.py -x -v` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | ONLINE-05 | unit | `pytest tests/test_text_cleaner.py::test_fix_unicode -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | ONLINE-01 | unit | `pytest tests/test_text_cleaner.py::test_strip_markdown -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | ONLINE-03 | unit | `pytest tests/test_text_cleaner.py::test_extract_urls -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 1 | ONLINE-02 | unit | `pytest tests/test_text_cleaner.py::test_standardize_emojis -x` | ❌ W0 | ⬜ pending |
| 02-02-05 | 02 | 1 | ONLINE-04 | unit | `pytest tests/test_text_cleaner.py::test_scrub_pii -x` | ❌ W0 | ⬜ pending |
| 02-02-06 | 02 | 1 | ONLINE-06 | unit | `pytest tests/test_text_cleaner.py::test_text_cleaner_pipeline -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | ONLINE-06 | integration | `pytest tests/test_middleware.py -x -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_text_cleaner.py` — unit tests for each cleaning step + full pipeline
- [ ] `tests/test_middleware.py` — integration test for middleware cleaning + persistence
- [ ] `tests/test_traffic_generator.py` — test that generator sends requests at target RPS
- [ ] `pip install ftfy emoji markdownify` — install new dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Traffic generator sustained 15-20 RPS | INGEST-04 | Requires running FastAPI server | Run `python src/data/synthetic_traffic_generator.py` and verify via logs that RPS reaches target |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
