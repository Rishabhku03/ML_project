"""Integration tests for MinIO buckets. Requires running Docker services."""


def test_raw_messages_bucket_exists(minio_client):
    assert minio_client.bucket_exists(
        "zulip-raw-messages"
    ), "Bucket zulip-raw-messages not found"


def test_training_data_bucket_exists(minio_client):
    assert minio_client.bucket_exists(
        "zulip-training-data"
    ), "Bucket zulip-training-data not found"
