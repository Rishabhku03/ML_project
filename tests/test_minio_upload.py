"""Integration tests for MinIO upload. Requires running Docker services."""


def test_minio_bucket_accessible(minio_client):
    assert minio_client.bucket_exists("zulip-raw-messages")


def test_ingest_script_importable():
    from src.data.ingest_and_expand import CHUNK_SIZE

    assert CHUNK_SIZE == 50_000
