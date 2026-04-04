# Data Quality Report: combined_dataset.csv

**Generated:** 2026-04-04
**Dataset:** `combined_dataset.csv` (218 MB, 1,586,127 raw lines)

## Overview

| Metric | Value |
|--------|-------|
| Total rows | 391,645 |
| Columns | `text`, `is_suicide`, `is_toxicity` |
| Unique texts | 391,383 |
| Avg text length | 568.7 chars |
| File size | 218 MB |

### Label Distribution

| is_suicide | is_toxicity | Count | % |
|-----------|------------|-------|---|
| 1 | 0 | 116,037 | 29.63% |
| 0 | 0 | 259,383 | 66.23% |
| 0 | 1 | 16,225 | 4.14% |
| 1 | 1 | **0** | **0.00%** |

---

## CRITICAL Issues

### 1. Mutually Exclusive Labels — Not a Real Combined Dataset

**Severity: CRITICAL**

The dataset has **zero rows** where both `is_suicide=1` AND `is_toxicity=1`. The three label combinations are `(1,0)`, `(0,0)`, and `(0,1)`. This means a message is classified as either toxic OR suicidal, but never both.

**Root cause confirmed:** The toxicity rows (index 232,080–391,628) appear AFTER all suicide rows (index 0–232,072). The dataset was created by **concatenating two separate datasets** — a suicide detection dataset and a toxicity dataset — then combining them into one CSV. The "both-zero" class (`0,0`) is just the non-positive examples from each source.

**Impact:** Any model trained on this data will learn that toxic messages are never suicidal and vice versa. This is a fundamental labeling flaw that makes the dataset unsuitable for multi-label classification without re-labeling.

### 2. 262 #ERROR! Corrupted Rows

**Severity: HIGH**

262 rows have `#ERROR!` as their text content. These are spreadsheet formula errors (likely from Excel/Google Sheets). Of these:
- 214 are labeled `(0, 0)` — non-suicide, non-toxic
- 48 are labeled `(0, 1)` — non-suicide, toxic

Even within the #ERROR! rows, there are **214 label inconsistencies** — the same `#ERROR!` text has conflicting labels across different rows.

**Action:** Remove all 262 rows. They carry no signal and add noise.

### 3. 2,228 Suicide=0 Rows Contain Suicide Keywords

**Severity: HIGH**

2,228 rows labeled `is_suicide=0` contain explicit suicide-related keywords (suicide, kill myself, want to die, self-harm, etc.). Examples:

- Line 220: "My sister's friend has recently passed away from **suicide**" → labeled 0 (discussing someone else's suicide — potentially correct)
- Line 318: "im not **suicidal** or anything but sometimes I feel like not existing" → labeled 0 (ambiguous — borderline)
- Line 1075: "I almost **attempted suicide** when i was 13" → labeled 0 (talking about past attempt — likely mislabeled)

Some may be legitimately non-suicide (discussing others' suicide), but many appear to be **false negatives**. Conversely, 53.3% of suicide=1 rows contain explicit keywords, while 46.7% do NOT — suggesting the model must learn from context, not just keywords.

---

## HIGH Severity Issues

### 4. 13,777 Toxic Language in Both-Zero Rows

**Severity: HIGH**

13,777 rows labeled `(0, 0)` (neither toxic nor suicidal) contain strong toxic language (profanity, slurs, aggressive speech). These are likely **false negatives** for the toxicity label. Examples:

- "Fuck the verizon smart family app..." → labeled non-toxic
- "To the actual dunce... Eat shit and die." → labeled non-toxic

**Impact:** Toxicity model will learn to accept strong profanity as non-toxic, degrading precision.

### 5. Severe Class Imbalance

**Severity: HIGH**

- `is_suicide`: 70.37% negative vs 29.63% positive (2.4:1 ratio) — moderate imbalance
- `is_toxicity`: 95.86% negative vs 4.14% positive (23:1 ratio) — **severe imbalance**

The toxicity label has only 16,225 positive examples. Combined with the mutual exclusion, this means the dataset effectively has:
- 116K suicide-only examples
- 16K toxicity-only examples
- 259K neither examples

---

## MEDIUM Severity Issues

### 6. 262 Duplicate Rows

**Severity: MEDIUM**

262 duplicate rows exist (260 are the #ERROR! rows, 2 are genuine duplicate texts). One text appears 262 times (`#ERROR!`).

### 7. 191,906 Rows with Embedded Newlines (49% of Data)

**Severity: MEDIUM**

Nearly half the dataset contains newline characters within text fields. The worst case has 1,279 newlines in a single text. While valid CSV (quoted fields), this causes issues with:
- Line-based tools (`wc -l`, `head`, `awk`)
- Some CSV parsers that don't handle multi-line fields
- Visual inspection of the raw file (1.58M raw lines vs 391K logical rows)

### 8. 3,777 Very Short/Very Long Texts

**Severity: MEDIUM**

- 3 texts are under 5 characters: `okok`, `:/ `/:, `IsK` — too short for meaningful classification
- 377 texts exceed 10,000 characters (max: 40,297 chars) — may cause memory/batch issues during training
- 2,398 texts exceed 5,000 characters — unusually long for chat messages

---

## LOW Severity Issues

### 9. 20,833 Rows with Trailing Whitespace

**Severity: LOW**

Trailing whitespace in the text column. Easy to fix with `.strip()` during preprocessing.

### 10. 8,163 Rows with HTML Entities

**Severity: LOW**

HTML entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#x200B;`) present in text. Example: `&lt;3` instead of `<3`. Likely from web-scraped data. Requires HTML entity decoding during preprocessing.

### 11. 10 Rows with Unicode Replacement Characters

**Severity: LOW**

10 rows contain `\ufffd` (replacement character), indicating encoding errors in the source data.

### 12. 88 Rows with Tab Characters

**Severity: LOW**

Tab characters embedded in text fields. Minor — handled by standard preprocessing.

### 13. 17,120 Rows Mention Reddit

**Severity: LOW (informational)**

17,120 rows contain Reddit-related markers (`reddit`, `r/`, `/u/`), confirming that at least the suicide detection portion of the data originates from Reddit.

---

## ML-Readiness Concerns

### Data Leakage Risk

53.3% of suicide=1 rows contain explicit suicide keywords. A model could achieve ~53% recall on the positive class by keyword matching alone. The dataset doesn't test nuanced understanding well.

### Dataset Provenance

| Property | Suicide Subset | Toxicity Subset |
|----------|---------------|----------------|
| Row range | 0–232,072 | 232,080–391,628 |
| Count | 116,037 (pos) | 16,225 (pos) |
| Median text length | 653 chars | 127 chars |
| Max text length | 40,297 chars | 5,000 chars |
| Likely source | Reddit (r/depression, r/SuicideWatch) | Wikipedia talk pages / Jigsaw |

The two subsets have dramatically different text length distributions, suggesting different sources and writing styles.

---

## Summary of All Issues

| # | Issue | Severity | Count |
|---|-------|----------|-------|
| 1 | Mutually exclusive labels (no both=1) | CRITICAL | 0 rows with both=1 |
| 2 | #ERROR! corrupted text | HIGH | 262 |
| 3 | Suicide keywords in non-suicide rows | HIGH | 2,228 |
| 4 | Toxic language in non-toxic rows | HIGH | 13,777 |
| 5 | Severe toxicity class imbalance (23:1) | HIGH | 16,225/391,645 |
| 6 | Duplicate rows | MEDIUM | 262 |
| 7 | Embedded newlines in text | MEDIUM | 191,906 |
| 8 | Extreme text lengths | MEDIUM | 3,777 |
| 9 | Trailing whitespace | LOW | 20,833 |
| 10 | HTML entities | LOW | 8,163 |
| 11 | Unicode replacement chars | LOW | 10 |
| 12 | Tab characters | LOW | 88 |
| 13 | Reddit-sourced data | INFO | 17,120 |

## Recommended Actions

1. **Fix the combination:** Re-label rows that could be both toxic AND suicidal — the mutual exclusion is artificial
2. **Remove #ERROR! rows:** Delete all 262 corrupted rows
3. **Audit mislabeled rows:** Review the 2,228 suicide=0 + keyword rows and 13,777 toxicity=0 + profanity rows
4. **Normalize text:** Strip whitespace, decode HTML entities, handle encoding errors
5. **Filter extremes:** Remove rows under 10 chars, cap length at ~2000 chars for training
6. **Consider oversampling:** Address the 23:1 toxicity imbalance
