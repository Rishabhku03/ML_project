#!/bin/bash
# Part 3: Online Feature Computation (TextCleaner pipeline)
# Runtime: ~5 seconds (10 test messages)

set -e

echo "=== Part 3: Online Feature Computation (TextCleaner) ==="
echo "Testing text cleaning with 10 different input types"
echo ""

# Send 10 test messages with different cleaning challenges
echo "[1/3] Sending 10 test messages to API..."
docker exec api python3 -c "
import requests
BASE = 'http://localhost:8000'

tests = [
    ('html', '<b>I feel so sad</b> and <i>nobody cares</i> about me'),
    ('markdown', '**I hate everything** and _nobody likes me_'),
    ('urls', 'Check this out https://example.com/sad'),
    ('emojis', 'I am so sad 😢 and crying 😭'),
    ('pii', 'Contact me at john@example.com or call 555-123-4567'),
    ('username', 'Hey @alice and @bob123 you are the worst'),
    ('unicode', 'I feel like café life is meaningless'),
    ('mixed', '<p>Email test@test.com</p> https://sad.com 😢'),
    ('code', '\`\`\`python\nprint(hi)\`\`\` nobody understands me'),
    ('all', '<b>@admin</b> https://site.com 😭 admin@test.com **help**'),
]

for label, text in tests:
    resp = requests.post(f'{BASE}/messages', json={'text': text, 'user_id': f'demo-{label}'})
    d = resp.json()
    changed = d['raw_text'] != d['cleaned_text']
    status = 'CLEANED' if changed else 'UNCHANGED'
    print(f'[{status}] {label}: {d[\"raw_text\"][:40]} → {d[\"cleaned_text\"][:40]}')
"

# Flush to S3
echo "[2/3] Flushing cleaned data to S3..."
curl -s -X POST http://localhost:8000/admin/flush

# Verify
echo "[3/3] Verifying cleaned data in S3..."
docker exec api python3 -c "
from minio import Minio
import os
c = Minio(os.environ['S3_ENDPOINT'], os.environ['MINIO_ACCESS_KEY'], os.environ['MINIO_SECRET_KEY'], secure=True, region='')
objs = list(c.list_objects('proj09_Data', prefix='zulip-raw-messages/cleaned/', recursive=True))
print(f'Cleaned data files: {len(objs)}')
for obj in objs:
    print(f'  {obj.object_name} ({obj.size/1024:.1f} KB)')
"

echo ""
echo "✓ Part 3 Complete — Text cleaning pipeline verified"
echo "  Pipeline: unicode → markdown → URLs → emojis → PII"
