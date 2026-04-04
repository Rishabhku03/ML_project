# Phase 1: Infrastructure & Ingestion

## Objective

Establish the foundational infrastructure for ChatSentry — a Docker Compose stack with PostgreSQL, MinIO, and FastAPI running on a single KVM@TACC VM. Ingest the 391K-row combined_dataset.csv into MinIO object storage. Build a synthetic data generator using HuggingFace API.

**Phase 1 = Set up the kitchen. Phase 2+ = Cook the food.**

## What Was Achieved

| Component | Status |
|-----------|--------|
| FastAPI API with /messages, /flags, /health | Running |
| PostgreSQL schema (4 tables, UUIDs, source tracking, GIN index) | Created |
| MinIO with zulip-raw-messages bucket | Running |
| Adminer (PostgreSQL browser UI) | Running |
| CSV ingestion (8 chunks uploaded to MinIO) | Complete |
| Synthetic data generator (HuggingFace Mistral-7B) | Complete |
| Live deployment on Chameleon Cloud | Verified |

## Main Code Files

### Infrastructure
- `docker/docker-compose.yaml` — Defines 5 services: postgres, minio, minio-init, adminer, api
- `docker/Dockerfile.api` — Dockerfile for the FastAPI container
- `docker/init_sql/00_create_tables.sql` — PostgreSQL schema (users, messages, flags, moderation)
- `docker/init_sql/01_seed_data.sql` — Seed data

### Application
- `src/api/main.py` — FastAPI app with /messages, /flags, /health endpoints
- `src/api/models.py` — Pydantic request/response models
- `src/api/routes/messages.py` — POST /messages endpoint (dummy, no DB writes in Phase 1)
- `src/api/routes/flags.py` — POST /flags endpoint (dummy, no DB writes in Phase 1)

### Data Pipeline
- `src/data/ingest_and_expand.py` — CSV chunked reader, uploads to MinIO
- `src/data/synthetic_generator.py` — HuggingFace Inference API generator
- `src/data/prompts.py` — Prompt templates for toxic/suicide/benign message generation

### Utilities
- `src/utils/config.py` — Environment configuration
- `src/utils/minio_client.py` — MinIO client factory
- `src/utils/db.py` — PostgreSQL connection utilities

### Deployment
- `deploy/0_deploy_chatbot.ipynb` — Jupyter notebook for Chameleon deployment (matches lab structure)
- `deploy/deploy_chameleon.py` — Python script for full automation
- `deploy/deploy_manual.sh` — Shell script for existing VM
- `deploy/teardown_chameleon.py` — Cleanup script

### Tests
- `tests/test_api_health.py` — API health endpoint tests
- `tests/test_csv_chunking.py` — CSV chunking and MinIO upload tests
- `tests/test_synthetic_gen.py` — Synthetic generation unit tests
- `tests/test_schema.py` — PostgreSQL schema verification
- `tests/test_minio_buckets.py` — MinIO bucket verification

## Deployment Issues & Fixes

### 1. python-chi not installed
**Error:** `ModuleNotFoundError: No module named 'chi'`
**Fix:** Added `!pip install python-chi` as the first cell in the notebook. In Chameleon Jupyter environment it's pre-installed, but running elsewhere requires installation.

### 2. SU quota exceeded
**Error:** `reservation for project chi-251409 would spend 1.20 sus, only 1.04 left`
**Fix:** Changed flavor from `m1.xlarge` to `m1.medium` (costs ~0.06 SU/hour vs ~0.15). The data pipeline stack runs fine on `m1.medium`.

### 3. Floating IP access — `._server` attribute
**Error:** `AttributeError: 'Server' object has no attribute '_server'`
**Fix:** The `python-chi` Server wrapper doesn't expose `._server`. Changed to use `chi.nova()` to get the Nova client and look up the server.

### 4. Floating IP access — `access_ipv4` attribute
**Error:** `AttributeError: access_ipv4`
**Fix:** Nova server object doesn't have `access_ipv4`. Used `srv.addresses` dict to extract the IP.

### 5. Floating IP — returned as dict not string
**Error:** URLs printed as `http://{'version': 4, 'addr': '129.114.27.58', ...}:8000`
**Fix:** The address list contains dicts. Changed to `list(srv.addresses.values())[0][-1]['addr']` to extract just the IP string.

### 6. Adminer "Not Found" at port 5050
**Error:** `{"detail":"Not Found"}`
**Fix:** Adminer service was not defined in docker-compose.yaml. Added the adminer service block.

### 7. Adminer can't connect to PostgreSQL
**Error:** `php_network_getaddresses: getaddrinfo for PostgreSQL failed`
**Fix:** User typed "PostgreSQL" (capital P) in the Server field. Must be `postgres` (lowercase, matching the docker-compose service name).

### 8. git clone fails — directory already exists
**Error:** `fatal: destination path '/home/cc/chatsentry' already exists and is not an empty directory`
**Fix:** Changed notebook cell to `git clone ... || cd /home/cc/chatsentry && git pull` to fall back to git pull if the repo already exists.

### 9. Docker permission denied
**Error:** `permission denied while trying to connect to the docker API`
**Fix:** Docker group change requires logout/login. Use `sudo docker` as workaround, or run `sudo usermod -aG docker $USER` and re-login.

### 10. pip3 not found
**Error:** `Command 'pip3' not found`
**Fix:** `sudo apt install python3-pip`

### 11. pip externally-managed-environment
**Error:** `This environment is externally managed` (PEP 668)
**Fix:** `pip3 install --break-system-packages -r requirements.txt`

### 12. CSV file not found
**Error:** `FileNotFoundError: CSV file not found: --csv`
**Fix:** The script uses positional args (`sys.argv[1]`), not `--csv` flag. Correct command: `python3 -m src.data.ingest_and_expand combined_dataset.csv`

### 13. CSV not on VM
**Error:** `FileNotFoundError: CSV file not found: combined_dataset.csv`
**Fix:** The CSV must be transferred to the VM first via scp from the LOCAL machine: `scp -i ~/.ssh/id_rsa_chameleon combined_dataset.csv cc@<IP>:/home/cc/chatsentry/`

### 14. minio-init container not running
**Error:** `Error response from daemon: container ... is not running`
**Fix:** minio-init is a one-shot job — it creates buckets then exits. To create missing buckets manually: `sudo docker exec minio mc mb --ignore-existing myminio/zulip-training-data`

### 15. HF_TOKEN in git history
**Error:** GitHub push protection blocked — detected HuggingFace token as secret
**Fix:** Removed hardcoded token from deploy script, used `os.environ.get("HF_TOKEN")` only. Squashed commits to clean git history.

### 16. CSV too large for GitHub (218MB)
**Error:** Push failed — file exceeds 100MB GitHub limit
**Fix:** Added `combined_dataset.csv` to .gitignore. Users transfer it to VM via scp.

### 17. GitHub authentication failed
**Error:** `remote: No anonymous write access`
**Fix:** User authenticated via Personal Access Token or SSH key.
