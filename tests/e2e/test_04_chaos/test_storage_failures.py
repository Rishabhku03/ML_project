"""Layer 4: Storage failure chaos tests.

Verifies pipeline handles MinIO going down gracefully.

Run: pytest tests/e2e/test_04_chaos/test_storage_failures.py -v -m chaos
"""

import io
import logging
import subprocess
import time

import pandas as pd
import pytest

from src.utils.config import config
from src.utils.minio_client import get_minio_client

logger = logging.getLogger(__name__)


@pytest.mark.chaos
class TestStorageFailures:
    """Verify graceful handling of MinIO failures."""

    def test_minio_connection_error(self, docker_services):
        """MinIO client raises exception when MinIO is down."""
        import minio

        # Stop minio
        subprocess.run(["docker", "stop", "minio"], check=True, capture_output=True)

        # Attempt operation — should raise exception
        with pytest.raises(Exception):
            client = get_minio_client()
            client.bucket_exists(config.BUCKET_RAW)

        # Restart minio
        subprocess.run(["docker", "start", "minio"], check=True, capture_output=True)
        time.sleep(5)

        # Verify reconnection
        client = get_minio_client()
        assert client.bucket_exists(config.BUCKET_RAW), "MinIO did not recover"

    def test_minio_upload_after_restart(self, docker_services, clean_state):
        """Upload succeeds after MinIO restart."""
        # Stop and restart
        subprocess.run(["docker", "stop", "minio"], check=True, capture_output=True)
        time.sleep(2)
        subprocess.run(["docker", "start", "minio"], check=True, capture_output=True)
        time.sleep(5)

        # Upload should succeed
        client = get_minio_client()
        data = b"test data after restart"
        client.put_object(
            bucket_name=config.BUCKET_RAW,
            object_name="test/chaos/restart_test.csv",
            data=io.BytesIO(data),
            length=len(data),
            content_type="text/csv",
        )

        # Verify
        response = client.get_object(config.BUCKET_RAW, "test/chaos/restart_test.csv")
        content = response.read()
        response.close()
        assert content == data, "Uploaded data does not match"
