"""
ChatSentry — Teardown Script
==============================
Deletes the VM and lease from Chameleon Cloud.
Run from the same Chameleon Jupyter environment as deploy.
"""

import chi
from chi import server, lease, context
import os

context.version = "1.0"
context.choose_project()
context.choose_site(default="KVM@TACC")
username = os.getenv("USER")

server_name = f"node-chatsentry-{username}"
lease_name = f"lease-chatsentry-{username}"

print(f"Deleting server: {server_name}")
try:
    s = server.get_server(server_name)
    s.delete()
    print("  Server deleted.")
except Exception as e:
    print(f"  Server not found or already deleted: {e}")

print(f"Deleting lease: {lease_name}")
try:
    l = lease.get_lease(lease_name)
    lease.delete_lease(l.id)
    print("  Lease deleted.")
except Exception as e:
    print(f"  Lease not found or already deleted: {e}")

print("\nTeardown complete.")
