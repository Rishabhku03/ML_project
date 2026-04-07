#!/bin/bash
# Part 4: Batch Pipeline — Versioned Training Data Compilation
# Runtime: ~15 seconds (1000 rows from demo.csv)
# WARNING: compile_initial() with full 391K rows takes 5-10 minutes

set -e

echo "=== Part 4: Batch Training Data Compilation Pipeline ==="
echo "Using demo.csv (1000 rows) for quick demonstration"
echo ""

# Step 1: Clear PostgreSQL for clean demo
echo "[1/5] Resetting PostgreSQL..."
docker exec postgres psql -U user -d chatsentry -c "TRUNCATE messages, flags, moderation, users CASCADE;"

# Step 2: Run initial compilation (reads S3, loads PG, splits, uploads)
echo "[2/5] Running compile_initial() — reads demo.csv chunks from S3..."
echo "  This reads CSV → cleans → loads to PostgreSQL → validates → splits → uploads"
docker exec api python3 -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
from src.data.compile_training_data import compile_initial
compile_initial()
"

# Step 3: Verify training data in S3
echo "[3/5] Verifying training data in S3..."
docker exec api python3 -c "
from minio import Minio
import os, pandas as pd, io
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')

# Find latest version
versions = set()
for obj in c.list_objects('proj09_Data', prefix='zulip-training-data/', recursive=True):
    version = obj.object_name.split('/')[1] if '/' in obj.object_name else ''
    if version.startswith('v'):
        versions.add(version)

latest = sorted(versions)[-1] if versions else None
if latest:
    print(f'Latest version: {latest}')
    for split in ['train.csv', 'val.csv', 'test.csv']:
        try:
            obj = c.get_object('proj09_Data', f'zulip-training-data/{latest}/{split}')
            df = pd.read_csv(io.BytesIO(obj.read()), nrows=3)
            obj.close()
            print(f'  {split}: {len(df)} rows (preview), columns: {list(df.columns)}')
        except:
            print(f'  {split}: not found')
"

# Step 4: Show PostgreSQL counts
echo "[4/5] PostgreSQL state after compilation..."
docker exec postgres psql -U user -d chatsentry -c "
SELECT 'messages' as table, COUNT(*) FROM messages 
UNION ALL SELECT 'moderation', COUNT(*) FROM moderation;
"

# Step 5: Show GE report link
echo "[5/5] Data quality report available at:"
echo "  http://$(cat /tmp/vm_ip.txt 2>/dev/null || echo 'VM_IP'):8080"
echo ""
echo "✓ Part 4 Complete — Versioned training data in S3"
echo "  • Temporal leakage prevention: created_at < decided_at"
echo "  • Stratified split: 70/15/15 by (is_suicide, is_toxicity)"
echo "  • Data quality: GE validation + quality gate"
