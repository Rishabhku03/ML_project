"""Integration tests for S3 bucket. Requires running Docker services."""


def test_bucket_exists(minio_client):
    assert minio_client.bucket_exists("chatsentry-data"), (
        "Bucket chatsentry-data not found"
    )
