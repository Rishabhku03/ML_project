# Phase 4: Design Doc & Config - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 04-design-doc-config
**Areas discussed:** Design document scope, YAML config file structure, Config vs env var boundary, Config loading strategy

---

## Design Document Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive | All 4 PostgreSQL tables + all columns, types, constraints. MinIO bucket layouts with object naming. Both data flow paths. Multiple Mermaid diagrams. | ✓ |
| Focused | Core tables (messages, moderation) with key columns only. Single data flow diagram. MinIO buckets mentioned but not full object naming. | |
| Minimal | Just the high-level data flow diagram. Schemas reference existing SQL init file. MinIO buckets as bullet list. | |

**User's choice:** Comprehensive
**Notes:** All 4 tables documented fully. MinIO object naming conventions included. Multiple Mermaid diagrams for real-time, batch, and overview. Reference existing SQL init file as source of truth.

---

## YAML Config File Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single config.yaml | One file with sections: database, minio, pipeline, traffic, synthetic_generation | |
| Split by concern | Separate files: infra.yaml (db, minio), pipeline.yaml (chunk sizes, thresholds, split ratios), generation.yaml (HF model, RPS, retry config) | ✓ |
| Single with deep nesting | Nested hierarchy: config.yaml with top-level keys grouping related settings | |

**User's choice:** Split by concern (3 files)
**Follow-up:** Grouping confirmed as infra / pipeline / generation

---

## Config vs Env Var Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| YAML for all non-secrets | All non-secret parameters go to YAML. Secrets stay as env vars only. | ✓ |
| YAML for tunables only | Only pipeline tunables in YAML. Everything else stays hardcoded. | |
| Everything in YAML | Everything in YAML including secrets. Use .env or vault for sensitive values. | |

**User's choice:** YAML for all non-secrets
**Notes:** Chunk sizes, quality thresholds, split ratios, RPS, batch sizes, retry config all move to YAML. DATABASE_URL, MINIO creds, HF_TOKEN stay as env vars.

---

## Config Loading Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| YAML-first, env var overrides | YAML loads first, env vars override specific keys. Frozen dataclass replaced. | ✓ |
| Merge into existing Config | Keep frozen dataclass. Add load_yaml_config() that merges. Env vars take precedence. | |
| Full replacement | Replace config.py entirely with new module. | |

**User's choice:** YAML-first, env var overrides
**Notes:** Frozen dataclass replaced with mutable class. YAML loads first, env vars override secrets/deployment. Existing `from src.utils.config import config` pattern preserved.

---

## Agent's Discretion

Areas where user deferred to agent's judgment:
- YAML loading library choice (OmegaConf vs pydantic-settings vs plain yaml.safe_load)
- Config validation approach (type checking on load vs lazy)
- Config file path resolution strategy
- Whether to generate example configs for team members
- Inline comment style in YAML files

