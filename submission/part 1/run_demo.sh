#!/bin/bash
# Part 1: Reproducible Pipeline — Ingest + Transform + Expand
# Runtime: ~30 seconds (demo.csv has 1000 rows)

set -e

echo "=== Part 1: Data Ingestion & Transformation Pipeline ==="
echo "Using demo.csv (1000 rows) for quick demonstration"
echo ""

# Step 1: Upload demo.csv to container
echo "[1/5] Copying demo.csv to API container..."
docker cp ../../demo.csv api:/tmp/demo.csv

# Step 2: Run ingestion (CSV → S3 chunks)
echo "[2/5] Ingesting data to S3..."
docker exec api python3 -m src.data.ingest_and_expand /tmp/demo.csv

# Step 3: Generate synthetic data (30 rows for quick demo)
echo "[3/5] Generating synthetic data (30 rows)..."
docker exec api python3 -m src.data.synthetic_generator --mode training --count 30

# Step 4: Verify S3 data
echo "[4/5] Verifying S3 bucket contents..."
docker exec api python3 -c "
from minio import Minio
import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
for prefix in ['zulip-raw-messages/real/', 'zulip-raw-messages/synthetic/']:
    objs = list(c.list_objects('proj09_Data', prefix=prefix, recursive=True))
    total = sum(o.size for o in objs)
    print(f'{prefix}: {len(objs)} files, {total/1024/1024:.1f} MB')
"

# Step 5: Show Great Expectations viewer link
echo "[5/5] Data quality reports available at:"
echo "  http://$(cat /tmp/vm_ip.txt 2>/dev/null || echo 'VM_IP'):8080"
echo ""
echo "✓ Part 1 Complete — All data in Chameleon S3 (proj09_Data)"
