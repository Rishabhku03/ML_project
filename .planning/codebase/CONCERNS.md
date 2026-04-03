# Codebase Concerns

**Analysis Date:** 2026-04-03

## Tech Debt

**No application code exists yet:**
- Issue: Project contains only planning documents (`Idea.md`, `MLOps-Project-Report-TeamChatSentry.txt`, `MLOps_-_Project-Presentation-Team-ChatSentry.txt`) and a raw dataset (`combined_dataset.csv`). No Python scripts, FastAPI endpoints, training code, or infrastructure-as-code has been implemented.
- Files: `Idea.md` (lines 1-42), `MLOps-Project-Report-TeamChatSentry.txt`
- Impact: Entire project is pre-implementation. Every planned component (data ingestion, online processor, batch pipeline, FastAPI serving, MinIO setup, model retraining) must be built from scratch.
- Fix approach: Follow the implementation plan in `Idea.md`. Priority order: (1) infrastructure setup on Chameleon, (2) data ingestion pipeline, (3) model training/fine-tuning, (4) FastAPI serving, (5) CI/CD pipeline.

**No `.gitignore` in project root:**
- Issue: No `.gitignore` file exists at the project root. The 218MB `combined_dataset.csv` is likely tracked by git or will be committed.
- Files: Project root directory
- Impact: Repository bloat, slow clones, potential CI/CD failures. The 218MB CSV file will make the repo unusable if committed.
- Fix approach: Create `.gitignore` immediately. Add `*.csv`, `*.pkl`, `*.model`, `__pycache__/`, `venv/`, `.env`, `*.egg-info/`, and model artifact directories.

**Missing `requirements.txt` or `pyproject.toml`:**
- Issue: No Python dependency file exists. The project requires FastAPI, transformers, torch, pandas, scikit-learn, and Chameleon tooling (`python-chi`) but none are declared.
- Files: Project root
- Impact: Cannot reproduce environment, no pinned dependencies, setup is entirely manual.
- Fix approach: Create `requirements.txt` or `pyproject.toml` with pinned versions based on lab toolchain. Include at minimum: `fastapi`, `uvicorn`, `transformers`, `torch`, `pandas`, `scikit-learn`, `python-chi`.

## Known Bugs

**Dataset column schema mismatch with stated labels:**
- Symptoms: `combined_dataset.csv` has columns `text`, `is_suicide`, `is_toxicity` — a binary toxicity label. But the project plan and report describe 6 Jigsaw labels (toxic, severe_toxic, obscene, threat, insult, identity_hate). These labels are missing from the combined dataset.
- Trigger: Any attempt to train a multi-label classifier as described in `MLOps-Project-Report-TeamChatSentry.txt` (lines 22-29) will fail against this dataset.
- Files: `combined_dataset.csv`, `Idea.md` (lines 23-25)
- Workaround: None — the dataset has already been collapsed to binary labels. The multi-label Jigsaw dataset appears to have been merged/flattened.
- Root cause: Unknown. The raw Jigsaw dataset with 6 labels may have been pre-processed into binary before combining with the suicide dataset.

**Dataset column naming inconsistency:**
- Symptoms: Column is named `is_suicide` (binary 0/1) in `combined_dataset.csv`, but the report describes it as "suicide" and "non-suicide" labels from the "suicide and depression detection" dataset (lines 36-42 of `MLOps-Project-Report-TeamChatSentry.txt`).
- Files: `combined_dataset.csv` (line 1 header: `text,is_suicide,is_toxicity`)
- Impact: Confusion between detection of suicide ideation (positive class) vs non-suicide. Column name is clear but the framing in docs may cause labeling mistakes in downstream code.
- Workaround: Use `is_suicide == 1` as positive class for self-harm detection. Document this clearly in code.

## Security Considerations

**PII in training dataset:**
- Risk: The `combined_dataset.csv` contains 1.58M real Reddit posts about suicide, depression, and toxic behavior. These may contain personal names, locations, usernames, and other PII from real users.
- Files: `combined_dataset.csv` (218MB, 1,586,127 rows)
- Current mitigation: None. The plan mentions "Use out-of-the-box LLM to scrub personal data" for training data pipeline (line 58 of `MLOps-Project-Report-TeamChatSentry.txt`) but this is not implemented.
- Recommendations: Implement PII scrubbing as part of the ingestion pipeline (`Idea.md` line 39). Consider using `presidio` or a local LLM for de-identification before any model training.

**No authentication/authorization plan for FastAPI endpoints:**
- Risk: The plan describes `POST /messages` and `POST /flags` endpoints (`Idea.md` lines 28-29) but no authentication mechanism is specified. Endpoints may be publicly accessible.
- Files: `Idea.md` (lines 27-30)
- Current mitigation: None specified in any documentation.
- Recommendations: Implement Zulip webhook signature validation. Add API key authentication for internal endpoints. Never expose MinIO or PostgreSQL ports publicly.

**Dataset publicly accessible without access controls:**
- Risk: The 218MB `combined_dataset.csv` with sensitive mental health content (suicide/self-harm posts) sits unprotected in the project directory.
- Files: `combined_dataset.csv`
- Current mitigation: None.
- Recommendations: Restrict file permissions. If uploading to MinIO, set bucket policies to private access only. Consider IRB review implications given this is a university project with real user content about self-harm.

## Performance Bottlenecks

**Dataset too large for in-memory processing without chunking:**
- Problem: `combined_dataset.csv` is 218MB with 1.58M rows. Loading the entire dataset into pandas memory for preprocessing or training may cause OOM on the planned 4 vCPU/16GB RAM VM.
- Files: `combined_dataset.csv`
- Cause: Single monolithic CSV file without partitioning.
- Improvement path: Use chunked reading (`pd.read_csv(chunksize=N)`), partition into smaller files, or convert to Parquet format for columnar access. Consider using Iceberg format as mentioned in `Idea.md` line 12.

**Single VM bottleneck for all services:**
- Problem: The deployment plan calls for Zulip app, PostgreSQL, and ML inference API to all run on a single 4 vCPU / 16GB RAM VM (`MLOps-Project-Report-TeamChatSentry.txt` line 71).
- Files: `MLOps-Project-Report-TeamChatSentry.txt` (lines 66-74)
- Cause: Budget constraints for Chameleon Cloud.
- Improvement path: At minimum, run services in isolated Docker containers with resource limits. Monitor memory carefully. Consider offloading inference to a separate container or leveraging the dynamic VM provisioning described for retraining (line 72-73).

**No caching strategy for inference:**
- Problem: The serving architecture (`MLOps-Project-Report-TeamChatSentry.txt` lines 30-46) targets <200ms P95 latency with 15-20 RPS. No caching or batching strategy is described for repeated/similar messages.
- Files: `MLOps-Project-Report-TeamChatSentry.txt`
- Cause: Not yet designed.
- Improvement path: Add message deduplication cache (Redis or in-memory). Consider batched inference for concurrent requests. Pre-compute hashes of previously-seen toxic patterns.

## Fragile Areas

**No code exists — entire system is fragile by nature:**
- Why fragile: Zero implementation. All architecture decisions are in planning documents only. No validation of feasibility.
- Files: `Idea.md`, `MLOps-Project-Report-TeamChatSentry.txt`
- Common failures: Architecture assumptions may not hold (e.g., hateBERT fine-tuning may not converge, Chameleon VM provisioning may fail, latency targets may be unrealistic on single VM).
- Safe modification: Build incrementally. Validate each component before proceeding. Start with data pipeline, then model training, then serving.

**Threshold-based moderation decisions:**
- Why fragile: The moderation system uses hardcoded confidence thresholds (`>0.85` high confidence, `0.60-0.85` medium, `>0.30` self-harm) from `MLOps-Project-Report-TeamChatSentry.txt` lines 36-46.
- Files: `MLOps-Project-Report-TeamChatSentry.txt` (lines 80-96 in presentation version)
- Common failures: Thresholds tuned on test set may not generalize. False positives erode trust; false negatives miss harmful content.
- Safe modification: Make thresholds configurable via environment variables. Implement A/B testing framework. Track precision/recall in production.

**Model retraining trigger based on fixed count (200 flags):**
- Why fragile: "Model retraining is triggered by 200 new verified flags or a weekly fallback schedule" (`MLOps-Project-Report-TeamChatSentry.txt` line 65).
- Files: `MLOps-Project-Report-TeamChatSentry.txt` (line 65)
- Common failures: 200 flags may be too few (retraining too frequently = resource waste) or too many (stale model). Depends entirely on traffic volume.
- Safe modification: Make retraining trigger configurable. Add model performance monitoring (drift detection) as a smarter trigger. Start with weekly schedule only.

## Scaling Limits

**Single VM deployment model:**
- Current capacity: 1 VM (4 vCPU / 16GB RAM) running Zulip + PostgreSQL + ML inference
- Limit: ~100 concurrent users / ~15 messages/sec as stated in `MLOps-Project-Report-TeamChatSentry.txt` (lines 68-70)
- Symptoms at limit: Inference latency exceeds 200ms P95 target, database connection exhaustion, OOM kills
- Scaling path: Containerize with Docker Compose. Add horizontal scaling for inference workers. Use managed PostgreSQL. Consider GPU-enabled VM for inference.

**Dataset growth unmanaged:**
- Current capacity: 1.58M rows / 218MB static dataset
- Limit: The plan mentions "synthetic data generation" and "endpoint data generator" (`Idea.md` lines 21-30) which will produce additional data with no archival strategy described.
- Symptoms at limit: Storage exhaustion on Chameleon VM, training times exceeding CI/CD timeout windows.
- Scaling path: Implement data versioning with DVC or Iceberg. Define retention policies. Archive old training snapshots in MinIO.

## Dependencies at Risk

**hateBERT model availability:**
- Risk: hateBERT is hosted on HuggingFace. Model hosting can change, repos can become private, or API changes may break downloads.
- Files: `MLOps-Project-Report-TeamChatSentry.txt` (lines 20-24)
- Impact: Cannot fine-tune or serve model if HuggingFace access breaks.
- Migration plan: Download and cache model locally. Store model artifacts in MinIO. Pin `transformers` library version.

**Chameleon Cloud availability:**
- Risk: Chameleon Cloud (KVM@TACC) is a research testbed with maintenance windows and quota limits. VM provisioning may fail during peak class periods.
- Files: `Idea.md` (lines 14-19), `MLOps-Project-Report-TeamChatSentry.txt` (lines 62-74)
- Impact: Cannot deploy, train, or demo the system.
- Migration plan: Have local Docker-based fallback for development. Use `python-chi` with error handling and retries. Provision VMs early in the semester.

**Zulip webhook integration unverified:**
- Risk: The entire serving architecture depends on Zulip's outgoing webhook integration. This integration has not been prototyped or tested.
- Files: `MLOps-Project-Report-TeamChatSentry.txt` (lines 30-32)
- Impact: If Zulip webhooks don't behave as expected (latency, format, retry behavior), the entire moderation pipeline fails.
- Migration plan: Prototype the webhook integration FIRST before building the inference pipeline. Create a mock Zulip endpoint for testing.

## Missing Critical Features

**No experiment tracking or model registry:**
- Problem: No MLflow, Weights & Biases, or other experiment tracking is mentioned. No model versioning strategy beyond "version tag" references.
- Current workaround: None
- Blocks: Cannot compare model iterations, reproduce results, or roll back to previous model versions. Critical for MLOps course deliverables.
- Implementation complexity: Medium (MLflow setup on Chameleon, as covered in `mlflow-chi` lab — see `lecture and labs.txt` line 15-16).

**No monitoring or observability infrastructure:**
- Problem: No logging, metrics collection, or alerting is defined for the serving layer.
- Current workaround: None
- Blocks: Cannot detect model drift, cannot track latency/throughput against SLA targets, cannot debug production issues.
- Implementation complexity: Medium (Prometheus + Grafana, or simpler: structured logging to stdout).

**No CI/CD pipeline defined:**
- Problem: `MLOps-Project-Report-TeamChatSentry.txt` mentions "CI/CD pipelines" (line 64) but no pipeline configuration (GitHub Actions, GitLab CI, Jenkins) exists.
- Current workaround: Manual deployment
- Blocks: Cannot automate testing, deployment, or model retraining. Core MLOps course deliverable.
- Implementation complexity: Medium-High (requires defining test suite, Docker build, deployment scripts).

**No test suite or testing strategy:**
- Problem: No test files, no test framework configuration, no testing conventions documented.
- Current workaround: None
- Blocks: Cannot validate code quality, model performance, or API behavior before deployment.
- Implementation complexity: Low-Medium (pytest for unit tests, integration tests for API, model evaluation metrics).

## Test Coverage Gaps

**Entire codebase — no tests exist:**
- What's not tested: Everything. No code has been written yet, so no tests exist.
- Risk: When implementation begins, without testing patterns established, code quality will be unverifiable.
- Priority: High
- Difficulty to test: Not applicable — tests must be established as part of initial implementation.

**Dataset quality and distribution:**
- What's not tested: Class balance in `combined_dataset.csv`, presence of corrupted/empty rows, label distribution between `is_suicide` and `is_toxicity`, duplicate entries.
- Files: `combined_dataset.csv`
- Risk: Training on imbalanced or corrupted data yields poor model performance.
- Priority: High
- Difficulty to test: Low — write an EDA script to validate dataset statistics.

---

*Concerns audit: 2026-04-03*
*Project status: Pre-implementation (planning phase only). All concerns are forward-looking risks.*
*Update as implementation progresses and new issues are discovered.*
