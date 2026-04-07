# ChatSentry — Batch Pipeline: Versioned Training & Evaluation Datasets from Production Data

**Requirement:**
Batch pipeline that compiles versioned training and evaluation datasets from "production" data, with well-justified candidate selection and avoiding data leakage.

**Duration target:** 4–6 minutes (sped up where noted)
**Author:** Rishabh Narayan (Data Specialist)

---

## Pre-Recording Checklist

- [ ] SSH into Chameleon VM: `ssh -i ~/.ssh/id_rsa_chameleon cc@<VM_IP>`
- [ ] Verify all Docker containers running: `docker ps`
- [ ] Have Adminer GUI open in browser tab: `http://<VM_IP>:5050`
- [ ] Have Chameleon S3 Horizon GUI open in browser tab: `https://chi.tacc.chameleoncloud.org`
- [ ] Have GE Viewer open in browser tab: `http://<VM_IP>:8080`
- [ ] PostgreSQL has data from previous pipeline runs (messages + moderation tables populated)

---

## Scene 1: Introduction & Architecture (30 sec)

**[Screen: Terminal with SSH into Chameleon VM]**

**Narration:**
"This demo shows ChatSentry's batch pipeline that compiles versioned training and evaluation datasets from production data. The pipeline addresses three core requirements: candidate selection — only messages that have received a moderation decision enter the training set, temporal leakage prevention — ensuring moderation decisions precede message creation timestamps, and versioned output — each compilation produces a UTC-timestamped snapshot of train, validation, and test CSVs in S3."

**Show infrastructure is running:**

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

**Expected output:** 4 containers (postgres, api, adminer, ge-viewer) all "Up"

---

## Scene 2: Production Data State — Before Pipeline (30 sec)

**[Screen: Terminal]**

**Narration:**
"Before launching the pipeline, let me verify the production state. The PostgreSQL database stores raw messages and moderation decisions. Only messages with a moderation decision — meaning a human or model has reviewed and labeled them — are eligible candidates for training."

**Show current PostgreSQL state:**

```bash
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  (SELECT COUNT(*) FROM messages) as total_messages,
  (SELECT COUNT(*) FROM moderation) as total_moderations,
  (SELECT COUNT(*) FROM messages m INNER JOIN moderation mod ON m.id = mod.message_id WHERE m.created_at < mod.decided_at) as eligible_candidates,
  (SELECT COUNT(*) FROM messages WHERE cleaned_text IS NOT NULL) as with_cleaned_text;
"
```

**Narration:**
"The `eligible_candidates` count shows only messages passing both the INNER JOIN with moderation AND the temporal filter. This is our candidate selection justification."

**[Switch to Browser: Adminer GUI]**
- Login: System=PostgreSQL, Server=postgres, Username=user, Password=chatsentry_pg, Database=chatsentry
- Run query to show sample messages with moderation decisions:
```sql
SELECT m.id, left(m.text, 40) as raw_text, m.is_suicide, m.is_toxicity,
       mod.action, mod.decided_at, m.created_at
FROM messages m
INNER JOIN moderation mod ON m.id = mod.message_id
WHERE m.created_at < mod.decided_at
LIMIT 5;
```

**External confirmation:** Adminer shows raw production data with timestamps and labels.

---

## Scene 3: Data Leakage Prevention — Justification (45 sec)

**[Screen: Terminal]**

**Narration:**
"Data leakage is the critical risk in training pipelines. Temporal leakage occurs if a moderation decision timestamp precedes the message creation timestamp — the model would be trained on information that wasn't available at inference time. Our pipeline prevents this at two levels."

**Show the incremental query:**

```bash
docker exec api python3 -c "
from src.data.compile_training_data import INCREMENTAL_QUERY
print(INCREMENTAL_QUERY)
"
```

**Narration:**
"The SQL WHERE clause enforces `created_at < decided_at`. A message can only appear in training data if the moderation decision was made AFTER the message was created. This is the first layer of defense."

**Show defense-in-depth Python filter:**

```bash
docker exec api python3 -c "
import pandas as pd
from src.data.compile_training_data import filter_temporal_leakage

# Simulate: 3 messages, one with decision BEFORE creation (leaked)
df = pd.DataFrame({
    'message_id': ['msg-1', 'msg-2', 'msg-3'],
    'cleaned_text': ['valid message 1', 'leaked message', 'valid message 2'],
    'created_at': pd.to_datetime(['2026-01-01T10:00:00Z', '2026-01-03T10:00:00Z', '2026-01-02T10:00:00Z']),
    'decided_at': pd.to_datetime(['2026-01-01T12:00:00Z', '2026-01-01T08:00:00Z', '2026-01-02T12:00:00Z']),
})
print('BEFORE filter:')
print(df[['message_id', 'created_at', 'decided_at']])
print()
result = filter_temporal_leakage(df)
print('AFTER filter (created_at < decided_at only):')
print(result[['message_id', 'created_at', 'decided_at']])
print(f'\nDropped {len(df) - len(result)} leaked row(s)')
"
```

**Expected output:** msg-2 is dropped because its `decided_at` precedes `created_at`.

**Run unit tests for leakage prevention:**

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v -k "temporal_leakage" 2>&1 | tail -10
```

**Expected:** Tests pass — temporal leakage filter correctly drops invalid rows.

---

## Scene 4: Candidate Selection — Quality Gate (30 sec)

**[Screen: Terminal]**

**Narration:**
"Candidate selection is justified by two filters. First, the INNER JOIN with moderation — only labeled messages enter. Second, the quality gate — removes corrupt data, noise, and outliers from the candidate pool."

**Show quality gate filtering:**

```bash
docker exec api python3 -c "
import pandas as pd
from src.data.compile_training_data import apply_quality_gate

df = pd.DataFrame({
    'cleaned_text': [
        '#ERROR! corrupt data',
        'short',
        'This is a valid and sufficiently long message for training',
        'x' * 6000,
    ]
})
result = apply_quality_gate(df)
print(f'Input rows: {len(df)}')
print(f'Output rows: {len(result)}')
print(f'Removed: 1 corrupt (#ERROR!), 1 too short (<10 chars), 1 too long (>5000 chars)')
"
```

**Run quality gate tests:**

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v -k "quality_gate" 2>&1 | tail -10
```

**Expected:** Tests pass — quality gate correctly filters corrupt, short, and long texts.

---

## Scene 5: Launch Batch Compilation (90 sec, speed up 4x during processing)

**[Screen: Terminal]**

**Narration:**
"Now I launch the batch pipeline. It will query PostgreSQL with temporal leakage prevention, apply the quality gate, run Great Expectations validation with 6 checks, perform a stratified 70/15/15 train/val/test split, and upload a versioned snapshot to S3."

**Launch the compilation:**

```bash
docker exec api python3 -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
from src.data.compile_training_data import compile_incremental
compile_incremental()
"
```

**While it runs (speed up 4x), narrate each step:**
1. Query PostgreSQL — INNER JOIN with moderation, WHERE created_at < decided_at
2. Defense-in-depth temporal leakage filter in Python
3. TextCleaner fallback for any NULL cleaned_text
4. Select output columns: cleaned_text, is_suicide, is_toxicity, source, message_id
5. Great Expectations validation — 6 declarative checks
6. Quality gate — remove #ERROR!, filter <10 chars, cap >5000 chars
7. Stratified 70/15/15 split on combined label (is_suicide + is_toxicity)
8. Upload versioned snapshot to S3

**Expected output:** Logs showing each step completing, ending with S3 upload confirmation.

---

## Scene 6: Verify Versioned Output in S3 — Terminal (45 sec)

**[Screen: Terminal]**

**Narration:**
"The pipeline produces timestamped version folders in S3. Each version contains train, validation, and test CSVs with exactly 5 columns. Let me verify the output."

**List versioned training data:**

```bash
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
print('=== Versioned Training Data ===')
for obj in sorted(c.list_objects('proj09_Data', prefix='zulip-training-data/', recursive=True), key=lambda o: o.object_name):
    print(f'  {obj.object_name} ({obj.size/1024:.1f} KB)')
"
```

**Expected output:**
```
=== Versioned Training Data ===
  zulip-training-data/vYYYYMMDD-HHMMSS/train.csv (XXX.X KB)
  zulip-training-data/vYYYYMMDD-HHMMSS/val.csv (XX.X KB)
  zulip-training-data/vYYYYMMDD-HHMMSS/test.csv (XX.X KB)
```

**Verify split proportions and stratification:**

```bash
docker exec api python3 -c "
from minio import Minio; import os, io, pandas as pd
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
objs = list(c.list_objects('proj09_Data', prefix='zulip-training-data/v', recursive=True))
version = [o for o in objs if '/train.csv' in o.object_name][0].object_name.split('/')[1]
for split in ['train', 'val', 'test']:
    obj = c.get_object('proj09_Data', f'zulip-training-data/{version}/{split}.csv')
    df = pd.read_csv(io.BytesIO(obj.read()))
    obj.close(); obj.release_conn()
    total = len(df)
    print(f'{split}: {total} rows, columns={list(df.columns)}')
    print(f'  is_suicide distribution: {dict(df.is_suicide.value_counts())}')
    print(f'  is_toxicity distribution: {dict(df.is_toxicity.value_counts())}')
    print()
"
```

**Expected output:** Shows train (~70%), val (~15%), test (~15%) with stratified label distributions.

**Run stratified split tests:**

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v -k "stratified_split" 2>&1 | tail -10
```

---

## Scene 7: External Confirmation — S3 Horizon GUI (30 sec)

**[Screen: Browser — Chameleon S3 Horizon at `https://chi.tacc.chameleoncloud.org`]**

**Narration:**
"External confirmation: the versioned training data is visible in the Chameleon Cloud dashboard, proving the pipeline wrote to external storage."

**Steps to show:**
1. Navigate: Object Store → Containers → `proj09_Data`
2. Expand `zulip-training-data/` folder
3. Show versioned subfolder `vYYYYMMDD-HHMMSS/`
4. Click into each CSV to show metadata (size, last modified)

**External confirmation:** Versioned training data visible in Chameleon Cloud dashboard.

---

## Scene 8: External Confirmation — GE Validation Report (30 sec)

**[Screen: Browser — GE Viewer at `http://<VM_IP>:8080`]**

**Narration:**
"Great Expectations validates every compilation output against 6 declarative quality checks. The HTML report confirms data integrity before the ML team consumes it."

**Show the GE Viewer page:**
- Click on the latest report
- Point out each of the 6 expectation results:
  1. Required Column Present (`cleaned_text`) — PASS
  2. Text Length Within Bounds (10–5000 chars) — PASS
  3. No Corrupt Data (`#ERROR!`) — PASS
  4. Valid Label Values (`is_suicide` in {0,1}) — PASS
  5. Class Balance Ratio (`is_toxicity` mean 2–8%) — PASS
  6. No Missing Values (`cleaned_text` not null) — PASS

**[Switch to terminal — verify report in S3]**

```bash
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for obj in c.list_objects('proj09_Data', prefix='data-quality-report/', recursive=True):
    print(f'{obj.object_name} ({obj.size/1024:.1f} KB)')
"
```

**External confirmation:** GE report visible in both GE Viewer (port 8080) and S3 bucket.

---

## Scene 9: Run All Batch Pipeline Tests (30 sec)

**[Screen: Terminal]**

**Narration:**
"Finally, let me run the full test suite for the batch pipeline to confirm everything passes."

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v 2>&1 | tail -20
```

**Expected output:** 12 passed — covers temporal leakage, quality gate, stratified split, output schema, version format, GE validation, and more.

**Run E2E pipeline tests if available:**

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py tests/test_data_quality.py -v 2>&1 | tail -20
```

**Expected:** All tests pass.

---

## Scene 10: End-to-End Summary (15 sec)

**[Screen: Terminal — final verification]**

**Narration:**
"To summarize: the batch pipeline compiles versioned training and evaluation datasets from production PostgreSQL data. Candidate selection is justified by the INNER JOIN with moderation and the quality gate. Temporal leakage is prevented at both the SQL and Python level. Each compilation produces a UTC-timestamped snapshot in S3, validated by Great Expectations."

```bash
echo "=== PostgreSQL ==="
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  (SELECT COUNT(*) FROM messages) as messages,
  (SELECT COUNT(*) FROM moderation) as moderations,
  (SELECT COUNT(*) FROM messages m INNER JOIN moderation mod ON m.id = mod.message_id WHERE m.created_at < mod.decided_at) as eligible_candidates;
"

echo "=== S3 Versioned Training Data ==="
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
objects = list(c.list_objects('proj09_Data', prefix='zulip-training-data/', recursive=True))
total_kb = sum(o.size for o in objects) / 1024
print(f'Versioned splits: {len(objects)} files, Total size: {total_kb:.1f} KB')
for o in sorted(objects, key=lambda x: x.object_name):
    print(f'  {o.object_name}')
"
```

---

## GUI Steps Summary

| Step | GUI | What to show |
|------|-----|-------------|
| 1 | Adminer (`<VM_IP>:5050`) | Production messages + moderation decisions with timestamps |
| 2 | Chameleon S3 Horizon (`chi.tacc.chameleoncloud.org`) | `zulip-training-data/v*/{train,val,test}.csv` versioned folders |
| 3 | GE Viewer (`<VM_IP>:8080`) | HTML data quality report with 6 expectation results |

---

## Tests That Verify Requirements

| Requirement | Test / Verification | How to show in video |
|-------------|---------------------|----------------------|
| Versioned training/evaluation datasets | S3 contains `zulip-training-data/vYYYYMMDD-HHMMSS/{train,val,test}.csv` | Show S3 listing + Horizon GUI |
| Candidate selection (well-justified) | INNER JOIN with moderation table — only labeled messages enter | Show SQL query + candidate count |
| Quality gate filtering | `apply_quality_gate()` removes #ERROR!, short, long texts | Show Python demo + `test_compile_training_data.py -k quality_gate` |
| Temporal leakage prevention (SQL) | `WHERE created_at < decided_at` in INCREMENTAL_QUERY | Show SQL query |
| Temporal leakage prevention (Python) | `filter_temporal_leakage()` defense-in-depth | Show Python demo + `test_compile_training_data.py -k temporal_leakage` |
| Stratified 70/15/15 split | `stratified_split()` preserves class proportions | Show split verification + `test_compile_training_data.py -k stratified_split` |
| GE validation (6 checks) | `data_quality.py` — HTML report in S3 | Show GE Viewer + S3 listing |
| Pipeline launch to external confirmation | Full pipeline run → S3 + GE Viewer + Adminer | Show end-to-end flow |
| Unit tests pass | `test_compile_training_data.py` — 12 tests | Run `pytest` in terminal |

---

## Video Recording Flow (Summary)

```
Scene 1: Introduction & Architecture (30s)
    ↓
Scene 2: Production Data State — Before Pipeline (30s)
    ↓
Scene 3: Data Leakage Prevention — Justification (45s)
    ↓
Scene 4: Candidate Selection — Quality Gate (30s)
    ↓
Scene 5: Launch Batch Compilation (90s, speed up 4x)
    ↓
Scene 6: Verify Versioned Output in S3 — Terminal (45s)
    ↓
Scene 7: External Confirmation — S3 Horizon GUI (30s)
    ↓
Scene 8: External Confirmation — GE Validation Report (30s)
    ↓
Scene 9: Run All Batch Pipeline Tests (30s)
    ↓
Scene 10: End-to-End Summary (15s)
```

**Total: ~5.5 minutes**
