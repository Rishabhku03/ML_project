# Phase 4: Design Doc & Config - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 04-design-doc-config
**Areas discussed:** Design doc scope, Diagram format, Config integration strategy, Config file scope

---

## Design doc scope

| Option | Description | Selected |
|--------|-------------|----------|
| Data pipeline only | Document YOUR components: ingestion, TextCleaner, batch pipeline, MinIO/PostgreSQL schemas. Skip ML training and serving. | ✓ |
| Full system | Include ML training (Aadarsh), model serving (Purvansh), and DevOps (Nitish) even though you don't own those. | |

**User's choice:** Data pipeline only
**Notes:** Scope limited to data specialist's domain. Other team members document their own components.

---

## Diagram format

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid in markdown | Embed Mermaid diagrams directly in the design doc. Version-controllable, renders on GitHub. | ✓ |
| Static images | Export diagrams as PNG/SVG files. Polished but harder to maintain. | |
| ASCII/text diagrams | Plain text flow diagrams in markdown. Simplest but less visual. | |

**User's choice:** Mermaid in markdown
**Notes:** Version-controllable, renders on GitHub, easy to update. Demo video can show rendered diagram.

---

## Config integration strategy

| Option | Description | Selected |
|--------|-------------|----------|
| YAML loads into Config dataclass | pipeline.yaml values populate Config fields with env vars as overrides. Single config = Config() call. | ✓ |
| Separate YAML config class | New PipelineConfig class that loads from pipeline.yaml independently. | |
| YAML replaces Config entirely | Remove frozen dataclass, all config comes from pipeline.yaml. | |

**User's choice:** YAML loads into Config dataclass
**Notes:** YAML is source of truth for defaults, env vars for deployment overrides. Single Config() call everywhere.

---

## Config file scope

| Option | Description | Selected |
|--------|-------------|----------|
| All pipeline parameters | Extract CHUNK_SIZE, bucket names, quality thresholds, TextCleaner steps, split ratios, RPS targets, version format. Complete CONFIG-01 compliance. | |
| Tunable params only | Keep truly-fixed values as Python constants. Only configure things a user might change. | ✓ |

**User's choice:** Tunable params only
**Notes:** Column names, UUID format, CSV filenames, version format, TextCleaner step order stay as Python constants. Chunk size, quality thresholds, split ratios, bucket names, RPS target go to YAML.

---

## YAML location

| Option | Description | Selected |
|--------|-------------|----------|
| config/pipeline.yaml | Matches what Phase 5 CONTEXT.md already references. | ✓ |
| src/config/pipeline.yaml | Inside src/ alongside the code. | |

**User's choice:** config/pipeline.yaml
**Notes:** Aligns with Phase 5 D-05 reference.

---

## Doc sections

| Option | Description | Selected |
|--------|-------------|----------|
| Schemas + Repositories + Flow diagrams | DESIGN-01 compliance: PostgreSQL schema docs, MinIO bucket structure, data flow diagrams, config overview. | |
| Add API endpoints + decisions | Above + document FastAPI endpoints and key architectural decisions. | ✓ |

**User's choice:** Add API endpoints + decisions
**Notes:** Design doc includes API endpoint documentation and architectural decision rationale (good for demo talking points).

---

## Agent's Discretion

- YAML parsing library choice (PyYAML vs ruamel.yaml)
- Whether to add `--config` CLI flag to pipeline scripts
- Design document filename and location
- Whether TextCleaner step enable/disable should be YAML-configurable
- How to handle missing YAML file (use defaults vs error)

## Deferred Ideas

- Parquet format conversion — future consideration
- Config validation schema — ensures bad config values fail fast
- Config hot-reloading — not needed for batch pipeline
- Environment-specific YAML files — overkill for single-VM deployment
- Automated config documentation generation
