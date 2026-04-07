#!/bin/bash
# Part 2: Data Generator hitting service endpoints
# Runtime: ~2 minutes (10 messages, 1s apart)

set -e

echo "=== Part 2: Synthetic Data Generator ==="
echo "Sending 10 synthetic messages to API (1 message/second)"
echo ""

# Test mode: 10 messages, 1s apart, random labels
echo "[1/3] Generating and sending 10 synthetic messages..."
docker exec api python3 -m src.data.synthetic_generator \
  --mode test \
  --count 10 \
  --interval 1

# Check API received them
echo "[2/3] Verifying messages in PostgreSQL..."
docker exec postgres psql -U user -d chatsentry -c "
SELECT user_id, substring(text, 1, 60) as text_preview
FROM messages
WHERE user_id LIKE 'synth-test-%'
ORDER BY created_at DESC
LIMIT 10;
"

# Show dashboard link
echo "[3/3] View messages in labeling dashboard:"
echo "  http://$(cat /tmp/vm_ip.txt 2>/dev/null || echo 'VM_IP'):8000/dashboard"
echo ""
echo "✓ Part 2 Complete — 10 synthetic messages sent to API"
