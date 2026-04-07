# ChatSentry Data Pipeline — Video Script

**Video 1: Reproducible Data Pipeline — Ingest, Transform, Expand, Serve**
**Duration target:** 3–5 minutes (sped up where noted)

---

## Pre-Recording Checklist

- [ ] SSH into Chameleon VM: `ssh -i ~/.ssh/id_rsa_chameleon cc@129.114.26.207`
- [ ] Verify all Docker containers running: `docker ps`
- [ ] Have Chameleon S3 Horizon GUI open in browser tab: `https://chi.tacc.chameleoncloud.org`
- [ ] Have Adminer GUI open in browser tab: `http://129.114.26.207:5050`
- [ ] Have GE Viewer open in browser tab: `http://129.114.26.207:8080`
- [ ] Have FastAPI docs open in browser tab: `http://129.114.26.207:8000/docs`
- [ ] `combined_dataset.csv` uploaded to VM at `/home/cc/chatsentry/combined_dataset.csv/combined_dataset.csv`

---

## Scene 1: Introduction (15 sec)

**[Screen: Terminal with SSH into Chameleon VM]**

**Narration:**
"This is ChatSentry's reproducible data pipeline. I'll demonstrate how we ingest 1.58M rows of toxic/suicide detection data into Chameleon object storage, clean and transform it, expand it synthetically, and produce versioned training data — all in one pipeline."

**Show:**
```bash
# Verify infrastructure is up
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

**Expected output:** 4 containers (postgres, api, adminer, ge-viewer) all "Up"

---

## Scene 2: Data Ingestion — CSV to Chameleon S3 (45 sec)

**[Screen: Terminal]**

**Narration:**
"Step 1: Ingest the raw 218MB CSV dataset into Chameleon S3. We read it in 50K-row chunks and upload each as a separate CSV to our object storage bucket."

**Commands to run:**

```bash
# Copy CSV into the API container
docker exec api rm -rf /tmp/combined_dataset.csv
docker cp /home/cc/chatsentry/combined_dataset.csv/combined_dataset.csv api:/tmp/combined_dataset.csv

# Verify file is inside container
docker exec api ls -lh /tmp/combined_dataset.csv

# Run ingestion pipeline
docker exec api python3 -m src.data.ingest_and_expand /tmp/combined_dataset.csv
```

**Tests to show (narrate results):**

| Test | Command | Expected |
|------|---------|----------|
| Chunks uploaded | `docker exec api python3 -c "from minio import Minio; import os; c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region=''); objs = list(c.list_objects('proj09_Data', prefix='zulip-raw-messages/real/combined_dataset/', recursive=True)); print(f'{len(objs)} chunks'); [print(f'  {o.object_name} ({o.size/1024/1024:.1f} MB)') for o in objs]"` | 8 chunks, ~33 MB each |

**[Switch to browser: Chameleon S3 Horizon GUI]**
- Navigate: Object Store → Containers → `proj09_Data`
- Show: `zulip-raw-messages/real/combined_dataset/chunk_000.csv` through `chunk_007.csv`

**External confirmation:** Files visible in Chameleon Cloud dashboard.

---

## Scene 3: Text Cleaning & Transformation (60 sec)

**[Screen: Terminal]**

**Narration:**
"Step 2: Run the batch compilation pipeline. This reads CSV chunks from S3, applies our 5-step text cleaning pipeline, loads into PostgreSQL, runs Great Expectations data quality validation, applies the quality gate, does a stratified 70/15/15 train/val/test split, and uploads versioned training data back to S3."

**Commands to run:**

```bash
# Truncate DB for clean initial load
docker exec postgres psql -U user -d chatsentry -c "TRUNCATE messages, flags, moderation, users CASCADE;"

# Run compilation (background, takes ~5-10 min for 391K rows)
docker exec -d api python3 -c "import logging; logging.basicConfig(level=logging.INFO); from src.data.compile_training_data import compile_initial; compile_initial()"

# Monitor progress (run a few times, show log output)
docker logs --tail 20 api
```

**While compilation runs, show the 5 cleaning steps via a quick Python demo:**

```bash
docker exec api python3 -c "
from src.data.text_cleaner import TextCleaner
tc = TextCleaner()
raw = '**Check** this https://example.com @user123 email@test.com 123-456-7890'
print('BEFORE:', raw)
print('AFTER: ', tc.clean(raw))
"
```

**Expected output:**
```
BEFORE: **Check** this https://example.com @user123 email@test.com 123-456-7890
AFTER:  Check this [URL] [USER] [EMAIL] [PHONE]
```

**Tests to show (narrate results):**

| Test | What it validates |
|------|-------------------|
| TextCleaner pipeline | Unicode fix → Markdown strip → URL extract → Emoji standardize → PII scrub |
| Quality gate | Removes `#ERROR!` rows, filters <10 chars, truncates >5000 chars |
| Stratified split | 70/15/15 with stratification on label combination |

**Wait for compilation to finish, then verify:**

```bash
# Check PostgreSQL row count
docker exec postgres psql -U user -d chatsentry -c "SELECT COUNT(*) as total_messages FROM messages;"

# Expected: 391645
```

**[Switch to browser: Adminer GUI]**
- Login: System=PostgreSQL, Server=postgres, Username=user, Password=chatsentry_pg, Database=chatsentry
- Run query: `SELECT text, cleaned_text, is_toxicity, is_suicide FROM messages LIMIT 5;`
- Show: raw text vs cleaned text side by side

**External confirmation:** PostgreSQL contains transformed data with cleaned_text column.

---

## Scene 4: Great Expectations Data Quality Validation (30 sec)

**[Screen: Browser — GE Viewer]**

**Narration:**
"Step 3: Great Expectations validates our training data against 6 declarative checks — column existence, text length bounds, no corrupt data, valid labels, class balance, and no nulls. The HTML report is uploaded to S3."

**Show:** GE Viewer at `http://129.114.26.207:8080`
- Point out each of the 6 expectation results (PASS/FAIL)
- Show summary: "X/Y expectations passed"

**[Switch to terminal — verify report in S3]**

```bash
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for obj in c.list_objects('proj09_Data', prefix='data-quality-report/', recursive=True):
    print(f'{obj.object_name} ({obj.size/1024:.1f} KB)')
"
```

**External confirmation:** GE report visible in both GE Viewer and S3.

---

## Scene 5: Versioned Training Data in S3 (30 sec)

**[Screen: Terminal]**

**Narration:**
"Step 4: The pipeline produces a versioned training data snapshot with train/val/test splits, stored in S3 with a UTC timestamp version tag."

**Commands to run:**

```bash
# List all S3 objects
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for obj in c.list_objects('proj09_Data', recursive=True):
    print(f'{obj.object_name} ({obj.size/1024/1024:.1f} MB)')
"
```

**Expected output includes:**
```
zulip-training-data/vYYYYMMDD-HHMMSS/train.csv (XXX.X MB)
zulip-training-data/vYYYYMMDD-HHMMSS/val.csv (XX.X MB)
zulip-training-data/vYYYYMMDD-HHMMSS/test.csv (XX.X MB)
```

**[Switch to browser: Chameleon S3 Horizon GUI]**
- Navigate: Object Store → Containers → `proj09_Data`
- Expand `zulip-training-data/` folder
- Show versioned subfolder with `train.csv`, `val.csv`, `test.csv`

**External confirmation:** Versioned training data visible in Chameleon Cloud dashboard.

---

## Scene 6: Synthetic Data Expansion (60 sec)

**[Screen: Terminal]**

**Narration:**
"Step 5: Since our dataset is under 5GB, we expand it with synthetic data using a local Qwen2.5-1.5B model. We use few-shot prompting to generate labeled toxic, suicide, and benign messages with a distribution that oversamples minority classes — 30% toxic, 30% suicide, 40% benign."

**Commands to run:**

```bash
# Generate synthetic training data (100 rows for demo speed, normally 10K)
docker exec api python3 -m src.data.synthetic_generator --mode training --count 100

# Verify synthetic data in S3
docker exec api python3 -c "
from minio import Minio; import os, io, pandas as pd
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
obj = c.get_object('proj09_Data', 'zulip-raw-messages/synthetic/synthetic_data.csv')
df = pd.read_csv(io.BytesIO(obj.read()))
obj.close()
print(f'Rows: {len(df)}')
print(df[['is_suicide','is_toxicity']].value_counts())
print()
print(df.head(5).to_string())
"
```

**Show label distribution** — oversamples toxic/suicide classes per lecture best practices.

**External confirmation:** Synthetic CSV in S3 at `zulip-raw-messages/synthetic/synthetic_data.csv`.

---

## Scene 7: Real-Time Processing via API (30 sec)

**[Screen: Browser — FastAPI docs]**

**Narration:**
"Step 6: The same TextCleaner pipeline also runs in real-time. Every message posted to our API gets cleaned before inference — Markdown stripped, URLs extracted, emojis standardized, PII scrubbed."

**Show:** FastAPI docs at `http://129.114.26.207:8000/docs`

**Use the "Try it out" button on POST /messages:**
```json
{
  "text": "**Bold** https://evil.com @admin user@email.com 555-123-4567 I feel terrible",
  "user_id": "demo-user"
}
```

**Show response** with cleaned text.

**[Switch to terminal — verify in PostgreSQL]**

```bash
docker exec postgres psql -U user -d chatsentry -c "SELECT text, cleaned_text FROM messages ORDER BY created_at DESC LIMIT 1;"
```

**External confirmation:** Message stored with both raw and cleaned text.

---

## Scene 8: End-to-End Summary (15 sec)

**[Screen: Terminal — final verification]**

**Narration:**
"Pipeline complete. Let me verify the full state."

```bash
# PostgreSQL count
docker exec postgres psql -U user -d chatsentry -c "SELECT COUNT(*) FROM messages;"

# S3 object summary
docker exec api python3 -c "
from minio import Minio; import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
objects = list(c.list_objects('proj09_Data', recursive=True))
total_mb = sum(o.size for o in objects) / 1024 / 1024
print(f'Total objects: {len(objects)}')
print(f'Total size: {total_mb:.1f} MB')
print(f'Types: raw CSV chunks, synthetic data, training splits, GE reports')
"
```

**[Switch to Chameleon S3 GUI — show bucket contents]**

**Narration:**
"To summarize: raw CSV chunks in S3, synthetic expansion data, cleaned and split training data with version tags, and data quality reports — all in Chameleon object storage, ready for the ML training team."

---

## GUI Steps Summary

| Step | GUI | What to show |
|------|-----|-------------|
| 1 | Chameleon S3 Horizon (`chi.tacc.chameleoncloud.org`) | Object Store → `proj09_Data` → raw CSV chunks |
| 2 | Adminer (`129.114.26.207:5050`) | PostgreSQL `messages` table with `cleaned_text` column |
| 3 | GE Viewer (`129.114.26.207:8080`) | HTML data quality report with 6 expectation results |
| 4 | Chameleon S3 Horizon | `zulip-training-data/v*/train.csv, val.csv, test.csv` |
| 5 | Chameleon S3 Horizon | `zulip-raw-messages/synthetic/synthetic_data.csv` |
| 6 | FastAPI docs (`129.114.26.207:8000/docs`) | POST /messages with real-time text cleaning |

---

## Tests That Verify Requirements

| Requirement | Test / Verification | How to show in video |
|-------------|---------------------|----------------------|
| Ingest external data into S3 | `chunk_000.csv` through `chunk_007.csv` in `proj09_Data` | Show S3 Horizon GUI + CLI listing |
| Execute transformations for training readiness | `cleaned_text` column in PostgreSQL with Markdown/URL/PII removed | Show Adminer query + TextCleaner demo |
| Data < 5GB → synthetic expansion | `synthetic_data.csv` in S3 with 10K rows, oversampled minority classes | Show S3 listing + value_counts output |
| Reproducible pipeline | `docker compose up` + single Python commands run entire pipeline | Show `docker exec` commands executing end-to-end |
| External confirmation | S3 Horizon GUI shows files; Adminer shows DB rows; GE Viewer shows report | Show all 3 GUIs with live data |
| Versioned training data | `zulip-training-data/vYYYYMMDD-HHMMSS/{train,val,test}.csv` | Show S3 bucket with timestamped versions |
