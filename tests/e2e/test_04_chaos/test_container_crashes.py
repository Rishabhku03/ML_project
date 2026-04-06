"""Layer 4: Container crash chaos tests.

Verifies services recover after container crashes with data intact.

Run: pytest tests/e2e/test_04_chaos/test_container_crashes.py -v -m chaos
"""

import io
import logging
import subprocess
import time

import pandas as pd
import pytest

from src.utils.config import config
from src.utils.db import get_db_connection
from src.utils.minio_client import get_minio_client

logger = logging.getLogger(__name__)


@pytest.mark.chaos
class TestContainerCrashes:
    """Verify recovery after container crashes."""

    def test_api_crash_recovery(self, docker_services, clean_state):
        """API restarts, state preserved in PostgreSQL."""
        # Insert data before crash
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (id, text, cleaned_text, is_suicide, is_toxicity, source, created_at) "
            "VALUES (gen_random_uuid(), 'before crash', 'before crash', false, false, 'test', NOW())"
        )
        conn.commit()
        cur.close()
        conn.close()

        # Crash API
        subprocess.run(["docker", "stop", "api"], check=True, capture_output=True)
        time.sleep(2)

        # Restart API
        subprocess.run(["docker", "start", "api"], check=True, capture_output=True)
        time.sleep(10)  # API needs time to start

        # Verify data preserved
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT text FROM messages WHERE text = 'before crash'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row is not None, "Data lost after API crash/restart"

    def test_minio_data_persists_after_restart(self, docker_services, clean_state):
        """MinIO objects survive container restart."""
        client = get_minio_client()
        data = b"persistent data"
        client.put_object(
            bucket_name=config.BUCKET_RAW,
            object_name="test/crash/persist.csv",
            data=io.BytesIO(data),
            length=len(data),
        )

        # Crash and restart minio
        subprocess.run(["docker", "stop", "minio"], check=True, capture_output=True)
        time.sleep(2)
        subprocess.run(["docker", "start", "minio"], check=True, capture_output=True)
        time.sleep(5)

        # Verify data persists
        client = get_minio_client()
        response = client.get_object(config.BUCKET_RAW, "test/crash/persist.csv")
        content = response.read()
        response.close()
        assert content == data, "MinIO data lost after restart"
