"""Integration smoke test for all 3 pipeline phases.

Validates end-to-end connectivity and correctness against live Docker services
(PostgreSQL, MinIO). Run after deployment to catch misconfigurations and regressions.

Usage:
    python scripts/smoke_test_integration.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import logging
import os
import sys
from datetime import datetime, timedelta

# Add project root to sys.path so `src` package is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd

logger = logging.getLogger("smoke_test")

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
PASSED = 0
FAILED = 0
DOCKER_AVAILABLE = True


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a check result and log it."""
    global PASSED, FAILED
    if condition:
        PASSED += 1
        logger.info("PASS: %s", name)
    else:
        FAILED += 1
        msg = f"FAIL: {name}"
        if detail:
            msg += f" — {detail}"
        logger.error(msg)


# ---------------------------------------------------------------------------
# Check 1: PostgreSQL reachable
# ---------------------------------------------------------------------------


def check_postgres() -> bool:
    """Verify PostgreSQL is reachable via get_db_connection()."""
    global DOCKER_AVAILABLE
    try:
        from src.utils.db import get_db_connection

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        check("PostgreSQL reachable", result == (1,))
        return True
    except Exception as exc:
        check("PostgreSQL reachable", False, str(exc))
        DOCKER_AVAILABLE = False
        return False


# ---------------------------------------------------------------------------
# Check 2: MinIO reachable + buckets exist
# ---------------------------------------------------------------------------


def check_minio() -> bool:
    """Verify MinIO is reachable and required buckets exist."""
    global DOCKER_AVAILABLE
    try:
        from src.utils.config import config
        from src.utils.minio_client import get_minio_client

        client = get_minio_client()
        bucket_raw_exists = client.bucket_exists(config.BUCKET_RAW)
        bucket_training_exists = client.bucket_exists(config.BUCKET_TRAINING)
        both_exist = bucket_raw_exists and bucket_training_exists
        detail = ""
        if not both_exist:
            missing = []
            if not bucket_raw_exists:
                missing.append(config.BUCKET_RAW)
            if not bucket_training_exists:
                missing.append(config.BUCKET_TRAINING)
            detail = f"missing buckets: {', '.join(missing)}"
        check("MinIO reachable + buckets exist", both_exist, detail)
        return both_exist
    except Exception as exc:
        check("MinIO reachable + buckets exist", False, str(exc))
        DOCKER_AVAILABLE = False
        return False


# ---------------------------------------------------------------------------
# Check 3: TextCleaner pipeline
# ---------------------------------------------------------------------------


def check_text_cleaner() -> None:
    """Verify TextCleaner strips markdown, URLs, emails, and username mentions."""
    from src.data.text_cleaner import TextCleaner

    cleaner = TextCleaner()
    raw = "**bold** visit https://example.com email me@test.org and @john"
    cleaned = cleaner.clean(raw)

    checks_passed = (
        "**" not in cleaned
        and "https://example.com" not in cleaned
        and "me@test.org" not in cleaned
        and "@john" not in cleaned
    )
    check("TextCleaner pipeline", checks_passed, f"cleaned: '{cleaned}'")


# ---------------------------------------------------------------------------
# Check 4: Quality gate
# ---------------------------------------------------------------------------


def check_quality_gate() -> None:
    """Verify quality gate removes #ERROR! rows and short texts."""
    from src.data.compile_training_data import apply_quality_gate

    df = pd.DataFrame(
        {
            "cleaned_text": [
                "#ERROR! duplicate",
                "valid text that is long enough",
                "short",
                "another valid and sufficiently long text",
                "#ERROR!",
            ]
        }
    )
    result = apply_quality_gate(df)
    # Should keep only 2 rows (long enough, no #ERROR!)
    no_errors = not result["cleaned_text"].str.contains("#ERROR!").any()
    no_short = (result["cleaned_text"].str.len() >= 10).all()
    correct_count = len(result) == 2
    check(
        "Quality gate",
        no_errors and no_short and correct_count,
        f"got {len(result)} rows, expected 2",
    )


# ---------------------------------------------------------------------------
# Check 5: Temporal leakage filter
# ---------------------------------------------------------------------------


def check_temporal_leakage() -> None:
    """Verify temporal leakage filter drops rows where created_at >= decided_at."""
    from src.data.compile_training_data import filter_temporal_leakage

    now = datetime.now()
    df = pd.DataFrame(
        {
            "cleaned_text": ["ok row", "leaked row", "also ok"],
            "created_at": [
                now - timedelta(hours=2),
                now,
                now - timedelta(hours=1),
            ],
            "decided_at": [
                now - timedelta(hours=1),
                now - timedelta(hours=2),
                now + timedelta(hours=1),
            ],
        }
    )
    result = filter_temporal_leakage(df)
    # Row 0: created_at < decided_at (keep)
    # Row 1: created_at >= decided_at (drop)
    # Row 2: created_at < decided_at (keep)
    kept_correct = len(result) == 2
    no_leaked = "leaked row" not in result["cleaned_text"].values
    check(
        "Temporal leakage filter",
        kept_correct and no_leaked,
        f"kept {len(result)} rows, expected 2",
    )


# ---------------------------------------------------------------------------
# Check 6: Stratified split
# ---------------------------------------------------------------------------


def check_stratified_split() -> None:
    """Verify stratified split produces ~70/15/15 proportions."""
    from src.data.compile_training_data import stratified_split

    # Create 1000-row DataFrame with binary labels
    df = pd.DataFrame(
        {
            "cleaned_text": [f"text {i}" for i in range(1000)],
            "is_suicide": [0] * 800 + [1] * 200,
            "is_toxicity": ([0] * 600 + [1] * 200) + ([0] * 150 + [1] * 50),
        }
    )
    train_df, val_df, test_df = stratified_split(df)

    total = len(train_df) + len(val_df) + len(test_df)
    train_pct = len(train_df) / total
    val_pct = len(val_df) / total
    test_pct = len(test_df) / total

    # Allow 5% tolerance
    proportions_ok = (
        0.65 <= train_pct <= 0.75
        and 0.10 <= val_pct <= 0.20
        and 0.10 <= test_pct <= 0.20
    )
    no_label_combo = "label_combo" not in train_df.columns
    check(
        "Stratified split",
        proportions_ok and no_label_combo,
        f"train={train_pct:.1%} val={val_pct:.1%} test={test_pct:.1%}",
    )


# ---------------------------------------------------------------------------
# Check 7: MinIO snapshot upload
# ---------------------------------------------------------------------------


def check_minio_snapshot() -> None:
    """Verify upload_snapshot puts train/val/test CSVs in MinIO."""
    import io as _io

    from src.utils.config import config
    from src.utils.minio_client import get_minio_client

    from src.data.compile_training_data import generate_version, upload_snapshot

    client = get_minio_client()
    train_df = pd.DataFrame(
        {
            "cleaned_text": ["a"],
            "is_suicide": [0],
            "is_toxicity": [0],
            "source": ["test"],
            "message_id": [1],
        }
    )
    val_df = pd.DataFrame(
        {
            "cleaned_text": ["b"],
            "is_suicide": [1],
            "is_toxicity": [0],
            "source": ["test"],
            "message_id": [2],
        }
    )
    test_df = pd.DataFrame(
        {
            "cleaned_text": ["c"],
            "is_suicide": [0],
            "is_toxicity": [1],
            "source": ["test"],
            "message_id": [3],
        }
    )

    version = upload_snapshot(client, config.BUCKET_TRAINING, train_df, val_df, test_df)

    all_exist = True
    for split_name in ("train", "val", "test"):
        object_name = f"{version}/{split_name}.csv"
        try:
            stat = client.stat_object(config.BUCKET_TRAINING, object_name)
            if stat.size == 0:
                all_exist = False
        except Exception:
            all_exist = False

    check("MinIO snapshot upload + verification", all_exist, f"version={version}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all smoke checks. Returns 0 on all-pass, 1 on any failure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Phase 1: Docker service checks (gate)
    pg_ok = check_postgres()
    minio_ok = check_minio()

    if not DOCKER_AVAILABLE:
        logger.warning(
            "Docker services not fully available — skipping live pipeline checks"
        )
        logger.info("Results: %d passed, %d failed", PASSED, FAILED)
        return 1 if FAILED > 0 else 0

    # Phase 2: Pipeline logic checks
    check_text_cleaner()
    check_quality_gate()
    check_temporal_leakage()
    check_stratified_split()

    # Phase 3: End-to-end MinIO check
    if minio_ok:
        check_minio_snapshot()

    logger.info("Results: %d passed, %d failed", PASSED, FAILED)
    return 1 if FAILED > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
