# Domain Pitfalls: Content Moderation Data Pipeline

**Domain:** AI content moderation (ChatSentry)
**Researched:** 2026-04-03
**Confidence:** MEDIUM-HIGH (MadeWithML curriculum + OpenAI paper + established MLOps practices)

---

## Critical Pitfalls

Mistakes that cause rewrites, pipeline failures, or make ML training unusable.

---

### Pitfall 1: Data Leakage Through Point-in-Time Violations

**What goes wrong:** Batch pipeline queries PostgreSQL for training data but includes records that were created *after* the moderation decision, or joins tables without temporal constraints. Model sees "future" information during training.

**Why it happens:** SQL joins between `messages`, `moderation_flags`, and `admin_decisions` tables don't respect timestamps. A `LEFT JOIN` pulls in metadata that wasn't available at inference time.

**Consequences:** Training accuracy looks great. Production accuracy is terrible. The model learned patterns that only exist when you already know the answer. This is the #1 silent killer in ML pipelines.

**Prevention:**
- Enforce point-in-time joins: `WHERE m.created_at < d.decided_at`
- Strip post-submission metadata (admin timestamps, user strike counts) before training
- The reference paper (arxiv:2208.03274) explicitly calls out data leakage prevention as critical
- Add explicit schema columns: `feature_snapshot_time` vs `label_time`

**Detection:**
- Compare train vs production accuracy — if train >> production, leakage is likely
- Run `df.expect_column_values_to_not_contain_future_dates()` on training snapshots
- Test: shuffle time columns and check if metrics change (they shouldn't if no leakage)

**Component:** `compile_training_data.py` (DATA-06)

---

### Pitfall 2: Synthetic Data Distribution Shift

**What goes wrong:** HuggingFace-generated synthetic Zulip messages don't match the distribution of real toxic/suicide content. Model trained on synthetic data fails on real data.

**Why it happens:** LLMs tend to generate "clean", formulaic text. Real toxic content has misspellings, slang, code words, emoji usage, and structural patterns that synthetic generators don't replicate. The HuggingFace API doesn't have access to your specific domain's writing patterns.

**Consequences:** Model learns the synthetic distribution, not the real one. Toxicity detection for edge cases (coded language, sarcasm, evolving slang) completely fails.

**Prevention:**
- Mix synthetic with real data — never train on 100% synthetic
- Validate synthetic data with distribution checks: word frequency, message length, vocabulary overlap with real data
- Label synthetic data with a `source=synthetic` flag so you can weight or exclude during training
- Generate adversarial examples (misspellings, emoji variations) intentionally
- Per course requirements the dataset must be expanded, but track the real:synthetic ratio

**Detection:**
- Compare class distribution between real and synthetic (should be similar)
- Check vocabulary overlap: if synthetic uses words never seen in real data, distribution has shifted
- Measure synthetic data perplexity against a model trained on real data

**Component:** `ingest_and_expand.py` (DATA-03, DATA-04)

---

### Pitfall 3: Preprocessing Inconsistency Between Training and Inference

**What goes wrong:** Text preprocessing (markdown removal, emoji standardization, URL extraction) is applied differently during batch pipeline compilation vs. real-time online processing. The training pipeline strips `**bold**` but the online processor doesn't, or vice versa.

**Why it happens:** Two separate code paths exist — `compile_training_data.py` (batch) and `online_processor.py` (real-time). If they're developed independently, preprocessing drift occurs silently.

**Consequences:** Model sees "clean" text during training but "dirty" text during inference (or vice versa). Performance degrades and the bug is invisible because both pipelines "succeed" individually.

**Prevention:**
- Extract preprocessing into a shared module `text_cleaner.py` used by BOTH batch and online paths
- MadeWithML best practice: "combine all preprocessing operations into functions so we can easily apply it to different datasets (training, inference, etc.)"
- Write unit tests that assert identical output given identical input, regardless of path
- Version the preprocessing function alongside the training data

**Detection:**
- Run the same sample text through both pipelines and diff the output
- Golden dataset test: 100 hand-curated texts that both pipelines must process identically

**Component:** Shared between `online_processor.py` (DATA-05) and `compile_training_data.py` (DATA-06)

---

### Pitfall 4: Training Data Snapshot Not Versioned

**What goes wrong:** Batch pipeline overwrites MinIO training data instead of creating versioned snapshots. When the training team reports degraded performance, you can't reproduce what data they trained on.

**Why it happens:** Writing to `s3://bucket/training_data/latest.csv` without timestamps or version tags. No provenance tracking.

**Consequences:** Non-reproducible experiments. Training team can't roll back. No audit trail. Course grading requires demonstrable versioning.

**Prevention:**
- Use immutable snapshots with version tags: `s3://bucket/training_data/v20260403-142301/`
- Include metadata file with each snapshot: source query, preprocessing version, row count, class distribution, generation timestamp
- MadeWithML: "version the locations of our artifacts and pull them as they're needed" — store pointers, not just data
- Use MinIO object metadata or a manifest file

**Detection:**
- Try to answer: "What exact data did the model train on 3 days ago?" If you can't answer, versioning is broken
- Check MinIO bucket — if all files have the same name with different content, overwrites are happening

**Component:** `compile_training_data.py` (DATA-06)

---

### Pitfall 5: Label Noise From Misaligned Multi-Label Columns

**What goes wrong:** The dataset has `is_suicide` (binary) and `is_toxicity` (binary) columns. These come from different source datasets (Reddit suicide detection + Jigsaw toxic comments) that were concatenated. Labeling criteria, annotation guidelines, and inter-annotator agreement differ between sources.

**Why it happens:** `combined_dataset.csv` was created by merging two separate datasets with different labeling protocols. A "toxic" comment in Jigsaw might not be labeled as toxic in the Reddit dataset, and vice versa.

**Consequences:** Model receives contradictory signals. Suicide detection labels from Reddit may have different sensitivity thresholds than toxicity labels from Jigsaw. Class boundaries are fuzzy.

**Prevention:**
- Track `source_dataset` column through the pipeline
- Analyze label distribution per source — if one source has 90% toxic and the other has 5%, that's a red flag
- Consider treating them as separate tasks with shared preprocessing, not a single multi-label problem
- The OpenAI paper (arxiv:2208.03274) emphasizes that taxonomy design and labeling instructions must be consistent

**Detection:**
- Cross-tabulate `source × label` — imbalanced sources need stratified sampling
- Check inter-label correlation: `is_suicide` and `is_toxicity` should have meaningful correlation patterns

**Component:** `ingest_and_expand.py` (DATA-03)

---

## Moderate Pitfalls

Issues that degrade quality but don't cause rewrites.

---

### Pitfall 6: Over-Cleaning Text Data

**What goes wrong:** Aggressive preprocessing strips emojis, punctuation, capitalization, and special characters that carry signal for toxicity detection. A message like `"I HATE you 😡😡😡"` becomes `"i hate you"` — losing ALL emotional signal.

**Why it happens:** Following generic NLP preprocessing advice (lowercase, remove stopwords, strip punctuation) without considering that toxicity detection REQUIRES these features.

**Consequences:** Model can't distinguish angry shouting (CAPS) from calm statements. Emoji patterns that indicate self-harm are removed. Sarcasm detection becomes impossible.

**Prevention:**
- Keep emojis but standardize them (convert unicode variants to canonical form)
- Keep capitalization as a feature (or extract it as `caps_ratio`)
- Keep punctuation count as a feature (excessive `!!!` correlates with toxicity)
- Test: run model with and without these features — measure F1 change

**Detection:**
- Compare feature importance before/after aggressive cleaning
- Manual inspection of 50 cleaned samples — are toxic messages losing their distinguishing features?

**Component:** `online_processor.py` (DATA-05)

---

### Pitfall 7: Under-Cleaning (Leaking PII or Metadata)

**What goes wrong:** Pipeline doesn't scrub usernames, real names, email addresses, or Reddit-specific metadata (subreddit names, post IDs) from text. Model learns to associate specific users or subreddits with labels.

**Why it happens:** Focus on what to keep (emojis, caps) causes PII scrubbing to be deprioritized. Reddit data especially has metadata embedded in text.

**Consequences:** Privacy violation. Model memorizes user names associated with self-harm. GDPR/FERPA risk if training data is shared with the team.

**Prevention:**
- Regex-based PII detection for emails, URLs with user IDs, @mentions
- Replace PII with tokens: `[USER]`, `[EMAIL]`, `[URL]`
- The OpenAI paper uses LLM-based PII detection — but for this project, regex is sufficient
- Test with known PII-containing samples

**Detection:**
- Grep for `@`, email patterns, URL patterns in processed training data
- Check if removing a specific username changes model predictions (memorization test)

**Component:** `compile_training_data.py` (DATA-06), `online_processor.py` (DATA-05)

---

### Pitfall 8: Class Imbalance Ignored in Synthetic Data Generation

**What goes wrong:** Suicide detection data is inherently rare (the OpenAI paper specifically calls out "active learning for rare events"). Synthetic data generation may amplify the majority class (non-toxic) because it's easier to generate, making imbalance worse.

**Why it happens:** Default LLM prompts generate "normal" conversation. Getting the model to generate genuinely toxic or suicidal content requires careful prompting and ethical guardrails.

**Consequences:** Model becomes even more biased toward predicting "safe" content. Recall on dangerous content drops to near zero.

**Prevention:**
- Generate synthetic data specifically for underrepresented classes
- Use stratified sampling when combining real + synthetic
- Monitor class distribution after each synthetic batch
- Apply class weights during training (already in project plan)

**Detection:**
- Track `synthetic_toxic_count / synthetic_total` ratio — target at least 15-20%
- Compare class distribution before and after synthetic augmentation

**Component:** `ingest_and_expand.py` (DATA-03, DATA-04)

---

### Pitfall 9: No Schema Validation on Data Flow Between Components

**What goes wrong:** Data produced by ingestion doesn't match what the batch pipeline expects. Column names change, types shift, null values appear. Pipeline fails silently (wrong results) or loudly (crash).

**Why it happens:** No formal schema contract between pipeline stages. Developer assumes column `text` exists but another component renamed it to `message_text`.

**Consequences:** Pipeline crashes during demo video recording. Or worse, it runs with wrong column mappings and produces garbage training data.

**Prevention:**
- Define Pydantic models or dataclass schemas for each data contract
- Use Great Expectations for data validation (as recommended by MadeWithML testing curriculum)
- At minimum: assert expected columns exist and have correct types before each pipeline stage
- `df.expect_table_columns_to_match_ordered_list(column_list=expected_columns)`

**Detection:**
- Pipeline fails at schema validation step (good — fails early)
- Unit tests that run each component with intentionally malformed input

**Component:** All pipeline components — especially at boundaries between DATA-03→DATA-06

---

### Pitfall 10: FastAPI Endpoint Drift from Real Zulip Webhooks

**What goes wrong:** Dummy FastAPI endpoints accept payloads that don't match real Zulip webhook format. When/if real Zulip integration happens, the online processor receives differently structured data.

**Why it happens:** Building dummy endpoints from imagination rather than from Zulip's actual webhook specification.

**Consequences:** Entire online processing layer needs restructuring. Demo videos show a system that won't work with real Zulip.

**Prevention:**
- Model dummy endpoint payloads on Zulip's actual webhook JSON schema (documented at https://zulip.com/api/outgoing-webhooks)
- Include realistic field names: `message.content`, `message.sender_email`, `message.stream_id`
- Add payload validation with strict Pydantic models

**Detection:**
- Test with actual Zulip webhook sample payloads (available in docs)
- Compare dummy payload structure against Zulip API documentation

**Component:** `online_processor.py` (DATA-05), serving endpoints

---

## Minor Pitfalls

Inconvenient but easily fixed.

---

### Pitfall 11: Docker Compose Resource Contention on Single VM

**What goes wrong:** PostgreSQL, MinIO, FastAPI, Redpanda, Redis, and Airflow all compete for CPU/RAM on a single 4 vCPU / 16GB VM. Pipeline runs slowly or OOM-kills during demo recording.

**Prevention:**
- Set memory limits in `docker-compose.yml` for each service
- Start only needed services per demo video (don't run everything at once)
- Use lightweight alternatives where possible (SQLite for Airflow metadata instead of PostgreSQL)

**Component:** Infrastructure (all components)

---

### Pitfall 12: HuggingFace API Rate Limits Block Synthetic Data Generation

**What goes wrong:** HuggingFace free-tier API has rate limits. Large synthetic data generation jobs hit limits and fail mid-pipeline.

**Prevention:**
- Implement retry with exponential backoff
- Cache generated synthetic data in MinIO — don't re-generate
- Generate in small batches with progress tracking
- Have a fallback: template-based generation if API is unavailable

**Component:** `ingest_and_expand.py` (DATA-03, DATA-04)

---

### Pitfall 13: Demo Video Recordings Show Unrepeatable State

**What goes wrong:** Demo videos recorded with non-deterministic data or random ports. Can't reproduce the exact demo scenario for course staff questions.

**Prevention:**
- Use seeded random state for all synthetic data generation
- Fix ports and service names in docker-compose
- Record the exact commands and timestamps used for each demo
- Keep demo data snapshots in MinIO alongside versioned training data

**Component:** All components (demo workflow)

---

### Pitfall 14: CSV Parsing Issues in 1.58M Row Dataset

**What goes wrong:** `combined_dataset.csv` has text with embedded commas, newlines, quotes. `pd.read_csv()` silently drops rows or misaligns columns.

**Prevention:**
- Use `quoting=csv.QUOTE_ALL` and explicit `escapechar`
- Validate row count after load: `assert len(df) == 1586127`
- Check for NaN in `text` column — likely indicates parsing failure

**Component:** `ingest_and_expand.py` (DATA-03)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Ingestion (DATA-03) | CSV parsing silently drops rows | Validate row count, check for NaN in text column |
| Synthetic generation (DATA-04) | Distribution shift between real and synthetic | Track real:synthetic ratio, validate class distribution |
| Online processing (DATA-05) | Preprocessing inconsistency with batch path | Shared preprocessing module, golden dataset tests |
| Batch pipeline (DATA-06) | Data leakage through temporal joins | Point-in-time joins, strip post-submission metadata |
| MinIO storage (DATA-02) | Overwrites without versioning | Immutable snapshots with timestamps |
| Demo videos (all) | Non-reproducible state during recording | Seeded randomness, fixed ports, command logs |

---

## Confidence Assessment

| Pitfall | Confidence | Reason |
|---------|------------|--------|
| Data leakage (P1) | HIGH | Well-documented in literature, explicitly in reference paper |
| Synthetic distribution shift (P2) | HIGH | Common in all synthetic data projects, well-understood |
| Preprocessing inconsistency (P3) | HIGH | MadeWithML explicitly warns about this, standard MLOps knowledge |
| Versioning failures (P4) | HIGH | Standard MLOps best practice from MadeWithML curriculum |
| Label noise (P5) | MEDIUM | Depends on exact merging logic of source datasets |
| Over/under-cleaning (P6-7) | MEDIUM | Specific to content moderation domain, not always documented |
| Class imbalance (P8) | HIGH | Reference paper emphasizes this for rare events |
| Schema validation (P9) | HIGH | Standard software engineering practice, universal |
| Endpoint drift (P10) | MEDIUM | Depends on Zulip API specifics |
| Docker contention (P11) | MEDIUM | Depends on actual service resource usage |
| API rate limits (P12) | MEDIUM | Depends on HuggingFace plan and batch size |
| Demo state (P13) | LOW | Project management issue, not technical |
| CSV parsing (P14) | MEDIUM | Common with large text datasets |

---

## Sources

- MadeWithML by Anyscale — [Data Preprocessing](https://madewithml.com/courses/mlops/preprocessing/) (WARNING: local vs global preprocessing, split first)
- MadeWithML — [Data Quality](https://madewithml.com/courses/foundations/data-quality/) (garbage in, garbage out principle)
- MadeWithML — [Versioning](https://madewithml.com/courses/mlops/versioning/) (version artifacts, not raw data)
- MadeWithML — [Testing](https://madewithml.com/courses/mlops/testing/) (Great Expectations for data validation, behavioral testing)
- MadeWithML — [Data Engineering](https://madewithml.com/courses/mlops/data-engineering/) (observability, data lineage, schema contracts)
- arxiv:2208.03274 — "A Holistic Approach to Undesired Content Detection in the Real World" (OpenAI, AAAI-23) — data quality control, active learning for rare events, leakage prevention
- ChatSentry PROJECT.md — project constraints and requirements
- ChatSentry ARCHITECTURE.md — dual-path data flow (real-time + batch)
