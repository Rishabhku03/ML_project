# Phase 4: Design Doc & Config - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Two deliverables: (1) comprehensive data design document with PostgreSQL schemas, MinIO bucket layouts, and Mermaid data flow diagrams for both real-time and batch paths, (2) YAML configuration extraction moving all non-secret hardcoded pipeline parameters into 3 split config files with a YAML-first, env-var-override loading strategy.

</domain>

<decisions>
## Implementation Decisions

### Data Design Document (DESIGN-01)

- **D-01:** Comprehensive scope — full schemas for all 4 PostgreSQL tables (users, messages, flags, moderation) with column names, types, constraints, and indexes
- **D-02:** MinIO bucket layouts documented with object naming conventions: `zulip-raw-messages/real/combined_dataset/chunk_NNN.csv`, `zulip-raw-messages/synthetic/synthetic_data.csv`, `zulip-raw-messages/cleaned/batch-{uuid}.jsonl`, `zulip-training-data/v{timestamp}/train|val|test.csv`
- **D-03:** Multiple Mermaid diagrams: (a) real-time inference data flow (HTTP → middleware → TextCleaner → PostgreSQL + MinIO), (b) batch training pipeline flow (MinIO/PostgreSQL → compile_training_data → quality gate → split → versioned MinIO snapshot), (c) high-level architecture overview
- **D-04:** Output format: Markdown file (`data_design_document.md`) at project root, using Mermaid fenced code blocks for diagrams
- **D-05:** Reference existing SQL init file (`docker/init_sql/00_create_tables.sql`) as source of truth for schema details — design doc mirrors it, doesn't duplicate

### YAML Configuration Structure (CONFIG-01)

- **D-06:** 3 YAML files split by concern:
  - `config/infra.yaml` — database connection (host, port, db name, user), MinIO connection (endpoint, access_key, secure flag), bucket names
  - `config/pipeline.yaml` — chunk sizes, quality gate thresholds (min text length, max text length, error pattern), train/val/test split ratios, MinIO batch size, cleaned data prefix
  - `config/generation.yaml` — HF model ID, provider, target RPS, retry config (max retries, delays), messages per API call, target synthetic total, label distribution

- **D-07:** Default config directory at project root: `config/` with 3 files
- **D-08:** Config file path configurable via `CHATSENTRY_CONFIG_DIR` env var (default: `./config`)

### Config vs Env Var Boundary

- **D-09:** YAML holds ALL non-secret pipeline and infrastructure parameters
- **D-10:** Env vars hold ONLY secrets and deployment-specific overrides: `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`, `HF_TOKEN`
- **D-11:** When both YAML and env var define the same key, env var wins (for deployment flexibility)
- **D-12:** Bucket names (`zulip-raw-messages`, `zulip-training-data`) move to `infra.yaml` — they're configuration, not secrets

### Config Loading Strategy

- **D-13:** YAML-first loading: config module reads YAML files first, then overlays env var values for secrets/deployment overrides
- **D-14:** Replace frozen dataclass with mutable dataclass or plain class — frozen dataclass prevents YAML merge
- **D-15:** Single entry point: `src/utils/config.py` loads all 3 YAML files, merges with env vars, exposes unified `config` object
- **D-16:** Existing import pattern preserved: `from src.utils.config import config` — all downstream code unchanged
- **D-17:** `pyyaml` added to project dependencies

### Specific Hardcoded Values to Extract

Ingestion (`ingest_and_expand.py`):
- **D-18:** `CHUNK_SIZE = 50_000` → `pipeline.chunk_size`
- **D-19:** `CSV_PATH` → `pipeline.csv_path` (default: relative path to `combined_dataset.csv`)

Synthetic Generator (`synthetic_generator.py`):
- **D-20:** `MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.2"` → `generation.model_id`
- **D-21:** `PROVIDER = "featherless-ai"` → `generation.provider`
- **D-22:** `MAX_RETRIES = 3`, `RETRY_DELAYS = [5, 10, 20]` → `generation.max_retries`, `generation.retry_delays`
- **D-23:** `MESSAGES_PER_CALL = 10` → `generation.messages_per_call`
- **D-24:** `TARGET_TOTAL = 10_000` → `generation.target_total`
- **D-25:** `LABEL_DISTRIBUTION` (0.30/0.30/0.40) → `generation.label_distribution`

Traffic Generator (`synthetic_traffic_generator.py`):
- **D-26:** `TARGET_RPS = 15` → `generation.target_rps`

Text Cleaner (`text_cleaner.py`):
- **D-27:** PII regex patterns stay hardcoded (they're algorithm design, not config) — NOT extracted to YAML

Middleware (`middleware.py`):
- **D-28:** `_MINIO_BATCH_SIZE = 10_000` → `pipeline.minio_batch_size`
- **D-29:** `_INTERCEPT_PATHS = {"/messages", "/flags"}` stays hardcoded (API contract, not config)

Batch Pipeline (`compile_training_data.py`):
- **D-30:** Quality gate thresholds: min 10 chars, max 5000 chars → `pipeline.quality_min_text_length`, `pipeline.quality_max_text_length`
- **D-31:** `#ERROR!` pattern → `pipeline.quality_error_pattern`
- **D-32:** Split ratio 70/15/15 → `pipeline.split_train`, `pipeline.split_val`, `pipeline.split_test`
- **D-33:** `random_state = 42` → `pipeline.random_seed`

Docker Compose:
- **D-34:** Docker Compose credentials remain in docker-compose.yaml (separate concern from app-level YAML config — Docker needs its own env vars)

### Agent's Discretion

- YAML file format details (inline comments style, key ordering)
- Whether to use `OmegaConf`, `pydantic-settings`, or plain `yaml.safe_load` for loading
- Config validation (type checking on load vs lazy validation)
- Whether to generate a `config/defaults.yaml` that users copy and customize
- Config file path resolution strategy (relative to project root vs absolute)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Documents
- `Idea.md` — Data architecture implementation plan: describes data_design_document.md target (§1), Mermaid diagrams, and overall pipeline architecture
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: system design, data flow, deployment architecture relevant to design doc content

### Requirements
- `.planning/REQUIREMENTS.md` — Requirements DESIGN-01 and CONFIG-01 with acceptance criteria

### Prior Phase Context
- `.planning/phases/01-infrastructure-ingestion/01-CONTEXT.md` — Decisions D-01 through D-15 (PostgreSQL schema, MinIO buckets, source tagging)
- `.planning/phases/02-real-time-processing/02-CONTEXT.md` — Decisions D-01 through D-17 (TextCleaner, middleware, cleaned_text storage)
- `.planning/phases/03-batch-pipeline/03-CONTEXT.md` — Decisions D-01 through D-26 (batch pipeline, temporal leakage, stratified split, quality gate)

### Existing Code (integration points)
- `src/utils/config.py` — Current frozen dataclass Config with env vars — to be modified for YAML loading
- `docker/init_sql/00_create_tables.sql` — PostgreSQL schema source of truth for design doc
- `docker/docker-compose.yaml` — Service definitions, port mappings, credentials
- `src/data/ingest_and_expand.py` — CHUNK_SIZE, CSV_PATH hardcoded constants
- `src/data/synthetic_generator.py` — MODEL_ID, PROVIDER, retry config, TARGET_TOTAL hardcoded
- `src/data/synthetic_traffic_generator.py` — TARGET_RPS hardcoded
- `src/data/text_cleaner.py` — PII regex patterns (NOT extracting — algorithm design)
- `src/api/middleware.py` — _MINIO_BATCH_SIZE hardcoded
- `src/data/compile_training_data.py` — Quality gate thresholds, split ratios, random_state hardcoded
- `src/data/prompts.py` — LABEL_DISTRIBUTION, prompt templates (prompts stay as code, distribution moves to YAML)

### Course Reference
- `lecture and labs.txt` — Course lab URLs for relevant tools

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/utils/config.py` — Existing Config dataclass pattern — modify to load YAML, preserve `config` singleton import pattern
- `docker/init_sql/00_create_tables.sql` — Complete schema with all 4 tables — design doc mirrors this
- `src/data/prompts.py` — GenerationPrompt frozen dataclass — label_distribution moves to YAML but prompt templates stay in code

### Established Patterns
- Frozen dataclass for configuration — needs to change (D-14: replace with mutable class)
- `from src.utils.config import import config` used by all modules — preserved as import interface
- YAML not yet used in project — new dependency (`pyyaml`)
- Module-level constants pattern (CHUNK_SIZE, TARGET_RPS, etc.) — replaced by config lookups

### Integration Points
- `src/utils/config.py` — Primary file to modify (add YAML loading, env var override)
- `config/` directory — New directory with 3 YAML files to create
- All pipeline modules — Import changes minimal (still `config.CHUNK_SIZE`), but values come from YAML now
- `pyproject.toml` or `requirements.txt` — Add `pyyaml` dependency
- Design document — New `data_design_document.md` at project root

</code_context>

<specifics>
## Specific Ideas

- Design document should include a "Data Quality Issues" section referencing `data/DATA_ISSUES.md` — shows the pipeline handles known issues
- Mermaid diagrams should be copy-pasteable for the course presentation slides
- Consider adding a `config/example/` directory with annotated example configs for other team members
- YAML config files should have inline comments explaining each parameter (self-documenting)
- The unified config object should expose nested access: `config.pipeline.chunk_size` or flat: `config.get("pipeline.chunk_size")` — prefer nested attribute access to match existing `config.BUCKET_RAW` pattern

</specifics>

<deferred>
## Deferred Ideas

- Config validation framework (pydantic-settings or custom validators) — can add later
- Config hot-reloading — not needed for course project
- Config generation from defaults (`config init` command) — nice-to-have
- Environment-specific config files (dev.yaml, prod.yaml) — single deployment, not needed

</deferred>

---

*Phase: 04-design-doc-config*
*Context gathered: 2026-04-04*
