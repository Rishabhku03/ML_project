"""
ChatSentry — Chameleon Cloud Deployment Script
================================================
Provisions a KVM@TACC VM, installs Docker, clones the repo,
and starts the full stack (PostgreSQL, MinIO, FastAPI).

Usage (from Chameleon Jupyter environment):
    python deploy_chameleon.py

Or run cells interactively in a Jupyter notebook.
"""

import chi
from chi import server, context, lease, network
import os
import time
import datetime

# ──────────────────────────────────────────────────────────────
# CONFIGURATION — edit these values
# ──────────────────────────────────────────────────────────────

SITE = "KVM@TACC"
FLAVOR = "m1.xlarge"
IMAGE = "CC-Ubuntu24.04"
LEASE_DURATION_HOURS = 8
HF_TOKEN = os.environ.get("HF_TOKEN") or input("Enter your HF_TOKEN: ")
GIT_REPO = "https://github.com/Rishabhku03/ML_project.git"
KEY_NAME = "id_rsa_chameleon"  # your SSH key name in Chameleon

# ──────────────────────────────────────────────────────────────
# STEP 1: Initialize context
# ──────────────────────────────────────────────────────────────

print("=" * 60)
print("  ChatSentry — Chameleon Deployment")
print("=" * 60)

context.version = "1.0"
context.choose_project()
context.choose_site(default=SITE)
username = os.getenv("USER")

# ──────────────────────────────────────────────────────────────
# STEP 2: Reserve VM (create lease)
# ──────────────────────────────────────────────────────────────

print(f"\n[2/10] Creating lease for {FLAVOR} ({LEASE_DURATION_HOURS}h)...")

l = lease.Lease(
    f"proj09_Data",
    duration=datetime.timedelta(hours=LEASE_DURATION_HOURS),
)
l.add_flavor_reservation(id=chi.server.get_flavor_id(FLAVOR), amount=1)
l.submit(idempotent=True)
l.show()

print("  Lease created. Waiting for ACTIVE status...")
time.sleep(10)

# ──────────────────────────────────────────────────────────────
# STEP 3: Provision VM
# ──────────────────────────────────────────────────────────────

print(f"\n[3/10] Launching VM with {IMAGE}...")

s = server.Server(
    f"node-proj09-{username}",
    image_name=IMAGE,
    flavor_name=l.get_reserved_flavors()[0].name,
)
s.submit(idempotent=True)

# ──────────────────────────────────────────────────────────────
# STEP 4: Get floating IP
# ──────────────────────────────────────────────────────────────

print("\n[4/10] Associating floating IP...")
s.associate_floating_ip()
s.refresh()

nova = chi.nova()
srv = nova.servers.find(name=f"node-proj09-{username}")
floating_ip = list(srv.addresses.values())[0][-1]  # last IP in first network = floating
print(f"  Floating IP: {floating_ip}")

# ──────────────────────────────────────────────────────────────
# STEP 5: Add security groups
# ──────────────────────────────────────────────────────────────

print("\n[5/10] Configuring security groups...")

security_groups = [
    {"name": "allow-ssh", "port": 22, "description": "SSH"},
    {"name": "allow-8000", "port": 8000, "description": "FastAPI"},
    {"name": "allow-9001", "port": 9001, "description": "MinIO Console"},
    {"name": "allow-5050", "port": 5050, "description": "Adminer"},
    {"name": "allow-8888", "port": 8888, "description": "Jupyter"},
]

for sg in security_groups:
    secgroup = network.SecurityGroup(
        {"name": sg["name"], "description": sg["description"]}
    )
    secgroup.add_rule(direction="ingress", protocol="tcp", port=sg["port"])
    secgroup.submit(idempotent=True)
    s.add_security_group(sg["name"])

print(f"  Security groups: {[sg['name'] for sg in security_groups]}")

s.refresh()
s.check_connectivity()
print("  VM is reachable.")

# ──────────────────────────────────────────────────────────────
# STEP 6: Install Docker
# ──────────────────────────────────────────────────────────────

print("\n[6/10] Installing Docker on VM...")
s.execute("curl -sSL https://get.docker.com/ | sudo sh")
s.execute("sudo groupadd -f docker; sudo usermod -aG docker $USER")
print("  Docker installed.")

# ──────────────────────────────────────────────────────────────
# STEP 7: Clone repo
# ──────────────────────────────────────────────────────────────

print(f"\n[7/10] Cloning repo: {GIT_REPO}")
s.execute(f"git clone {GIT_REPO} /home/cc/chatsentry")
print("  Repo cloned to /home/cc/chatsentry")

# ──────────────────────────────────────────────────────────────
# STEP 8: Set HF_TOKEN and start services
# ──────────────────────────────────────────────────────────────

print("\n[8/10] Setting HF_TOKEN and starting Docker Compose...")
s.execute(
    f"echo 'export HF_TOKEN={HF_TOKEN}' >> /home/cc/.bashrc && "
    f"export HF_TOKEN={HF_TOKEN} && "
    f"cd /home/cc/chatsentry/docker && "
    f"docker compose up -d"
)
print("  Docker Compose started.")

# ──────────────────────────────────────────────────────────────
# STEP 9: Wait for services to be healthy
# ──────────────────────────────────────────────────────────────

print("\n[9/10] Waiting for services to be healthy...")
time.sleep(15)

result = s.execute("docker ps --format 'table {{.Names}}\t{{.Status}}'")
print(result)

# ──────────────────────────────────────────────────────────────
# STEP 10: Verify endpoints
# ──────────────────────────────────────────────────────────────

print("\n[10/10] Verifying endpoints...")

health_check = s.execute("curl -s http://localhost:8000/health")
print(f"  /health: {health_check}")

minio_check = s.execute("curl -s -o /dev/null -w '%{http_code}' http://localhost:9001")
print(f"  MinIO console: HTTP {minio_check}")

# ──────────────────────────────────────────────────────────────
# DONE
# ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  DEPLOYMENT COMPLETE")
print("=" * 60)
print(f"""
  FastAPI:     http://{floating_ip}:8000/health
  FastAPI docs:http://{floating_ip}:8000/docs
  MinIO:       http://{floating_ip}:9001  (admin / chatsentry_minio)
  Adminer:     http://{floating_ip}:5050  (PostgreSQL / user / chatsentry_pg)
  PostgreSQL:  {floating_ip}:5432

  SSH: ssh -i ~/.ssh/{KEY_NAME} cc@{floating_ip}
  Logs: ssh -i ~/.ssh/{KEY_NAME} cc@{floating_ip} 'cd chatsentry/docker && docker compose logs -f'
""")
