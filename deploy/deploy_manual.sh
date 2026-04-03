#!/bin/bash
# ChatSentry — Manual SSH Deployment (steps 6-10)
# Use this if you already have a VM running and just need to deploy the stack.
#
# Usage:
#   export HF_TOKEN=hf_your_token
#   bash deploy_manual.sh <FLOATING_IP> [SSH_KEY_PATH]
#
# Example:
#   export HF_TOKEN=hf_xxxxx
#   bash deploy_manual.sh 129.114.26.100 ~/.ssh/id_rsa_chameleon

set -euo pipefail

FLOATING_IP="${1:?Usage: $0 <FLOATING_IP> [SSH_KEY_PATH]}"
SSH_KEY="${2:-$HOME/.ssh/id_rsa_chameleon}"
REPO_URL="https://github.com/Rishabhku03/ML_project.git"
REMOTE="cc@${FLOATING_IP}"
SSH_CMD="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no ${REMOTE}"

echo "=== ChatSentry Manual Deployment ==="
echo "Target: ${FLOATING_IP}"
echo ""

# Step 6: Install Docker
echo "[1/5] Installing Docker..."
${SSH_CMD} "curl -sSL https://get.docker.com/ | sudo sh && sudo groupadd -f docker; sudo usermod -aG docker \$USER"
echo "  Done. Reconnecting for docker group..."
# Need fresh SSH session for group change
SSH_CMD="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no ${REMOTE}"

# Step 7: Clone repo
echo "[2/5] Cloning repo..."
${SSH_CMD} "git clone ${REPO_URL} /home/cc/chatsentry 2>/dev/null || echo '  Repo already cloned, pulling...'; cd /home/cc/chatsentry && git pull"

# Step 8: Set HF_TOKEN and start services
echo "[3/5] Starting Docker Compose..."
${SSH_CMD} "echo 'export HF_TOKEN=${HF_TOKEN}' >> /home/cc/.bashrc && export HF_TOKEN=${HF_TOKEN} && cd /home/cc/chatsentry/docker && docker compose up -d"

# Step 9: Wait for health
echo "[4/5] Waiting for services (20s)..."
sleep 20
${SSH_CMD} "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Step 10: Verify
echo "[5/5] Verifying endpoints..."
${SSH_CMD} "curl -s http://localhost:8000/health"
echo ""
${SSH_CMD} "curl -s -o /dev/null -w 'MinIO console: HTTP %{http_code}\n' http://localhost:9001"

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "  FastAPI:     http://${FLOATING_IP}:8000/health"
echo "  FastAPI docs:http://${FLOATING_IP}:8000/docs"
echo "  MinIO:       http://${FLOATING_IP}:9001  (admin / chatsentry_minio)"
echo "  Adminer:     http://${FLOATING_IP}:5050  (PostgreSQL / user / chatsentry_pg)"
echo "  PostgreSQL:  ${FLOATING_IP}:5432"
echo "  SSH:         ssh -i ${SSH_KEY} cc@${FLOATING_IP}"
