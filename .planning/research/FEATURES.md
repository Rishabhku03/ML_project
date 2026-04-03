# Feature Landscape: ChatSentry Data Pipeline

**Domain:** Content moderation data pipeline (text classification, toxic/self-harm detection)
**Researched:** 2026-04-03
**Confidence:** HIGH (architecture docs + reference paper + industry patterns)

---

## Table Stakes

Features the pipeline **must have** or it fails to produce usable training data. Missing any of these makes the pipeline non-functional for the ML team.

### 1. Raw Data Ingestion from CSV

| Attribute | Detail |
|-----------|--------|
| **Feature** | Read `combined_dataset.csv` (1.58M rows, 218MB) and load into pipeline |
| **Why expected** | Foundation of entire pipeline — no ingestion, no data |
| **Complexity** | Low |
| **Notes** | Must handle chunked reading (`pd.read_csv(chunksize=N)`) to avoid OOM on 16GB VM. Convert to Parquet immediately after ingestion for columnar access. |

### 2. MinIO Bucket Creation and Data Upload

| Attribute | Detail |
|-----------|--------|
| **Feature** | Create buckets (`zulip-raw-messages`, `zulip-training-data`) and upload data artifacts |
| **Why expected** | DATA-02 deliverable. MinIO is the team's shared data store — without it, ML team cannot consume training data |
| **Complexity** | Low |
| **Notes** | Use `minio-py` SDK. Buckets must be browsable by course staff (port 9001 UI). Set bucket policies to private. |

### 3. Text Preprocessing Pipeline (Online)

| Attribute | Detail |
|-----------|--------|
| **Feature** | Real-time text cleaning: markdown removal, emoji standardization, URL extraction, PII scrubbing |
| **Why expected** | DATA-05 deliverable. HateBERT expects clean text — raw Zulip messages contain markdown formatting (`**bold**`, `~~strike~~`, `[links](url)`), emojis (Unicode + shortcodes), URLs, and potentially PII |
| **Complexity** | Medium |
| **Notes** | See detailed breakdown below |

#### Text Preprocessing Sub-features

| Sub-feature | Implementation | Priority |
|-------------|----------------|----------|
| **Markdown stripping** | Regex-based removal of `*`, `**`, `~~`, `[text](url)`, `>`, code blocks | Table stakes |
| **URL extraction/replacement** | Extract URLs to separate field, replace with `[URL]` token | Table stakes |
| **Emoji standardization** | Convert emoji shortcodes (`:smile:`) to Unicode, then normalize to a canonical form | Table stakes |
| **PII detection and scrubbing** | Regex for emails, phone numbers, SSN patterns. Optionally LLM-based for names | Table stakes |
| **Unicode normalization** | NFKC normalization to handle homoglyph attacks (e.g., Cyrillic а vs Latin a) | Table stakes |
| **Case normalization** | Lowercase for BERT uncased input | Table stakes |
| **Whitespace collapsing** | Collapse multiple spaces, strip leading/trailing whitespace | Table stakes |
| **HTML entity decoding** | `&amp;` → `&`, `&lt;` → `<`, etc. | Table stakes |
| **Repeated character normalization** | `haaaaate` → `hate` (toxic users often elongate words) | Differentiator |
| **Leet speak detection** | `h4te`, `k1ll` normalization | Differentiator |
| **Toxic span annotation** | Mark which character ranges triggered toxicity detection | Differentiator (future) |

### 4. Synthetic Data Generation via HuggingFace API

| Attribute | Detail |
|-----------|--------|
| **Feature** | Generate Zulip-style synthetic messages (toxic + benign) via LLM API calls |
| **Why expected** | DATA-03 deliverable. Dataset needs synthetic expansion per course requirements (>5GB threshold). No GPU on KVM, so external API is mandatory |
| **Complexity** | Medium-High |
| **Notes** | Must handle rate limiting, retries, cost tracking. Generate in batches. Store generation prompts as metadata for reproducibility |

### 5. Synthetic Traffic Generator (HTTP)

| Attribute | Detail |
|-----------|--------|
| **Feature** | Generate synthetic HTTP POST requests hitting dummy FastAPI endpoints with realistic Zulip message payloads |
| **Why expected** | DATA-04 deliverable. Simulates real traffic for load testing and populating PostgreSQL with test data |
| **Complexity** | Medium |
| **Notes** | Must produce realistic message distributions (95% benign, 4% mildly toxic, 1% severely toxic/self-harm). Control rate to simulate 15-20 RPS |

### 6. Batch Training Data Compilation

| Attribute | Detail |
|-----------|--------|
| **Feature** | Query PostgreSQL for production data, clean it, version it, save to MinIO without data leakage |
| **Why expected** | DATA-06 deliverable. This is the pipeline's primary output — versioned training data the ML team consumes |
| **Complexity** | High |
| **Notes** | See detailed breakdown below |

#### Batch Pipeline Sub-features

| Sub-feature | Implementation | Priority |
|-------------|----------------|----------|
| **Time-windowed queries** | Query only recent data (1-week candidate window per reference paper) | Table stakes |
| **Noise filtering** | Remove bot notifications, spam, unresolved admin logs | Table stakes |
| **Post-submission metadata stripping** | Remove fields created after message submission (moderator decisions, timestamps of review) to prevent target leakage | Table stakes |
| **PII scrubbing (batch)** | LLM-based or regex-based PII removal on training data | Table stakes |
| **Versioned snapshots** | Each compilation produces an immutable, tagged snapshot in MinIO | Table stakes |
| **Data leakage prevention** | Temporal split validation — training data must precede evaluation data chronologically | Table stakes |
| **Class balance reporting** | Report label distribution before/after filtering | Table stakes |
| **Parquet export** | Export training data as Parquet (not CSV) for efficient ML consumption | Table stakes |
| **Iceberg format support** | Optional: write snapshots in Apache Iceberg format for time-travel queries | Differentiator |
| **Automated quality gates** | Reject snapshots that fail quality checks (too few rows, imbalanced classes, schema mismatch) | Differentiator |

### 7. Data Design Document

| Attribute | Detail |
|-----------|--------|
| **Feature** | Schemas, data flow diagrams, and data repository documentation |
| **Why expected** | DATA-01 deliverable. Course staff need to understand the pipeline design |
| **Complexity** | Low |
| **Notes** | Include: table schemas for PostgreSQL, bucket layouts for MinIO, data flow diagrams (Mermaid or ASCII), field definitions |

### 8. Schema Validation

| Attribute | Detail |
|-----------|--------|
| **Feature** | Validate data conforms to expected schema at every pipeline boundary |
| **Why expected** | Without schema validation, corrupted data silently propagates to training. Reference paper emphasizes data quality control as critical |
| **Complexity** | Low-Medium |
| **Notes** | Use Pydantic models for API payloads, pandas schema checks for batch data. Validate: column presence, data types, value ranges, null counts |

---

## Differentiators

Features that **impress course graders** but aren't strictly required for the pipeline to function. These demonstrate MLOps maturity.

### 1. Data Versioning with DVC or Iceberg

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Demonstrates understanding of reproducible ML — the "Ops" in MLOps. Associates model versions with exact data states |
| **Complexity** | Medium-High |
| **Notes** | DVC is simpler (Git-based metadata). Iceberg is more impressive (time-travel, schema evolution). Course materials reference both. Recommendation: DVC for simplicity, mention Iceberg in design doc as future work |

### 2. Data Quality Metrics Dashboard

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Shows operational awareness. Track: class balance, null rates, duplicate rates, text length distribution, PII leak rate across pipeline stages |
| **Complexity** | Medium |
| **Notes** | Can be as simple as a JSON report generated at each pipeline stage, or as complex as a Grafana dashboard. A printed report is sufficient for course demos |

### 3. Active Learning Sampling for Rare Events

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Directly implements the reference paper's key insight — suicide is rare (likely <5% of data). Active learning identifies the most informative examples for labeling |
| **Complexity** | High |
| **Notes** | Reference paper (arxiv:2208.03274) emphasizes this as critical for real-world moderation. Implement: uncertainty sampling on model confidence scores to prioritize human review of ambiguous cases |

### 4. Deduplication Engine

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Reddit posts are often reposted or near-duplicated. Training on duplicates biases the model. Reference paper mentions this explicitly |
| **Complexity** | Medium |
| **Notes** | Use MinHash/LSH for fuzzy deduplication on 1.58M rows. Exact match dedup is table stakes; fuzzy dedup is differentiating |

### 5. Data Drift Detection

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Compare incoming production data distributions against training data. Alert when distributions shift (new slang, new toxicity patterns, seasonal effects) |
| **Complexity** | Medium |
| **Notes** | Compare: text length distribution, vocabulary overlap, label distribution. Statistical tests (KS test, PSI) on feature distributions |

### 6. Reproducible Pipeline with Deterministic Seeds

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Same input + same config = same output. Set random seeds for synthetic generation, train/test splits, shuffling. Log all parameters |
| **Complexity** | Low |
| **Notes** | Small effort, big impact on grading. Log: seed values, API parameters, filter thresholds, timestamp of run |

### 7. Configurable Pipeline Parameters

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | All thresholds, file paths, API keys, and batch sizes in a config file (YAML/JSON), not hardcoded. Supports different configs for dev/staging/prod |
| **Complexity** | Low |
| **Notes** | Use environment variables + config file pattern. This is basic software engineering but many course projects skip it |

### 8. Pipeline Orchestration with Airflow DAGs

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Schedule and monitor pipeline runs. Show ingestion → processing → quality check → upload as a DAG with dependencies |
| **Complexity** | Medium-High |
| **Notes** | Course materials reference Airflow. Even a simple 3-task DAG (ingest → process → upload) demonstrates orchestration concepts |

---

## Anti-Features

Features to **deliberately NOT build**. Building these wastes time, adds complexity, or goes against project constraints.

### 1. Real Zulip Integration

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Connecting to actual Zulip server | PROJECT.md explicitly scopes this out. Real integration adds webhook auth, retry handling, rate limiting, error recovery — all distracting from data pipeline work | Use dummy FastAPI endpoints that accept the same payload format. Document the expected webhook format in the data design doc |

### 2. GPU-Accelerated Processing

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Local LLM inference, GPU-based text processing | KVM@TACC has no GPU. Building GPU-dependent code is dead code | Use HuggingFace API for LLM calls. Use CPU-based regex/string ops for text preprocessing. Pandas handles 1.58M rows fine on 16GB RAM with chunking |

### 3. Full ML Model Training

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| HateBERT fine-tuning, hyperparameter tuning, model evaluation | This is Aadarsh's (Training specialist) responsibility. Building it here creates merge conflicts and duplicated effort | Focus on producing clean, versioned training data in MinIO. Define the output schema the ML team expects. Let them consume it |

### 4. Production-Grade Authentication

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| OAuth2, JWT tokens, RBAC, API gateway | Over-engineering for a course project. The dummy endpoints don't need real auth | Use simple API key validation via environment variable. Document webhook auth format for future Zulip integration |

### 5. Real-Time Streaming Infrastructure (Kafka/Redpanda)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Setting up Kafka/Redpanda for message streaming | The pipeline is batch-oriented (ingest → process → store). Real-time streaming adds operational complexity (Zookeeper, topic management, consumer groups) with no benefit for the data specialist's deliverables | Use simple HTTP POST to FastAPI endpoints. The online processor runs synchronously within the request. Batch pipeline runs on a schedule or manual trigger |

### 6. Over-Engineered Data Format Migration

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Converting entire pipeline to Iceberg, implementing full ACID transactions | PyIceberg setup requires catalog service (Hive metastore), adds significant infrastructure complexity. Overkill for 1.58M rows | Store as Parquet files in MinIO with version-tagged directory structure (`/training-data/v1.0/`, `/training-data/v1.1/`). Mention Iceberg as future work in design doc |

### 7. Custom Text Tokenizer

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Building a custom BPE/WordPiece tokenizer | HateBERT uses BERT's pre-trained tokenizer. A custom tokenizer would be incompatible | Use `transformers.AutoTokenizer.from_pretrained("hatebert")` for tokenization. Preprocessing (markdown, emoji) happens BEFORE tokenization |

### 8. Web UI for Pipeline Management

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Dashboard for triggering runs, viewing data, managing pipeline | Not a deliverable. Adds frontend complexity (React/Vue, API design, state management) unrelated to data engineering | Use CLI scripts with argparse. Use MinIO UI (port 9001) for data browsing. Use Airflow UI if orchestration is implemented |

---

## Feature Dependencies

```
DATA-01 (Design Doc)
  ↓
DATA-02 (MinIO Setup) ──────────────────────────────────┐
  ↓                                                      │
DATA-03 (Ingestion + Synthetic)                          │
  ↓                                                      │
Schema Validation → DATA-06 (Batch Pipeline) ────────────┤
  ↓                                                      │
DATA-04 (Traffic Generator) → DATA-05 (Online Processor)─┘
                                   ↓
                          Versioned Snapshots → ML Team
```

**Critical path:** DATA-02 → DATA-03 → DATA-06 (everything else is parallelizable)

**DATA-04 and DATA-05** are independent of each other — traffic generator populates PostgreSQL, online processor serves real-time inference. Both feed into DATA-06.

---

## MVP Recommendation

For maximum course impact with minimum scope, prioritize in this order:

### Must Build (all table stakes)

1. **DATA-02: MinIO setup** — everything depends on this
2. **DATA-03: Ingestion pipeline** — read CSV, generate synthetic data, upload to MinIO
3. **DATA-05: Online text preprocessing** — markdown, emoji, URL, PII handling
4. **DATA-06: Batch pipeline** — versioned training data compilation with leakage prevention
5. **DATA-01: Design document** — schemas, flow diagrams
6. **DATA-04: Traffic generator** — synthetic HTTP requests to dummy endpoints
7. **Schema validation** — at every pipeline boundary
8. **Class balance reporting** — before/after every pipeline stage

### Should Build (high-value differentiators, 2-3 picks)

Pick based on what looks best in demo videos:

- **Configurable pipeline parameters** (Low effort, high perceived quality)
- **Reproducible pipeline with deterministic seeds** (Low effort, shows MLOps thinking)
- **Data quality metrics report** (Medium effort, directly addresses reference paper's emphasis on quality control)
- **DVC for data versioning** (Medium effort, demonstrates reproducibility)

### Defer (mention in design doc, don't build)

- **Active learning sampling** — too complex for scope, mention as future work
- **Airflow orchestration** — CLI scripts are sufficient for demos
- **Iceberg format** — Parquet is sufficient, mention Iceberg migration path
- **Data drift detection** — requires production traffic we don't have yet

---

## Data Quality Controls (from Reference Paper)

The OpenAI paper (arxiv:2208.03274) emphasizes these data quality patterns that should inform feature decisions:

| Paper Insight | Pipeline Feature | Priority |
|---------------|-----------------|----------|
| "Data quality control is critical" | Schema validation, null checks, duplicate detection | Table stakes |
| "Active learning for rare events" | Class balance reporting, stratified sampling | Differentiator |
| "Content taxonomy design" | Binary labels (`is_suicide`, `is_toxicity`) — simplified but functional | Table stakes |
| "Data leakage prevention" | Temporal splits, metadata stripping, train/eval separation | Table stakes |
| "Model robustness to adversarial inputs" | Unicode normalization, homoglyph detection, repeated char normalization | Differentiator |

---

## Sources

- **Reference paper:** arxiv:2208.03274 — "A Holistic Approach to Undesired Content Detection in the Real World" (OpenAI, AAAI-23)
- **Project context:** `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/CONCERNS.md`
- **MinIO SDK:** minio/minio-py (GitHub) — Python SDK for S3-compatible object storage
- **HuggingFace Datasets:** huggingface.co/docs/datasets — data processing patterns (map, filter, batch processing)
- **Delta Lake:** delta.io — data versioning and ACID transactions (considered but deferred)
- **Toxic Spans dataset:** github.com/ipavlopoulos/toxic_spans — SemEval-2021 Task 5, span-level toxicity annotation

---

*Researched: 2026-04-03*
*Confidence: HIGH — grounded in project architecture docs, reference paper, and verified library documentation*
