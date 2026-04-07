# ChatSentry — Online Feature Computation & Batch Training Data Pipeline

**Requirements:**
1. Online feature computation path for real-time inference (integrate-able with open source chat service)
2. Batch pipeline that compiles versioned training/evaluation datasets from "production" data, with candidate selection and data leakage prevention

**Duration target:** 4–6 minutes (sped up where noted)
**Author:** Rishabh Narayan (Data Specialist)

---

## Pre-Recording Checklist

- [ ] SSH into Chameleon VM: `ssh -i ~/.ssh/id_rsa_chameleon cc@129.114.26.207`
- [ ] Verify all Docker containers running: `docker ps`
- [ ] Have FastAPI docs open in browser tab: `http://129.114.26.207:8000/docs`
- [ ] Have Adminer GUI open in browser tab: `http://129.114.26.207:5050`
- [ ] Have Chameleon S3 Horizon GUI open in browser tab: `https://chi.tacc.chameleoncloud.org`
- [ ] Have GE Viewer open in browser tab: `http://129.114.26.207:8080`
- [ ] PostgreSQL has data from previous pipeline runs (messages table populated)

---

## Scene 1: Introduction (15 sec)

**[Screen: Terminal with SSH into Chameleon VM]**

**Narration:**
"This demo covers two components of ChatSentry's data pipeline. First, the online feature computation path — a real-time text preprocessing service that cleans raw chat messages before ML inference. Second, the batch pipeline that compiles versioned training and evaluation datasets from production data, with temporal leakage prevention and stratified splitting."

**Show:**
```bash
# Verify infrastructure is up
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

**Expected output:** 4 containers (postgres, api, adminer, ge-viewer) all "Up"

---

## Scene 2: Online Feature Computation — Architecture Overview (30 sec)

**[Screen: Terminal]**

**Narration:**
"The online feature computation path intercepts every incoming chat message at the API layer. It runs a 5-step text cleaning pipeline before the message reaches ML inference. This same TextCleaner class is shared with the batch path, ensuring identical transformations whether processing one message in real-time or 1.58 million in batch."

**Show the TextCleaner pipeline steps:**

```bash
docker exec api python3 -c "
from src.data.text_cleaner import TextCleaner
tc = TextCleaner()
print('Pipeline steps (in order):')
for i, step in enumerate(tc.steps, 1):
    print(f'  {i}. {step.__name__}: {step.__doc__.split(chr(10))[0]}')
"
```

**Expected output:**
```
Pipeline steps (in order):
  1. fix_unicode: Normalize Unicode text using ftfy (ONLINE-05, D-05 step 1).
  2. strip_markdown: Remove HTML tags and Markdown syntax markers (ONLINE-01).
  3. extract_urls: Replace URLs with [URL] placeholder (ONLINE-03, D-08).
  4. standardize_emojis: Convert Unicode emojis to :shortcode: format (ONLINE-02, D-09).
  5. scrub_pii: Replace personally identifiable information with placeholders (ONLINE-04, D-07).
```

---

## Scene 3: Online Feature Computation — End-to-End Demo (90 sec)

**[Screen: Browser — FastAPI docs at `http://129.114.26.207:8000/docs`]**

**Narration:**
"Let me demonstrate the online path end-to-end. I'll POST a message containing Markdown, a URL, an email, a phone number, and an @mention. The middleware cleans all of it before persisting to PostgreSQL."

**Step 1: Show the API endpoint**

- Navigate to POST `/messages` in Swagger UI
- Click "Try it out"

**Step 2: Send a message with all cleaning targets**

Enter this request body:
```json
{
  "text": "**IMPORTANT** Please contact @admin at admin@company.com or call 555-867-5309. Visit https://internal.wiki.com/policy for details. This is a caf\u00e9 review \ud83d\ude02",
  "user_id": "demo-user-001"
}
```

Click "Execute".

**Expected response:**
```json
{
  "status": "accepted",
  "message_id": "<uuid>",
  "raw_text": "**IMPORTANT** Please contact @admin at admin@company.com or call 555-867-5309. Visit https://internal.wiki.com/policy for details. This is a café review 😂",
  "cleaned_text": "IMPORTANT Please contact [USER] at [EMAIL] or call [PHONE]. Visit [URL] for details. This is a café review :face_with_tears_of_joy:"
}
```

**Narrate the transformation:**
- `**IMPORTANT**` → `IMPORTANT` (Markdown stripped)
- `@admin` → `[USER]` (PII scrubbed)
- `admin@company.com` → `[EMAIL]` (PII scrubbed)
- `555-867-5309` → `[PHONE]` (PII scrubbed)
- `https://internal.wiki.com/policy` → `[URL]` (URL extracted)
- `😂` → `:face_with_tears_of_joy:` (emoji standardized)

**[Switch to terminal — verify in PostgreSQL]**

```bash
docker exec postgres psql -U user -d chatsentry -c "
SELECT left(text, 50) as raw_text, left(cleaned_text, 50) as cleaned_text
FROM messages ORDER BY created_at DESC LIMIT 1;
"
```

**Expected output:** Shows raw text and cleaned_text side by side, confirming persistence.

**[Switch to browser: Adminer GUI]**
- Login: System=PostgreSQL, Server=postgres, Username=user, Password=chatsentry_pg, Database=chatsentry
- Run: `SELECT text, cleaned_text, created_at FROM messages ORDER BY created_at DESC LIMIT 5;`
- Show the raw vs cleaned text columns

**External confirmation:** Message stored in PostgreSQL with both raw and cleaned text.

---

## Scene 4: Online Feature Computation — Integration Test via curl (30 sec)

**[Screen: Terminal]**

**Narration:**
"To prove this is integrate-able with any chat service — not just our demo UI — I'll send messages via curl, simulating how Zulip or any webhook-based chat system would call this endpoint."

**Send 3 messages via curl:**

```bash
# Message 1: Toxic content with PII
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "You are such an **idiot** @john email@x.com https://hate.com go away", "user_id": "test-toxic"}' | python3 -m json.tool

# Message 2: Suicide-related content
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "I feel so **hopeless** nobody cares about me anymore 😢", "user_id": "test-suicide"}' | python3 -m json.tool

# Message 3: Benign content
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"text": "Hey team, the PR for the auth module is ready for review 👍", "user_id": "test-benign"}' | python3 -m json.tool
```

**Show each response with cleaned_text field.**

**Verify all 3 landed in PostgreSQL:**

```bash
docker exec postgres psql -U user -d chatsentry -c "
SELECT left(cleaned_text, 60) as cleaned, is_toxicity, is_suicide
FROM messages ORDER BY created_at DESC LIMIT 3;
"
```

**Tests to narrate:**

| Test | Command | Validates |
|------|---------|-----------|
| TextCleaner unit tests | `docker exec api python3 -m pytest tests/test_text_cleaner.py -v` | All 13 tests: individual steps, pipeline order, edge cases |
| API health | `curl -s http://localhost:8000/health` | Service is running |
| Middleware integration | Show curl responses | TextCleaner applied on every POST |

**Run the tests:**
```bash
docker exec api python3 -m pytest tests/test_text_cleaner.py -v 2>&1 | tail -20
```

**Expected output:** 13 passed — covers fix_unicode, strip_markdown, extract_urls, standardize_emojis, scrub_pii, full pipeline, custom steps, empty input, no side effects.

---

## Scene 5: Batch Pipeline — Launch Compilation (60 sec, partially sped up)

**[Screen: Terminal]**

**Narration:**
"Now the batch pipeline. This compiles versioned training and evaluation datasets from the production messages in PostgreSQL. The key design decisions: temporal leakage prevention ensures only messages created BEFORE the moderation decision are included, and stratified splitting preserves class proportions across train, validation, and test sets."

**Show the incremental query with temporal leakage prevention:**

```bash
docker exec api python3 -c "
from src.data.compile_training_data import INCREMENTAL_QUERY
print(INCREMENTAL_QUERY)
"
```

**Narrate:**
"The INNER JOIN with the moderation table ensures only labeled messages are included. The WHERE clause `created_at < decided_at` prevents temporal leakage — a message can't appear in training data if the moderation decision came first."

**Show current PostgreSQL state:**

```bash
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  (SELECT COUNT(*) FROM messages) as total_messages,
  (SELECT COUNT(*) FROM moderation) as total_moderations,
  (SELECT COUNT(*) FROM messages m INNER JOIN moderation mod ON m.id = mod.message_id WHERE m.created_at < mod.decided_at) as eligible_for_training;
"
```

**Launch the batch compilation (speed up 4x during processing):**

```bash
docker exec api python3 -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
from src.data.compile_training_data import compile_incremental
compile_incremental()
"
```

**While it runs, narrate the steps being executed:**
1. Query PostgreSQL with temporal leakage filter
2. TextCleaner fallback for any NULL cleaned_text
3. Select output columns (cleaned_text, is_suicide, is_toxicity, source, message_id)
4. Great Expectations validation (6 checks)
5. Quality gate (remove #ERROR!, filter <10 chars, cap >5000 chars)
6. Stratified 70/15/15 train/val/test split
7. Upload versioned snapshot to S3

---

## Scene 6: Batch Pipeline — Verify Versioned Output in S3 (45 sec)

**[Screen: Terminal]**

**Narration:**
"The pipeline produces timestamped version folders in S3. Each version contains train, validation, and test CSVs with exactly 5 columns."

**List versioned training data in S3:**

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

**Verify split contents and proportions:**

```bash
docker exec api python3 -c "
from minio import Minio; import os, io, pandas as pd
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for split in ['train', 'val', 'test']:
    objs = list(c.list_objects('proj09_Data', prefix=f'zulip-training-data/v', recursive=True))
    version = [o for o in objs if '/train.csv' in o.object_name][0].object_name.split('/')[1]
    obj = c.get_object('proj09_Data', f'zulip-training-data/{version}/{split}.csv')
    df = pd.read_csv(io.BytesIO(obj.read()))
    obj.close(); obj.release_conn()
    print(f'{split}: {len(df)} rows, columns={list(df.columns)}')
    print(f'  is_suicide distribution: {dict(df.is_suicide.value_counts())}')
    print(f'  is_toxicity distribution: {dict(df.is_toxicity.value_counts())}')
    print()
"
```

**Expected output:** Shows train (~70%), val (~15%), test (~15%) with stratified label distributions.

**[Switch to browser: Chameleon S3 Horizon GUI]**
- Navigate: Object Store → Containers → `proj09_Data`
- Expand `zulip-training-data/` folder
- Show versioned subfolder with `train.csv`, `val.csv`, `test.csv`

**External confirmation:** Versioned training data visible in Chameleon Cloud dashboard.

---

## Scene 7: Batch Pipeline — Data Leakage & Candidate Selection (30 sec)

**[Screen: Terminal]**

**Narration:**
"Let me demonstrate the data leakage prevention and candidate selection logic that justifies which rows enter the training set."

**Show temporal leakage filter in action:**

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

**Expected output:** msg-2 is dropped because its `decided_at` (Jan 1, 08:00) precedes its `created_at` (Jan 3, 10:00).

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
print(f'Removed: corrupt data, short text, capped long text')
"
```

**Tests to narrate:**

```bash
docker exec api python3 -m pytest tests/test_compile_training_data.py -v -k "temporal_leakage or quality_gate or stratified_split" 2>&1 | tail -15
```

**Expected:** Tests for temporal leakage filter, quality gate removal, stratified split proportions all passing.

---

## Scene 8: Batch Pipeline — GE Validation Report (30 sec)

**[Screen: Browser — GE Viewer at `http://129.114.26.207:8080`]**

**Narration:**
"Great Expectations validates every batch compilation output against 6 declarative checks. The HTML report is uploaded to S3 and viewable through our GE Viewer."

**Show the GE Viewer page:**
- Click on the latest report
- Point out each of the 6 expectation results:
  1. Required Column Present (cleaned_text) — PASS
  2. Text Length Within Bounds (10–5000 chars) — PASS/FAIL
  3. No Corrupt Data (#ERROR!) — PASS
  4. Valid Label Values (0 or 1) — PASS
  5. Class Balance Ratio (2–8% toxicity) — PASS/FAIL
  6. No Missing Values (cleaned_text) — PASS

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

## Scene 9: End-to-End Summary (15 sec)

**[Screen: Terminal — final verification]**

**Narration:**
"To summarize: the online path cleans every incoming message in real-time through a 5-step pipeline before inference. The batch path compiles versioned, leakage-free training data from production with Great Expectations validation. Both paths share the same TextCleaner class, ensuring identical transformations."

```bash
# Final state summary
echo "=== PostgreSQL ==="
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  (SELECT COUNT(*) FROM messages) as messages,
  (SELECT COUNT(*) FROM moderation) as moderations,
  (SELECT COUNT(*) FROM messages WHERE cleaned_text IS NOT NULL) as with_cleaned_text;
"

echo "=== S3 Objects ==="
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
objects = list(c.list_objects('proj09_Data', recursive=True))
total_mb = sum(o.size for o in objects) / 1024 / 1024
print(f'Total objects: {len(objects)}, Total size: {total_mb:.1f} MB')
prefixes = set()
for o in objects:
    parts = o.object_name.split('/')
    prefixes.add(parts[0] + '/' + parts[1] if len(parts) > 1 else parts[0])
for p in sorted(prefixes):
    print(f'  {p}/')
"
```

---

## GUI Steps Summary

| Step | GUI | What to show |
|------|-----|-------------|
| 1 | FastAPI docs (`129.114.26.207:8000/docs`) | POST /messages with cleaned_text in response |
| 2 | Adminer (`129.114.26.207:5050`) | PostgreSQL messages table — raw vs cleaned text |
| 3 | Chameleon S3 Horizon (`chi.tacc.chameleoncloud.org`) | `zulip-training-data/v*/{train,val,test}.csv` |
| 4 | GE Viewer (`129.114.26.207:8080`) | HTML data quality report with 6 expectations |

---

## Tests That Verify Requirements

| Requirement | Test / Verification | How to show in video |
|-------------|---------------------|----------------------|
| Online feature computation (real-time) | `test_text_cleaner.py` — 13 tests covering all 5 cleaning steps | Run `pytest tests/test_text_cleaner.py -v` |
| Integrate-able with chat service | `curl POST /messages` returns cleaned_text, stores in PostgreSQL | Show curl responses + Adminer query |
| Same pipeline online & batch | TextCleaner class used in both `main.py` middleware and `compile_training_data.py` | Show code: `from src.data.text_cleaner import TextCleaner` in both files |
| Batch pipeline compiles versioned data | S3 contains `zulip-training-data/vYYYYMMDD-HHMMSS/{train,val,test}.csv` | Show S3 listing |
| Temporal leakage prevention | `filter_temporal_leakage()` drops rows where `created_at >= decided_at` | Show Python demo + `test_compile_training_data.py` |
| Candidate selection (quality gate) | `apply_quality_gate()` removes #ERROR!, short texts, caps long texts | Show Python demo + test output |
| Stratified 70/15/15 split | `stratified_split()` preserves class proportions | Show split size verification |
| GE validation (6 checks) | `data_quality.py` — 6 expectations, HTML report in S3 | Show GE Viewer + S3 listing |
| Versioned snapshots in S3 | `zulip-training-data/v*/{train,val,test}.csv` with UTC timestamp | Show S3 Horizon GUI |
| PostgreSQL has cleaned production data | `messages` table with `cleaned_text` column populated | Show Adminer query |

---

## Video Recording Flow (Summary)

```
Scene 1: Introduction (15s)
    ↓
Scene 2: Architecture Overview (30s)
    ↓
Scene 3: Online Demo — FastAPI docs → POST message → show response → Adminer (90s)
    ↓
Scene 4: Integration Test — curl 3 messages → run TextCleaner tests (30s)
    ↓
Scene 5: Batch Pipeline — launch compilation (60s, speed up 4x)
    ↓
Scene 6: Verify S3 — versioned splits + proportions (45s)
    ↓
Scene 7: Data Leakage + Candidate Selection demo (30s)
    ↓
Scene 8: GE Validation Report — GE Viewer + S3 (30s)
    ↓
Scene 9: Summary (15s)
```

**Total: ~5 minutes**
