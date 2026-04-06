# Phase 4: Design Doc & Config - Research

**Researched:** 2026-04-06
**Domain:** Python YAML configuration management, technical documentation, Mermaid diagrams
**Confidence:** HIGH

## Summary

This phase has two deliverables: (1) a data pipeline design document with Mermaid diagrams and schema references, and (2) a `config/pipeline.yaml` that extracts tunable parameters from hardcoded Python constants. Both are well-understood patterns with clear implementation paths.

The YAML config integrates with the existing frozen `Config` dataclass by loading YAML values as defaults, then layering env var overrides on top. PyYAML is the right library choice — it's already an installed transitive dependency (via `huggingface_hub`), is the Python ecosystem standard, and requires zero new dependencies. Mermaid diagrams render natively on GitHub markdown, making them the right choice for version-controllable architecture documentation.

**Primary recommendation:** Use PyYAML `safe_load()` to read `config/pipeline.yaml`, pass values as kwargs to the frozen `Config` dataclass constructor, and keep env vars as overrides for secrets. Create `config/pipeline.yaml` with commented sections for each pipeline stage.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Data pipeline only — documents ingestion, TextCleaner, batch pipeline, MinIO/PostgreSQL schemas. Does NOT document ML training (Aadarsh), model serving (Purvansh), or DevOps (Nitish).
- **D-02:** Sections include: PostgreSQL schema reference, MinIO bucket structure, data flow diagrams, API endpoints (POST /messages, POST /flags with request/response schemas), and key architectural decisions.
- **D-03:** Mermaid diagrams embedded in markdown — version-controllable, renders on GitHub, no external tools needed. Three diagrams: ingestion flow, online preprocessing flow, batch pipeline flow.
- **D-04:** YAML config loads into existing `Config` frozen dataclass (`src/utils/config.py`). YAML is source of truth for defaults; env vars override for deployment (e.g., `DATABASE_URL`, `MINIO_SECRET_KEY` for credentials).
- **D-05:** Config file location: `config/pipeline.yaml` — matches Phase 5 CONTEXT.md reference (D-05 in 05-CONTEXT.md).
- **D-06:** Config loading: add a `load_pipeline_config()` function or integrate into `Config.__post_init__()` that reads YAML and populates fields.
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

### Deferred Ideas (OUT OF SCOPE)
- Parquet format conversion — can be added later if ML team needs it
- Config validation schema (JSON Schema or Pydantic for YAML) — ensures bad config values fail fast
- Config hot-reloading — not needed for a batch pipeline
- Environment-specific YAML files (dev.yaml, prod.yaml) — overkill for single-VM deployment
- Automated config documentation generation from YAML schema

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DESIGN-01 | High-level data design document with schemas, data repositories, and data flow diagrams | PostgreSQL schema documented in `docker/init_sql/00_create_tables.sql`; Mermaid diagrams for 3 flows; MinIO bucket structure from docker-compose |
| CONFIG-01 | Configurable pipeline parameters via YAML (not hardcoded) | PyYAML `safe_load()` → frozen dataclass pattern; 10 tunable params identified across 4 source files |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | 6.0.3 | YAML parsing for pipeline config | Python ecosystem standard for YAML; already installed as transitive dep of `huggingface_hub`; `safe_load()` prevents code execution |
| Mermaid | N/A (GitHub-native) | Embedded diagrams in markdown | Renders natively on GitHub; version-controllable; no external tools needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses | stdlib | Frozen Config dataclass | Already in use — extend, don't replace |
| python-dotenv | (already used) | `.env` file loading | Loads env vars that override YAML defaults |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML | ruamel.yaml (0.19.1 installed) | ruamel.yaml preserves comments/roundtrip — unnecessary for read-only config; heavier dependency; PyYAML is already transitive dep |
| Mermaid | PlantUML, draw.io SVG | PlantUML needs server/renderer; draw.io SVGs are binary blobs in git; Mermaid is text + GitHub-native |
| Embedded Mermaid | Link to external diagrams | External links break; embedded diagrams survive repo forks/clones |

**Installation:** None needed — PyYAML 6.0.3 already installed. No new dependencies.

**Version verification:**
```
PyYAML: 6.0.3 (verified at runtime 2026-04-06)
ruamel.yaml: 0.19.1 (verified — available but not recommended)
```

## Architecture Patterns

### Recommended Project Structure
```
├── config/
│   └── pipeline.yaml          # NEW — tunable pipeline parameters
├── docs/
│   └── data-design.md         # NEW — design document
├── src/
│   ├── utils/
│   │   └── config.py          # MODIFIED — add YAML loading
│   ├── data/
│   │   ├── ingest_and_expand.py       # MODIFIED — use config.chunk_size
│   │   ├── compile_training_data.py   # MODIFIED — use config.quality_*, config.*_split_ratio
│   │   ├── text_cleaner.py            # UNCHANGED
│   │   └── synthetic_traffic_generator.py  # MODIFIED — use config.rps_target
│   └── ...
```

### Pattern 1: YAML-Backed Frozen Dataclass Config
**What:** Load YAML file as defaults, pass to frozen dataclass constructor, env vars override secrets.
**When to use:** When you need immutable config with file-based defaults and env var overrides for deployment.
**Why frozen dataclass:** Immutable after creation prevents accidental mutation; `__post_init__` validates types; existing code already imports `config` singleton.

```python
# Source: Adapted from existing src/utils/config.py pattern + PyYAML docs
import os
import yaml
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "pipeline.yaml")


def _load_yaml_defaults(path: str = DEFAULTS_PATH) -> dict:
    """Load pipeline.yaml defaults. Returns empty dict if file missing."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


@dataclass(frozen=True)
class Config:
    # --- Infrastructure (env var overrides, secrets) ---
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://user:chatsentry_pg@localhost:5432/chatsentry",
    )
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "chatsentry_minio")
    MINIO_SECURE: bool = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    HF_TOKEN: str = os.environ.get("HF_TOKEN", "")

    # --- Pipeline tunables (from YAML) ---
    BUCKET_RAW: str = "zulip-raw-messages"
    BUCKET_TRAINING: str = "zulip-training-data"
    CHUNK_SIZE: int = 50_000
    QUALITY_MIN_TEXT_LENGTH: int = 10
    QUALITY_MAX_TEXT_LENGTH: int = 5_000
    QUALITY_ERROR_PATTERN: str = "#ERROR!"
    TRAIN_SPLIT_RATIO: float = 0.70
    VAL_SPLIT_RATIO: float = 0.15
    TEST_SPLIT_RATIO: float = 0.15
    RPS_TARGET: int = 15
    MINIO_BATCH_UPLOAD_SIZE: int = 10_000
    SYNTHETIC_TARGET_ROWS: int = 10_000
    RANDOM_STATE: int = 42


# Module-level singleton — matches existing pattern `from src.utils.config import config`
_yaml = _load_yaml_defaults()
config = Config(**_yaml)
```

**Key design decisions:**
- YAML values become `Config(**yaml_dict)` kwargs — PyYAML keys must match field names case-sensitively
- Env vars are set as dataclass defaults (evaluated at class definition time) — YAML overrides them when present
- Missing YAML file → empty dict → all defaults from dataclass field definitions → safe fallback
- Frozen dataclass stays frozen — `config` is still immutable after creation
- No `__post_init__` magic — simple constructor kwargs pattern is more predictable

### Pattern 2: Mermaid Data Flow Diagrams in Markdown
**What:** Embed Mermaid `flowchart TD` blocks directly in markdown. GitHub renders them natively.
**When to use:** Architecture docs, data flow, sequence diagrams in version-controlled repos.
**Example:**
````
```mermaid
flowchart TD
    A[combined_dataset.csv] -->|chunked read| B[ingest_and_expand.py]
    B -->|CSV chunks| C[MinIO: zulip-raw-messages]
    C -->|read chunks| D[compile_training_data.py]
    D -->|TextCleaner| E[cleaned DataFrame]
    E -->|quality gate| F[train/val/test split]
    F -->|versioned CSV| G[MinIO: zulip-training-data]
```
````

**Three diagrams required (per D-03):**
1. **Ingestion flow:** CSV → `ingest_and_expand.py` → MinIO raw bucket → synthetic HF API → MinIO raw bucket
2. **Online preprocessing flow:** Webhook → FastAPI → TextCleaner → PostgreSQL → inference response
3. **Batch pipeline flow:** PostgreSQL → compile_training_data.py → TextCleaner → quality gate → split → MinIO training bucket

### Anti-Patterns to Avoid
- **Config as Python module:** Don't use `import config` with module-level variables — YAML is explicitly required (D-04, D-05)
- **Config hot-reloading:** Not needed for batch pipeline; adds complexity with no benefit
- **JSON Schema validation for YAML:** Deferred per context — keep it simple, fail gracefully on bad types
- **Separate config per environment:** Overkill for single-VM deployment per deferred ideas

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | `yaml.safe_load()` | PyYAML already installed; handles edge cases (encoding, multiline, types) |
| Config merging (file + env) | Custom merge logic | Dataclass constructor kwargs | Python dataclass handles type coercion; env vars set as defaults, YAML overrides |
| Mermaid rendering | Custom SVG generator | GitHub-native Mermaid | No toolchain needed; renders in PRs, README, wiki |
| Missing config file handling | Custom fallback chain | `os.path.exists()` check → empty dict | Dataclass defaults provide full fallback |

**Key insight:** The frozen dataclass pattern already handles 90% of config management. The only new code is `_load_yaml_defaults()` — approximately 10 lines — plus new fields on the existing `Config` class.

## Common Pitfalls

### Pitfall 1: YAML Key Name Mismatches
**What goes wrong:** YAML keys use `snake_case` (`chunk_size`) but dataclass fields are `UPPER_SNAKE_CASE` (`CHUNK_SIZE`). `Config(**yaml_dict)` silently ignores unmatched keys.
**Why it happens:** Python naming conventions (UPPER for constants) vs YAML conventions (lowercase).
**How to avoid:** Either (a) use lowercase keys in YAML and uppercase fields in dataclass with a key-mapping step, or (b) use lowercase in YAML and lowercase fields in dataclass (breaks convention D-08 says "UPPER_SNAKE_CASE for constants"). **Recommendation:** Use lowercase YAML keys, add a `_normalize_keys()` function that uppercases all keys before passing to `Config()`.
**Warning signs:** Config fields retain default values despite YAML having different values.

### Pitfall 2: Frozen Dataclass Construction Failure
**What goes wrong:** Passing wrong types to `Config()` raises `TypeError` at import time, crashing all modules that import `config`.
**Why it happens:** YAML parses `50000` as int, `"50000"` as string. If YAML has `"50000"` (quoted), Python gets a string where int is expected.
**How to avoid:** Use unquoted numeric values in YAML. Add type annotations to all Config fields (already present). Consider a `__post_init__` validation step.
**Warning signs:** `TypeError: Config.__init__() argument must be str, not int`.

### Pitfall 3: Config File Not Found in Docker
**What goes wrong:** `config/pipeline.yaml` exists locally but isn't copied into the Docker container, causing fallback to defaults silently.
**Why it happens:** Dockerfile COPY doesn't include `config/` directory.
**How to avoid:** Add `COPY config/ ./config/` to Dockerfile. Or: use `config/pipeline.example.yaml` as committed reference.
**Warning signs:** Pipeline behaves differently in Docker vs local (different chunk sizes, thresholds).

### Pitfall 4: Design Doc Staleness
**What goes wrong:** Design document describes schemas/as-of a date, then code changes, doc becomes misleading.
**Why it happens:** No automation to detect drift between doc and code.
**How to avoid:** Design doc is a snapshot for the demo. Include "Last Updated" date. Don't aim for auto-sync — this is a course project, not production.
**Warning signs:** Schema in doc doesn't match `00_create_tables.sql`.

## Code Examples

### Loading YAML Config
```python
# Source: PyYAML docs — safe_load for untrusted input
import yaml

def _load_yaml_defaults(path: str) -> dict:
    """Load YAML config. Returns empty dict if file missing."""
    if not os.path.exists(path):
        logger.warning("Config file not found: %s — using defaults", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}
```

### Config YAML Structure
```yaml
# config/pipeline.yaml — ChatSentry Data Pipeline Configuration
# Loaded by src/utils.config at startup. Env vars override secrets.

ingestion:
  chunk_size: 50000            # Rows per CSV chunk (ingest_and_expand.py)
  synthetic_target_rows: 10000 # Target rows for HF synthetic generation

quality:
  min_text_length: 10          # Drop rows shorter than this (DATA_ISSUES.md Issue 5)
  max_text_length: 5000        # Truncate rows longer than this (DATA_ISSUES.md Issue 5)
  error_pattern: "#ERROR!"     # Remove rows matching this pattern (DATA_ISSUES.md Issue 4)

split:
  train_ratio: 0.70            # Training set proportion
  val_ratio: 0.15              # Validation set proportion
  test_ratio: 0.15             # Test set proportion
  random_state: 42             # Reproducibility seed

buckets:
  raw: zulip-raw-messages      # MinIO bucket for ingested data
  training: zulip-training-data # MinIO bucket for versioned training snapshots

traffic:
  rps_target: 15               # Requests per second for synthetic traffic generator

batch:
  upload_size: 10000           # Rows per MinIO upload batch
```

### Consuming Config in Pipeline Scripts
```python
# Before (hardcoded):
CHUNK_SIZE = 50_000

# After (from config):
from src.utils.config import config
CHUNK_SIZE = config.CHUNK_SIZE
```

### Mermaid Diagram — Batch Pipeline Flow
````
```mermaid
flowchart TD
    PG[(PostgreSQL)] -->|INCREMENTAL_QUERY| A[compile_training_data.py]
    MIO[MinIO: zulip-raw-messages] -->|CSV chunks| A
    A -->|raw text| B[TextCleaner]
    B -->|cleaned_text| C[select_output_columns]
    C -->|5-column DataFrame| D[apply_quality_gate]
    D -->|filtered| E[stratified_split]
    E -->|70%| F[train.csv]
    E -->|15%| G[val.csv]
    E -->|15%| H[test.csv]
    F -->|versioned upload| I[MinIO: zulip-training-data]
    G -->|versioned upload| I
    H -->|versioned upload| I
```
````

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded constants in each script | YAML config + frozen dataclass | This phase | Single source of truth; operators change params without code edits |
| No design documentation | Markdown + Mermaid diagrams | This phase | Demo video talking points; onboarding for ML team |
| `dotenv` only for config | YAML defaults + env var override | This phase | Structured non-secret config in version control |

**Deprecated/outdated:**
- Hardcoded `CHUNK_SIZE = 50_000` in `ingest_and_expand.py` → replaced by `config.CHUNK_SIZE`
- Hardcoded quality thresholds in `compile_training_data.py` → replaced by `config.QUALITY_*`
- Hardcoded split ratios in `stratified_split()` → replaced by `config.*_SPLIT_RATIO`

## Open Questions

1. **YAML key naming convention (UPPER vs lower)**
   - What we know: Dataclass fields are UPPER_SNAKE_CASE; YAML convention is lowercase
   - What's unclear: Whether to normalize keys or use a nested structure with lowercase
   - Recommendation: Use lowercase YAML keys with a `_normalize_keys()` helper that uppercases before passing to `Config()`. Keeps YAML readable, dataclass fields Pythonic.

2. **Design doc location (`docs/` vs root)**
   - What we know: `docs/` directory exists (currently has `LIVE-TESTING.md`)
   - What's unclear: No team convention established
   - Recommendation: `docs/data-design.md` — follows `docs/` directory pattern already in repo

3. **TextCleaner step enable/disable via YAML**
   - What we know: User said "tunable params only"; TextCleaner step order is fixed (D-08)
   - What's unclear: Whether enabling/disabling individual steps counts as "tunable"
   - Recommendation: Keep TextCleaner steps fixed (not in YAML). The step ORDER is a design decision, not an operator knob. If needed later, add `text_cleaner.enabled_steps` list — deferred.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyYAML | YAML config loading | ✓ | 6.0.3 | — (stdlib `json` if YAML truly unavailable, but not needed) |
| ruamel.yaml | Alternative YAML lib | ✓ | 0.19.1 | Not needed — PyYAML is sufficient |
| Mermaid | Diagram rendering | ✓ (GitHub) | N/A | Render locally via mermaid-cli if needed |
| python-dotenv | Env var loading | ✓ | (installed) | — |

**Missing dependencies with no fallback:** None — all required dependencies are available.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `tests/` directory with `test_*.py` pattern |
| Quick run command | `pytest tests/test_config.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DESIGN-01 | Design doc exists with required sections | manual-only | N/A — doc review | N/A |
| CONFIG-01 | YAML loads into Config; params override defaults | unit | `pytest tests/test_config.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_config.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Config test green; design doc reviewed manually

### Wave 0 Gaps
- [ ] `tests/test_config.py` — test YAML loading, missing file fallback, env var override, type coercion
- [ ] `config/pipeline.yaml` — must be created before tests can run

## Sources

### Primary (HIGH confidence)
- PyYAML 6.0.3 — verified installed and functional at runtime (2026-04-06)
- `src/utils/config.py` — existing frozen dataclass pattern (24 lines, read in full)
- `docker/init_sql/00_create_tables.sql` — PostgreSQL schema (4 tables, GIN index)
- `src/data/compile_training_data.py` — hardcoded thresholds at lines 80-86, 153-166
- `src/data/ingest_and_expand.py` — hardcoded CHUNK_SIZE at line 21
- `.planning/phases/05-integrate-great-expectations-data-quality-framework/05-CONTEXT.md` — D-05 confirms Phase 5 depends on `config/pipeline.yaml`

### Secondary (MEDIUM confidence)
- GitHub Mermaid documentation — confirms native rendering in markdown (no external tools)
- Great Expectations 1.15.2 — confirmed installed; Phase 5 reads from same YAML config

### Tertiary (LOW confidence)
- None — all findings verified against installed packages or project code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyYAML already installed, Mermaid is GitHub-native, no new deps needed
- Architecture: HIGH — frozen dataclass pattern already established; YAML integration is straightforward
- Pitfalls: MEDIUM — key naming mismatch and Docker copy are practical concerns discovered by analysis, not from external sources

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (30 days — PyYAML and Mermaid are stable technologies)
