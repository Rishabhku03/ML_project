#!/bin/bash
# Master script to run all demo parts
# Total runtime: ~3-4 minutes

set -e

VM_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")
echo "$VM_IP" > /tmp/vm_ip.txt

echo "=========================================="
echo " ChatSentry Data Pipeline — Full Demo"
echo "=========================================="
echo "VM IP: $VM_IP"
echo "Using demo.csv (1000 rows) for quick demonstration"
echo ""
echo "Part 1: Data Ingestion & Synthetic Expansion"
echo "Part 2: Synthetic Traffic Generator"
echo "Part 3: Online Text Cleaning Pipeline"
echo "Part 4: Batch Training Data Compilation"
echo ""
read -p "Press Enter to start..."

cd "$(dirname "$0")"

echo ""
echo "==================================================="
cd "part 1" && bash run_demo.sh
cd ..

echo ""
echo "==================================================="
cd "part 2" && bash run_demo.sh
cd ..

echo ""
echo "==================================================="
cd "part 3" && bash run_demo.sh
cd ..

echo ""
echo "==================================================="
cd "part 4" && bash run_demo.sh
cd ..

echo ""
echo "=========================================="
echo " All Demos Complete!"
echo "=========================================="
echo ""
echo "Access points:"
echo "  FastAPI Docs:  http://$VM_IP:8000/docs"
echo "  Dashboard:     http://$VM_IP:8000/dashboard"
echo "  Adminer:       http://$VM_IP:5050 (user/chatsentry_pg)"
echo "  GE Reports:    http://$VM_IP:8080"
echo "  S3 Horizon:    https://chi.tacc.chameleoncloud.org → Object Store → proj09_Data"
echo ""
