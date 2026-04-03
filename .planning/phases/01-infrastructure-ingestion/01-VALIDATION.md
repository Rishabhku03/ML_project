---
phase: 01
slug: infrastructure-ingestion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml — Wave 0 creates |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~60 seconds (integration tests with Docker services) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | INFRA-04 | integration | `docker compose config --quiet` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | INFRA-01 | integration | `pytest tests/test_schema.py -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | INFRA-02 | integration | `pytest tests/test_minio_buckets.py -x` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | INGEST-01, INGEST-03 | unit | `pytest tests/test_csv_chunking.py -x` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 3 | INGEST-02, INGEST-03 | unit | `pytest tests/test_synthetic_gen.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (minio_client, pg_conn, api_client)
- [ ] `tests/test_schema.py` — verify tables, columns, indexes
- [ ] `tests/test_minio_buckets.py` — verify buckets exist
- [ ] `tests/test_csv_chunking.py` — verify chunk count and row distribution
- [ ] `tests/test_synthetic_gen.py` — verify output columns and source tag
- [ ] `pip install pytest httpx` — test framework + FastAPI TestClient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MinIO console browsable at :9001 | INFRA-02 | Visual verification of UI | Open http://<vm-ip>:9001, verify buckets visible |
| FastAPI /docs page loads | INFRA-03 | Visual verification of Swagger UI | Open http://<vm-ip>:8000/docs, verify endpoints listed |
| Docker Compose services all healthy | INFRA-04 | Health status is visual | Run `docker compose ps`, verify all show "healthy" |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
