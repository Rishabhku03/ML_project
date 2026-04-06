# Phase 4: Design Doc & Config - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Pipeline documented with schemas/flow diagrams and configurable via YAML. Two deliverables: (1) a high-level data design document covering the data pipeline only (not ML training, serving, or DevOps), and (2) a `config/pipeline.yaml` that makes tunable pipeline parameters configurable without code changes. Phase 5 (Great Expectations) already depends on `config/pipeline.yaml` existing.
</domain>

<decisions>
## Implementation Decisions

### Design Document Scope
- **D-01:** Data pipeline only — documents ingestion, TextCleaner, batch pipeline, MinIO/PostgreSQL schemas. Does NOT document ML training (Aadarsh), model serving (Purvansh), or DevOps (Nitish).
- **D-02:** Sections include: PostgreSQL schema reference, MinIO bucket structure, data flow diagrams, API endpoints (POST /messages, POST /flags with request/response schemas), and key architectural decisions.

### Diagram Format
- **D-03:** Mermaid diagrams embedded in markdown — version-controllable, renders on GitHub, no external tools needed. Three diagrams: ingestion flow, online preprocessing flow, batch pipeline flow.

### YAML Config Integration
- **D-04:** YAML config loads into existing `Config` frozen dataclass (`src/utils/config.py`). YAML is source of truth for defaults; env vars override for deployment (e.g., `DATABASE_URL`, `MINIO_SECRET_KEY` for credentials).
- **D-05:** Config file location: `config/pipeline.yaml` — matches Phase 5 CONTEXT.md reference (D-05 in 05-CONTEXT.md).
- **D-06:** Config loading: add a `load_pipeline_config()` function or integrate into `Config.__post_init__()` that reads YAML and populates fields.

### Config Scope — Tunable Parameters Only
- **D-07:** Extract tunable parameters to YAML — things a user/operator might change between runs:
  - `chunk_size` (currently `50_000` in `ingest_and_expand.py`)
  - `quality_min_text_length` (currently `10` in `compile_training_data.py`)
  - `quality_max_text_length` (currently `5000` in `compile_training_data.py`)
  - `quality_error_pattern` (currently `"#ERROR!"`)
  - `train_split_ratio` / `val_split_ratio` / `test_split_ratio` (currently `0.70` / `0.15` / `0.15`)
  - `bucket_raw` / `bucket_training` (currently in Config)
  - `rps_target` (currently `15-20` in traffic generator)
  - `minio_batch_upload_size` (currently `10_000` for cleaned data batches)
  - `synthetic_target_rows` (currently `10_000`)
  - `random_state` (currently `42` for stratified split)

- **D-08:** Keep truly fixed values as Python constants — not configurable:
  - Column names (`cleaned_text`, `is_suicide`, `is_toxicity`, `source`, `message_id`)
  - Output CSV filenames (`train.csv`, `val.csv`, `test.csv`)
  - UUID format for primary keys
  - Version format (`v%Y%m%d-%H%M%S`)
  - TextCleaner step ORDER (ftfy → markdown → URLs → emoji → PII) — steps are fixed; enabling/disabling individual steps could be YAML-controlled

### Agent's Discretion
- YAML parsing library choice (PyYAML vs ruamel.yaml)
- Whether to add a `--config` CLI flag to pipeline scripts for custom config path
- Design document filename and location (e.g., `docs/data-design.md` or `DATA_DESIGN.md` at root)
- Whether TextCleaner step enable/disable should be YAML-configurable (user said tunable params only — agent decides)
- How to handle missing YAML file (use defaults vs error)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Documents
- `Idea.md` — Data architecture implementation plan: describes all pipeline components, their placement, and relationships
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: system design, team roles, data flow, deployment architecture
- `MLOps_-_Project-Presentation-Team-ChatSentry.txt` — Presentation content: dataset description, model details, serving targets

### Data Quality
- `data/DATA_ISSUES.md` — 7 data quality issues in combined_dataset.csv. Quality thresholds in YAML reference these.

### Requirements
- `.planning/REQUIREMENTS.md` — Requirements DESIGN-01 (design document) and CONFIG-01 (YAML configuration) for this phase

### Prior Phase Context
- `.planning/phases/01-infrastructure-ingestion/01-CONTEXT.md` — Decisions D-01 through D-15 (PostgreSQL schema, MinIO buckets, source tagging, synthetic data generation)
- `.planning/phases/02-real-time-processing/02-CONTEXT.md` — Decisions D-01 through D-17 (TextCleaner pipeline, middleware, cleaned_text column, traffic generator)
- `.planning/phases/03-batch-pipeline/03-CONTEXT.md` — Decisions D-01 through D-26 (two-phase batch pipeline, temporal leakage prevention, stratified split, quality gate)
- `.planning/phases/05-integrate-great-expectations-data-quality-framework/05-CONTEXT.md` — D-05 references `config/pipeline.yaml` — this phase must create it

### Existing Code (integration points)
- `src/utils/config.py` — Frozen dataclass Config with env vars. YAML loads into this class.
- `src/data/ingest_and_expand.py` — Hardcoded `CHUNK_SIZE = 50_000` (line 21) → extract to YAML
- `src/data/compile_training_data.py` — Hardcoded quality thresholds (lines 80-86), split ratios (lines 153-166) → extract to YAML
- `src/data/text_cleaner.py` — TextCleaner pipeline class with fixed step order
- `src/data/synthetic_traffic_generator.py` — RPS target hardcoded
- `src/utils/minio_client.py` — MinIO client factory (unchanged)
- `src/utils/db.py` — PostgreSQL connection helper (unchanged)
- `docker/docker-compose.yaml` — Service definitions (reference for env vars)

### Course Reference
- `lecture and labs.txt` — Course lab URLs for relevant tools

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/utils/config.py` — Frozen dataclass Config pattern — extend with YAML loading, keep env var override
- `src/utils/minio_client.py` — `get_minio_client()` — used for design doc if uploaded to MinIO
- All existing modules that import `from src.utils.config import config` — they'll automatically get YAML values after Config loads them

### Established Patterns
- Frozen dataclass for configuration (Config in config.py) — extend, don't replace
- Logging via `logging.getLogger(__name__)` per module
- `__main__` entry points with argparse — could add `--config` flag
- MinIO `put_object` with `io.BytesIO` — reuse if design doc uploaded to MinIO

### Integration Points
- `config/pipeline.yaml` — new file to create (Phase 5 depends on this existing)
- `src/utils/config.py` — add YAML loading logic, new fields for tunable params
- All pipeline scripts — replace hardcoded values with `config.field_name` references
- `docs/` or root — design document location

</code_context>

<specifics>
## Specific Ideas

- Design document should include a "Config Reference" section listing all YAML keys with descriptions — serves as operator documentation
- Mermaid diagrams should show data flowing between containers (MinIO, PostgreSQL, FastAPI, batch pipeline) with labels for data format at each stage
- Consider a `config/pipeline.example.yaml` alongside the real one — shows all available keys with comments, safe to commit (real YAML might have secrets)
- The design doc is a good place to document the decision rationale: "Why CSV not Parquet", "Why two-phase batch pipeline", "Why prompt-guided labeling" — these are demo talking points

</specifics>

<deferred>
## Deferred Ideas

- Parquet format conversion — can be added later if ML team needs it
- Config validation schema (JSON Schema or Pydantic for YAML) — ensures bad config values fail fast
- Config hot-reloading — not needed for a batch pipeline
- Environment-specific YAML files (dev.yaml, prod.yaml) — overkill for single-VM deployment
- Automated config documentation generation from YAML schema

</deferred>

---

*Phase: 04-design-doc-config*
*Context gathered: 2026-04-06*
