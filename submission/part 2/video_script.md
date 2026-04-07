# ChatSentry — Data Generator Demo Video Script

**Requirement:** Data generator that hits the (hypothetical) service endpoints with real or synthetic data (following best practices for synthetic data generation).
**Duration target:** 3–5 minutes (sped up where noted)
**Author:** Rishabh Narayan (Data Specialist)

---

## Pre-Recording Checklist

- [ ] SSH into Chameleon VM: `ssh -i ~/.ssh/id_rsa_chameleon cc@129.114.26.207`
- [ ] Verify all Docker containers running: `docker ps`
- [ ] Have FastAPI docs open in browser tab: `http://129.114.26.207:8000/docs`
- [ ] Have Chameleon S3 Horizon GUI open in browser tab: `https://chi.tacc.chameleoncloud.org`
- [ ] Have Adminer GUI open in browser tab: `http://129.114.26.207:5050`

---

## Scene 1: Introduction (15 sec)

**[Screen: Terminal with SSH into Chameleon VM]**

**Narration:**
"This demo shows ChatSentry's synthetic data generator. It uses a local Qwen2.5-1.5B language model with few-shot prompting to generate labeled toxic, suicide, and benign chat messages. The generator hits our FastAPI service endpoints in real-time, simulating realistic Zulip user traffic."

**Show:**
```bash
# Verify infrastructure is up
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

**Expected output:** 4 containers (postgres, api, adminer, ge-viewer) all "Up"

---

## Scene 2: Synthetic Data Generation Best Practices (45 sec)

**[Screen: Terminal]**

**Narration:**
"Before running the generator, let me show the design decisions that follow lecture best practices for synthetic data generation."

**Show the prompt templates:**

```bash
docker exec api python3 -c "
from src.data.prompts import PROMPTS_BY_LABEL, LABEL_DISTRIBUTION
print('=== Label Distribution (oversamples minority classes) ===')
for label, prop in LABEL_DISTRIBUTION.items():
    print(f'  {label}: {prop*100:.0f}%')
print()
print('=== Prompt Design ===')
for label, prompt_obj in PROMPTS_BY_LABEL.items():
    print(f'--- {label.upper()} (is_suicide={prompt_obj.is_suicide}, is_toxicity={prompt_obj.is_toxicity}) ---')
    print(prompt_obj.prompt[:200] + '...')
    print()
"
```

**Key best practices to narrate:**

| Practice | Implementation |
|----------|---------------|
| **Few-shot prompting** | Each prompt includes 3 real dataset examples to ground generation |
| **Label distribution rebalancing** | Oversamples minority classes: toxic 30%, suicide 30%, benign 40% (vs. original ~2% toxic, ~22% suicide) |
| **Prompt-guided labeling** | Labels assigned from prompt instruction, not post-hoc classification (per D-13) |
| **Source tracking** | All synthetic rows tagged `source='synthetic_local'` for provenance |
| **Local model** | Qwen2.5-1.5B runs on CPU — no GPU or external API needed |

**Tests to narrate:**

```bash
# Run synthetic generator tests
docker exec api python3 -m pytest tests/test_synthetic_gen.py -v 2>&1 | head -30
```

**Expected output:** 8 tests passing — covers label flags, distribution sums to 1.0, minority class oversampling, text parsing, target total range.

---

## Scene 3: Training Mode — Generate Labeled CSV (30 sec)

**[Screen: Terminal]**

**Narration:**
"The generator has two modes. Training mode produces a labeled CSV uploaded directly to S3. For this demo I'll generate 100 rows — in production it generates 10,000."

**Commands to run:**

```bash
# Generate 100 synthetic training rows (speed up this part)
docker exec api python3 -m src.data.synthetic_generator --mode training --count 100
```

**While it runs (speed up 4x), then verify:**

```bash
# Verify synthetic data in S3
docker exec api python3 -c "
from minio import Minio; import os, io, pandas as pd
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
obj = c.get_object('proj09_Data', 'zulip-raw-messages/synthetic/synthetic_data.csv')
df = pd.read_csv(io.BytesIO(obj.read()))
obj.close()
print(f'Total rows: {len(df)}')
print(f'Columns: {list(df.columns)}')
print()
print('Label distribution:')
print(df[['is_suicide','is_toxicity']].value_counts())
print()
print('Sample rows:')
print(df.head(5).to_string())
"
```

**Expected output:**
- 100 rows with columns: `text`, `is_suicide`, `is_toxicity`
- Label distribution showing oversampled minority classes
- Sample rows with realistic chat messages

**[Switch to browser: Chameleon S3 Horizon GUI]**
- Navigate: Object Store → Containers → `proj09_Data`
- Show: `zulip-raw-messages/synthetic/synthetic_data.csv`

---

## Scene 4: Test Mode — Hitting Service Endpoints (90 sec, sped up)

**[Screen: Terminal]**

**Narration:**
"Now the main demo: test mode generates synthetic messages and POSTs them to our FastAPI endpoint in real-time. This simulates realistic Zulip user traffic hitting the moderation service."

**Show the API endpoint being targeted:**

```bash
# Verify API is healthy
curl -s http://localhost:8000/health | python3 -m json.tool

# Show API docs endpoint
curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  {m.upper()} {p}') for p,methods in d['paths'].items() for m in methods]"
```

**Expected output:**
```json
{"status": "ok"}
```
And endpoint list: `GET /`, `GET /health`, `POST /messages`, `POST /flags`, `POST /admin/flush`, `GET /dashboard`

**Run the data generator hitting endpoints (20 messages, 2s apart — speed up video 4x):**

```bash
docker exec api python3 -m src.data.synthetic_generator \
  --mode test \
  --count 20 \
  --interval 2 \
  --api-url http://localhost:8000/messages
```

**While it runs, show in parallel:**

**[Split screen or alternate between]**

1. **Terminal output** — shows each generated message and API response:
   ```
   [1/20] toxic: "You're such a pathetic loser..."
   API response: {"message_id": "abc-123", "cleaned_text": "You're such a pathetic loser...", "action": "pass"}
   [2/20] benign: "Has anyone reviewed the PR for the auth module?"
   API response: {"message_id": "def-456", "cleaned_text": "Has anyone reviewed the PR for the auth module?", "action": "pass"}
   [3/20] suicide: "I can't take this anymore, everything feels pointless..."
   API response: {"message_id": "ghi-789", "cleaned_text": "I can't take this anymore, everything feels pointless...", "action": "warn"}
   ```

2. **FastAPI docs** at `http://129.114.26.207:8000/docs` — show POST /messages endpoint

**After completion, verify messages landed in PostgreSQL:**

```bash
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  source,
  COUNT(*) as count,
  COUNT(*) FILTER (WHERE is_toxicity) as toxic_count,
  COUNT(*) FILTER (WHERE is_suicide) as suicide_count
FROM messages
WHERE source = 'real'
GROUP BY source;
"
```

```bash
# Show last 5 messages
docker exec postgres psql -U user -d chatsentry -c "
SELECT left(text, 60) as raw_text, left(cleaned_text, 60) as cleaned, is_toxicity, is_suicide
FROM messages
ORDER BY created_at DESC
LIMIT 5;
"
```

**[Switch to browser: Adminer GUI]**
- Login: System=PostgreSQL, Server=postgres, Username=user, Password=chatsentry_pg, Database=chatsentry
- Run query: `SELECT text, cleaned_text, is_toxicity, is_suicide, source FROM messages ORDER BY created_at DESC LIMIT 10;`
- Show: raw text vs cleaned text (URLs replaced, PII scrubbed), labels from synthetic generation

**External confirmation:** Messages visible in PostgreSQL with both raw and cleaned text, labels correctly assigned.

---

## Scene 5: Verify Synthetic Data in S3 (15 sec)

**[Screen: Browser — Chameleon S3 Horizon GUI]**

**Narration:**
"Both generated datasets live in Chameleon object storage. The training CSV goes to `zulip-raw-messages/synthetic/`, and every message posted via test mode is also buffered and flushed to S3 as cleaned JSONL."

**Show in S3 GUI:**
- `proj09_Data/zulip-raw-messages/synthetic/synthetic_data.csv` (training mode output)
- `proj09_Data/zulip-raw-messages/cleaned/batch-*.jsonl` (test mode buffered output)

---

## Scene 6: End-to-End Summary (15 sec)

**[Screen: Terminal — final verification]**

**Narration:**
"To summarize the data generator: it uses a local Qwen2.5-1.5B model with few-shot prompting, oversamples minority classes per lecture best practices, and has two modes — training mode produces labeled CSVs for S3, and test mode hits the API endpoints in real-time to simulate user traffic."

```bash
# Final counts
docker exec postgres psql -U user -d chatsentry -c "
SELECT
  COUNT(*) as total_messages,
  COUNT(*) FILTER (WHERE source = 'real') as from_generator,
  COUNT(*) FILTER (WHERE is_toxicity) as toxic,
  COUNT(*) FILTER (WHERE is_suicide) as suicide
FROM messages;
"
```

---

## GUI Steps Summary

| Step | GUI | What to show |
|------|-----|-------------|
| 1 | FastAPI docs (`129.114.26.207:8000/docs`) | POST /messages endpoint accepting synthetic messages |
| 2 | Chameleon S3 Horizon (`chi.tacc.chameleoncloud.org`) | `synthetic_data.csv` in S3 bucket |
| 3 | Adminer (`129.114.26.207:5050`) | PostgreSQL `messages` table with synthetic rows, cleaned text, labels |

---

## Tests That Verify Requirements

| Requirement | Test / Verification | How to show in video |
|-------------|---------------------|----------------------|
| Synthetic data generation with best practices | `test_synthetic_gen.py` — 8 tests: label flags, distribution sums to 1.0, minority oversampling, text parsing | Run `pytest tests/test_synthetic_gen.py -v` |
| Hits service endpoints | `docker exec` test mode sends POST to `/messages`, API returns 200 with message_id | Show terminal output with API responses |
| Label distribution rebalancing | `LABEL_DISTRIBUTION` = toxic 30%, suicide 30%, benign 40% | Show Python output of distribution |
| Few-shot prompting | Prompt templates include 3 real examples per label | Show prompt template output |
| Source tracking | `source='real'` in PostgreSQL for generated messages | Adminer query showing source column |
| Messages stored with cleaned text | TextCleaner pipeline applied on ingest: URLs→[URL], PII→[EMAIL]/[PHONE]/[USER] | Adminer showing raw vs cleaned |
| S3 upload (training mode) | `synthetic_data.csv` in `zulip-raw-messages/synthetic/` | S3 Horizon GUI |
| S3 upload (test mode) | JSONL batch files in `zulip-raw-messages/cleaned/` | S3 Horizon GUI |
