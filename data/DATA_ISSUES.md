# Data Quality Issues — combined_dataset.csv

**Source:** Deep analysis via `sample_dataset.py` (2026-04-04)
**Dataset:** 391,645 rows × 3 columns (text, is_suicide, is_toxicity), 234.65 MB
**File:** `data/combined_dataset.csv`

---

## Issue 1: Severe Toxicity Class Imbalance (23×)

- **Severity:** HIGH
- **Evidence:** is_toxicity=1 covers only 4% of rows (≈15,666) vs is_toxicity=0 at 96% (≈375,979). Ratio: 23.14:1.
- **Impact:** Model will bias heavily toward non-toxic predictions. Precision/recall on toxic class will be poor without mitigation.
- **Recommended action:** Apply stratified sampling, SMOTE oversampling, or class weights during training. Consider collecting more toxic examples.

## Issue 2: Mutual Exclusivity of Labels (Zero Overlap)

- **Severity:** HIGH
- **Evidence:** Cross-tabulation shows 0 rows where is_suicide=1 AND is_toxicity=1. Labels are completely disjoint.
- **Impact:** Multi-label classification setup is misleading — this is effectively two separate binary problems sharing the same text pool, not a joint label space. Model architecture and evaluation metrics must reflect this.
- **Recommended action:** Treat as two independent binary classifiers, not a multi-label task. Document this constraint for the ML team.

## Issue 3: Suicide Text Length as Potential Leakage Signal

- **Severity:** MEDIUM
- **Evidence:** Suicide texts average 1,050 chars vs 366 chars for non-suicide — a 2.87× difference. Median also reflects this gap.
- **Impact:** A model could learn to classify based on text length alone, achieving high accuracy without understanding content. This would not generalize to real chat messages.
- **Recommended action:** Evaluate model sensitivity to text length. Consider length-normalized features or length-stratified evaluation. Flag in model card.

## Issue 4: 262 Duplicate Rows (#ERROR! Artifacts)

- **Severity:** MEDIUM
- **Evidence:** 262 rows (0.07%) are exact duplicates. All contain "#ERROR!" in the text field — a data pipeline artifact, not real user content.
- **Impact:** These rows add noise and may bias the model toward recognizing "#ERROR!" strings as a class signal.
- **Recommended action:** Remove all 262 duplicate rows before training. Add a data validation check that rejects rows containing "#ERROR!".

## Issue 5: Extreme Text Lengths (3 chars to 40,297 chars)

- **Severity:** MEDIUM
- **Evidence:** Shortest text is 3 chars ("IsK"), longest is 40,297 chars. P99 is 4,417 chars — the 40K outlier is 9× beyond P99.
- **Impact:** Ultra-short texts (3 chars) are likely noise with no meaningful signal. Ultra-long texts (40K chars) may be copy-pasted content or spam that doesn't represent typical chat messages. Both distort text length statistics.
- **Recommended action:** Filter texts below 10 chars (noise threshold). Cap or flag texts above 5,000 chars for manual review. Document chosen thresholds.

## Issue 6: Suicide/Non-Suicide Imbalance (70/30)

- **Severity:** LOW-MEDIUM
- **Evidence:** is_suicide split is 70/30 (approximately 274,152 vs 117,493 rows). Moderate imbalance, not as severe as toxicity.
- **Impact:** Model will slightly favor the majority class. Less critical than the toxicity imbalance but still worth addressing.
- **Recommended action:** Use stratified train/test splits. Consider class weights if recall on suicide class is insufficient.

## Issue 7: Minimal Non-ASCII Content (~0.5%)

- **Severity:** LOW
- **Evidence:** ~0.5% of rows contain non-ASCII characters. No null bytes or control characters detected.
- **Impact:** Negligible. The online text cleaner (TextCleaner pipeline) already handles encoding via ftfy.
- **Recommended action:** No action needed — handled by existing preprocessing pipeline.

---

## Summary Table

| # | Issue | Severity | Rows Affected | Action |
|---|-------|----------|---------------|--------|
| 1 | Toxicity imbalance (23×) | HIGH | ~375,979 (majority) | Stratified sampling / oversampling |
| 2 | Label mutual exclusivity | HIGH | All 391,645 | Use two binary classifiers |
| 3 | Suicide text length leakage | MEDIUM | ~274,152 (suicide) | Length-normalized evaluation |
| 4 | 262 #ERROR! duplicates | MEDIUM | 262 | Remove before training |
| 5 | Extreme text lengths | MEDIUM | ~1,000 (est.) | Filter <10 chars, cap >5,000 |
| 6 | Suicide class imbalance | LOW-MEDIUM | ~117,493 (minority) | Stratified splits |
| 7 | Non-ASCII content | LOW | ~1,958 (0.5%) | None (handled by cleaner) |
