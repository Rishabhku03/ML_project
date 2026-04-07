# ChatSentry — Bonus: Great Expectations Data Quality Framework Integration

**Requirement:**
Integrate a data framework not used in the lab assignments, that substantially improves your data design. Justify why it improves your design with a concrete example realistic in the context of your proposed service.

**Framework chosen:** Great Expectations (GE) — declarative data quality validation
**Duration target:** 4-6 minutes
**Author:** Rishabh Narayan (Data Specialist)

---

## Pre-Recording Checklist

- [ ] SSH into Chameleon VM: `ssh -i ~/.ssh/id_rsa_chameleon cc@<VM_IP>`
- [ ] Verify all Docker containers running: `docker ps`
- [ ] Have Adminer GUI open in browser tab: `http://<VM_IP>:5050`
- [ ] Have GE Viewer / Data Docs open in browser tab: `http://<VM_IP>:8080`
- [ ] Have terminal ready with working directory at project root
- [ ] Ensure PostgreSQL has data from previous pipeline runs

---

## Scene 1: Introduction & Problem Statement (45 sec)

**[Screen: Terminal with SSH into Chameleon VM]**

**Narration:**
"Before integrating Great Expectations, ChatSentry's data quality relied on a hand-coded `apply_quality_gate()` function — a series of if-else statements that filter corrupt data, short texts, and outlier lengths. This approach has three critical weaknesses for an ML production system:

1. **No declarative specification** — quality rules are buried in imperative code, invisible to non-engineers
2. **No per-check reporting** — a single function returns a filtered DataFrame with no audit trail of which checks failed
3. **No threshold configuration** — changing a text length limit requires editing code and redeploying

Great Expectations solves all three by replacing imperative filtering with declarative Expectation Suites — named, versioned, and independently reportable quality checks."

**Show the old approach:**

```bash
docker exec api python3 -c "
import inspect
from src.data.compile_training_data import apply_quality_gate
print(inspect.getsource(apply_quality_gate))
"
```

**Narration:**
"This is our old quality gate — imperative if-else statements. Now let me show how Great Expectations replaces this with a declarative, auditable, and configurable framework."

---

## Scene 2: GE Expectation Suite — Declarative Quality Checks (60 sec)

**[Screen: Terminal]**

**Narration:**
"Great Expectations uses Expectation Suites — declarative contracts that describe what valid data looks like. Our suite defines 6 expectations for training data quality."

**Show the expectation suite:**

```bash
docker exec api python3 -c "
from src.data.data_quality import build_expectation_suite, DEFAULT_THRESHOLDS
import great_expectations as gx

context = gx.get_context(mode='ephemeral')
suite = build_expectation_suite(context)

print('=== Expectation Suite: training_data_quality ===')
print(f'Total expectations: {len(suite.expectations)}')
print()
for i, exp in enumerate(suite.expectations, 1):
    exp_type = exp.type.replace('expect_', '').replace('_', ' ').title()
    col = exp.kwargs.get('column', 'N/A')
    print(f'{i}. {exp_type} on column \"{col}\"')
print()
print('=== Default Thresholds ===')
for k, v in DEFAULT_THRESHOLDS.items():
    print(f'  {k}: {v}')
"
```

**Expected output:**
```
=== Expectation Suite: training_data_quality ===
Total expectations: 6

1. Column To Exist on column "cleaned_text"
2. Column Value Lengths To Be Between on column "cleaned_text"
3. Column Values To Not Match Regex on column "cleaned_text"
4. Column Values To Be In Set on column "is_suicide"
5. Column Mean To Be Between on column "is_toxicity"
6. Column Values To Not Be Null on column "cleaned_text"

=== Default Thresholds ===
  min_text_length: 10
  max_text_length: 5000
  error_pattern: #ERROR!
  min_toxicity_ratio: 0.02
  max_toxicity_ratio: 0.08
```

**Narration:**
"Each expectation is a named, self-documenting check. The suite is built programmatically but could also be loaded from YAML — making quality rules visible to data scientists and product managers, not just engineers."

---

## Scene 3: Concrete Example — Validating Training Data (60 sec)

**[Screen: Terminal]**

**Narration:**
"Let me demonstrate GE catching real data quality issues. I'll create a DataFrame with three problem rows — a corrupt `#ERROR!` value, a too-short message, and an invalid label value — and show GE detecting each one independently."

**Run the validation demo:**

```bash
docker exec api python3 -c "
import pandas as pd
from src.data.data_quality import validate_training_data

# Simulated training data with 3 intentional quality issues
df = pd.DataFrame({
    'cleaned_text': [
        'I feel so sad and hopeless today',
        '#ERROR! corrupt data here',
        'Hi',
        'This is a perfectly valid training message',
        'Another normal message for the dataset',
        'You are such a terrible person',
        'Great work on the assignment today',
        'I want to end everything right now',
    ],
    'is_suicide': [1, 0, 0, 0, 0, 0, 0, 1],
    'is_toxicity': [0, 0, 0, 0, 0, 1, 0, 0],
    'source': ['real'] * 8,
})

print('=== Input: 8 rows with 3 quality issues ===')
print()

success, results = validate_training_data(df)

print(f'Overall validation: {\"PASSED\" if success else \"FAILED\"}')
print(f'Expectations evaluated: {results[\"statistics\"][\"evaluated_expectations\"]}')
print(f'Expectations passed: {results[\"statistics\"][\"successful_expectations\"]}')
print(f'Expectations failed: {results[\"statistics\"][\"evaluated_expectations\"] - results[\"statistics\"][\"successful_expectations\"]}')
print()

print('=== Per-Expectation Results ===')
for r in results['expectation_results']:
    config = r.expectation_config
    status = 'PASS' if r.success else 'FAIL'
    col = config.kwargs.get('column', '')
    exp_type = config.type.replace('expect_', '').replace('_', ' ').title()
    detail = ''
    if not r.success:
        unexpected = r.result.get('unexpected_percent', '')
        if isinstance(unexpected, (int, float)):
            detail = f' ({unexpected:.1f}% unexpected)'
    print(f'  [{status}] {exp_type} on \"{col}\"{detail}')
"
```

**Expected output:**
```
=== Input: 8 rows with 3 quality issues ===

Overall validation: FAILED
Expectations evaluated: 6
Expectations passed: 3
Expectations failed: 3

=== Per-Expectation Results ===
  [PASS] Column To Exist on "cleaned_text"
  [FAIL] Column Value Lengths To Be Between on "cleaned_text" (12.5% unexpected)
  [FAIL] Column Values To Not Match Regex on "cleaned_text" (12.5% unexpected)
  [PASS] Column Values To Be In Set on "is_suicide"
  [PASS] Column Mean To Be Between on "is_toxicity"
  [FAIL] Column Values To Not Be Null on "cleaned_text"
```

**Narration:**
"Notice how GE reports exactly which expectations failed and what percentage of rows violated each one. The old `apply_quality_gate()` function silently drops rows — GE gives us a diagnostic report. This is critical for an ML system where data quality directly impacts model performance."

---

## Scene 4: Configurable Thresholds — No Code Changes (45 sec)

**[Screen: Terminal]**

**Narration:**
"One key advantage over the hand-coded approach is threshold configurability. The ML team can adjust quality thresholds without touching pipeline code."

**Run threshold override demo:**

```bash
docker exec api python3 -c "
import pandas as pd
from src.data.data_quality import validate_training_data

df = pd.DataFrame({
    'cleaned_text': ['Short msg', 'Normal length message here', 'Another valid text'],
    'is_suicide': [0, 0, 0],
    'is_toxicity': [0, 0, 0],
    'source': ['real'] * 3,
})

print('=== Default thresholds (min_text_length=10) ===')
success_default, _ = validate_training_data(df)
print(f'  Result: {\"PASSED\" if success_default else \"FAILED\"}')
print()

print('=== Relaxed thresholds (min_text_length=5) ===')
success_relaxed, _ = validate_training_data(
    df, thresholds={'min_text_length': 5}
)
print(f'  Result: {\"PASSED\" if success_relaxed else \"FAILED\"}')
print()

print('Same data, different thresholds — no code change required.')
"
```

**Expected output:**
```
=== Default thresholds (min_text_length=10) ===
  Result: FAILED

=== Relaxed thresholds (min_text_length=5) ===
  Result: PASSED

Same data, different thresholds — no code change required.
```

**Narration:**
"The same 3-row DataFrame fails with default thresholds but passes with relaxed thresholds. In the old code, changing this limit meant editing `apply_quality_gate()` and redeploying. With GE, it's a parameter change — configurable per environment, per dataset, or per model version."

---

## Scene 5: Integration in Batch Pipeline (45 sec)

**[Screen: Terminal]**

**Narration:**
"GE is integrated into the batch training data compilation pipeline. After querying PostgreSQL and before the stratified split, GE validates the candidate data and generates an HTML report uploaded to S3."

**Show the integration point:**

```bash
docker exec api python3 -c "
from src.data.compile_training_data import compile_incremental
import inspect

source = inspect.getsource(compile_incremental)
# Show just the GE validation section
lines = source.split('\n')
for i, line in enumerate(lines):
    if 'validate_training_data' in line or 'upload_data_docs' in line or 'GE validation' in line:
        start = max(0, i-2)
        end = min(len(lines), i+3)
        for j in range(start, end):
            print(f'{j+1:4d} | {lines[j]}')
        print()
"
```

**Show pipeline flow:**

```bash
docker exec api python3 -c "
print('=== Batch Pipeline Steps ===')
print('1. Query PostgreSQL (INNER JOIN moderation, temporal filter)')
print('2. Defense-in-depth temporal leakage filter')
print('3. TextCleaner fallback for NULL cleaned_text')
print('4. Select output columns (5 columns)')
print('5. >>> Great Expectations validation (6 checks) <<<  <-- NEW')
print('6. Quality gate (filter issues found by GE)')
print('7. Stratified 70/15/15 train/val/test split')
print('8. Upload versioned snapshot to S3')
print()
print('GE runs BEFORE the quality gate, providing diagnostic')
print('report. The quality gate still filters, but now we know')
print('WHAT was filtered and WHY.')
"
```

---

## Scene 6: Data Docs — HTML Report in S3 (45 sec)

**[Screen: Browser — GE Viewer at `http://<VM_IP>:8080`]**

**Narration:**
"Every pipeline run generates an HTML Data Docs report uploaded to S3. This report provides an auditable record of data quality at each compilation."

**Steps to show:**
1. Open GE Viewer in browser (`http://<VM_IP>:8080`)
2. Click on the latest report
3. Point out each of the 6 expectation results with PASS/FAIL status
4. Show the summary: total expectations evaluated, passed, failed

**[Switch to Terminal — verify report in S3]**

```bash
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'],
          os.environ['MINIO_SECRET_KEY'], secure=True, region='')
print('=== Data Quality Reports in S3 ===')
for obj in c.list_objects('proj09_Data', prefix='data-quality-report/', recursive=True):
    print(f'  {obj.object_name} ({obj.size/1024:.1f} KB)')
"
```

**Expected output:**
```
=== Data Quality Reports in S3 ===
  data-quality-report/report-20260407-012345.html (2.3 KB)
```

**Narration:**
"The HTML report is stored alongside the versioned training data. The ML team can review it before consuming a training snapshot — creating an auditable data quality trail."

---

## Scene 7: Run the Test Suite (45 sec)

**[Screen: Terminal]**

**Narration:**
"Let me run the full test suite for the GE integration to verify all 15 tests pass."

```bash
docker exec api python3 -m pytest tests/test_data_quality.py -v 2>&1
```

**Expected output:** 15 passed covering:
- Suite construction (6 expectations, custom thresholds)
- Clean data validation (all pass)
- Violation detection (error pattern, short text, long text, invalid label, class balance skew, nulls)
- Warn-and-continue behavior (no exceptions on failure)
- Data Docs generation (HTML report with pass/fail)
- Edge cases (empty DataFrame, runtime threshold overrides)

**Narration:**
"15 tests verify every aspect of the GE integration — from suite construction to violation detection to threshold configurability. Each test corresponds to a specific quality guarantee the ML team depends on."

---

## Scene 8: Justification — Why GE Over Hand-Coded Checks (45 sec)

**[Screen: Terminal]**

**Narration:**
"To summarize why Great Expectations substantially improves our data design compared to the hand-coded quality gate:"

```bash
docker exec api python3 -c "
print('=== Great Expectations vs. Hand-Coded Quality Gate ===')
print()
print('Feature              | Hand-Coded           | Great Expectations')
print('---------------------|----------------------|---------------------------')
print('Quality rules        | Hidden in if-else    | Declarative suite')
print('Per-check reporting  | Silent filtering     | Per-expectation PASS/FAIL')
print('Threshold config     | Edit code + redeploy | Parameter at runtime')
print('Audit trail          | None                 | HTML reports in S3')
print('ML team visibility   | Requires reading code| Readable Data Docs')
print('Testability          | One monolithic func  | 15 targeted unit tests')
print('Reusability          | Copy-paste           | Suite import/share')
print()
print('Concrete example in ChatSentry context:')
print('The ML team retrains hateBERT every 200 verified flags.')
print('Before GE: pipeline silently drops rows, ML team has no')
print('idea what was removed or why.')
print('After GE: each retraining snapshot has an HTML report')
print('showing exactly which quality checks passed/failed and')
print('what percentage of rows violated each rule.')
print()
print('This is the difference between blind filtering and')
print('auditable data quality governance.')
"
```

**[Switch to Browser — show Data Docs alongside training data in S3]**

**External confirmation:** Data Docs report visible at `http://<VM_IP>:8080` alongside versioned training data in S3.

---

## Scene 9: End-to-End Summary (15 sec)

**[Screen: Terminal]**

**Narration:**
"To summarize: Great Expectations replaces our hand-coded quality gate with a declarative, configurable, and auditable framework. Every batch compilation produces a Data Docs report alongside the versioned training data. The ML team can verify data quality before consuming any training snapshot."

```bash
echo "=== ChatSentry GE Integration Summary ==="
echo "Framework: Great Expectations (declarative data quality)"
echo "Expectation Suite: 6 checks (column existence, text length, error pattern, label validity, class balance, null check)"
echo "Integration point: Batch pipeline Step 5 (before quality gate)"
echo "Output: HTML Data Docs uploaded to S3 alongside training data"
echo "Tests: 15 unit tests in test_data_quality.py"
echo "Configurability: Runtime threshold overrides without code changes"
```

---

## GUI Steps Summary

| Step | GUI | What to show |
|------|-----|-------------|
| 1 | Browser — GE Viewer (`<VM_IP>:8080`) | HTML Data Docs report with 6 expectation results |
| 2 | Browser — Adminer (`<VM_IP>:5050`) | Production data that feeds into GE validation |
| 3 | Browser — S3 Horizon (`chi.tacc.chameleoncloud.org`) | Data quality reports alongside versioned training data |

---

## Tests That Verify Requirements

| Requirement | Test / Verification | How to show in video |
|-------------|---------------------|----------------------|
| Declarative quality framework | `build_expectation_suite()` creates suite with 6 expectations | Show suite construction + output |
| Replaces hand-coded checks | GE runs before `apply_quality_gate()` in pipeline | Show pipeline flow diagram |
| Per-check reporting | `validate_training_data()` returns per-expectation PASS/FAIL | Show validation demo with 3 failures |
| Configurable thresholds | `thresholds={}` parameter overrides defaults | Show threshold override demo |
| Audit trail | HTML Data Docs uploaded to S3 | Show S3 listing + GE Viewer |
| Integration in pipeline | `compile_incremental()` calls GE before quality gate | Show pipeline source code |
| Test coverage | 15 tests in `test_data_quality.py` | Run `pytest` in terminal |
| Warn-and-continue (D-03) | Validation failures log warnings, don't raise exceptions | Show validation with failures returning normally |

---

## Video Recording Flow (Summary)

```
Scene 1: Introduction & Problem Statement (45s)
    ↓
Scene 2: GE Expectation Suite — Declarative Quality Checks (60s)
    ↓
Scene 3: Concrete Example — Validating Training Data (60s)
    ↓
Scene 4: Configurable Thresholds — No Code Changes (45s)
    ↓
Scene 5: Integration in Batch Pipeline (45s)
    ↓
Scene 6: Data Docs — HTML Report in S3 (45s)
    ↓
Scene 7: Run the Test Suite (45s)
    ↓
Scene 8: Justification — Why GE Over Hand-Coded Checks (45s)
    ↓
Scene 9: End-to-End Summary (15s)
```

**Total: ~6 minutes**
