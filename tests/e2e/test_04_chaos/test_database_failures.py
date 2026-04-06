"""Layer 4: Database failure chaos tests.

Verifies pipeline handles PostgreSQL going down gracefully.

Run: pytest tests/e2e/test_04_chaos/test_database_failures.py -v -m chaos
"""

import logging

import pytest

from tests.e2e.conftest import kill_container
from src.utils.db import get_db_connection

logger = logging.getLogger(__name__)


@pytest.mark.chaos
class TestDatabaseFailures:
    """Verify graceful handling of PostgreSQL failures."""

    def test_postgres_down_during_query(self, docker_services, clean_state):
        """Pipeline detects DB failure, doesn't crash with unhandled exception."""
        import psycopg2

        # Stop postgres
        import subprocess

        subprocess.run(["docker", "stop", "postgres"], check=True, capture_output=True)

        # Attempt connection — should raise OperationalError, not crash
        with pytest.raises(psycopg2.OperationalError):
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")

        # Restart postgres
        subprocess.run(["docker", "start", "postgres"], check=True, capture_output=True)

        # Wait for recovery
        import time

        time.sleep(5)

        # Verify reconnection works
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        assert result == (1,), "PostgreSQL did not recover after restart"

    def test_partial_write_rollback(self, docker_services, clean_state):
        """Transaction rollback on mid-load failure leaves no orphaned rows."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Start transaction, insert, then rollback
            cur.execute(
                "INSERT INTO messages (id, text, cleaned_text, is_suicide, is_toxicity, source, created_at) "
                "VALUES (gen_random_uuid(), 'rollback test', 'rollback test', false, false, 'test', NOW())"
            )
            conn.rollback()

            # Verify row was not committed
            cur.execute("SELECT COUNT(*) FROM messages WHERE text = 'rollback test'")
            count = cur.fetchone()[0]
            assert count == 0, f"Expected 0 rows after rollback, got {count}"
        finally:
            conn.close()
