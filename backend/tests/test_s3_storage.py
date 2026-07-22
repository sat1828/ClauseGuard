import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import boto3
from moto import mock_aws

import app.config as config_module
from app.storage import S3Storage, StorageError


@pytest.fixture
def s3_env(monkeypatch):
    """Point the app's S3 settings at a moto-mocked bucket, and actually
    create that bucket before each test — moto intercepts boto3 calls at
    the network layer, so this is a real S3 API round-trip, just not a
    real AWS/R2 account."""
    monkeypatch.setattr(config_module.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(config_module.settings, "S3_BUCKET", "clauseguard-test-bucket")
    monkeypatch.setattr(config_module.settings, "S3_ACCESS_KEY_ID", "testing")
    monkeypatch.setattr(config_module.settings, "S3_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(config_module.settings, "S3_REGION", "us-east-1")
    monkeypatch.setattr(config_module.settings, "S3_ENDPOINT_URL", "")

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="clauseguard-test-bucket")
        yield


def test_put_and_get_round_trip(s3_env):
    storage = S3Storage()
    storage.put("users/abc/contract.pdf", b"fake pdf bytes here")
    result = storage.get("users/abc/contract.pdf")
    assert result == b"fake pdf bytes here"


def test_get_missing_key_raises_storage_error(s3_env):
    storage = S3Storage()
    with pytest.raises(StorageError, match="not found"):
        storage.get("does/not/exist.pdf")


def test_exists_true_and_false(s3_env):
    storage = S3Storage()
    assert storage.exists("some/key.pdf") is False
    storage.put("some/key.pdf", b"data")
    assert storage.exists("some/key.pdf") is True


def test_delete_removes_object(s3_env):
    storage = S3Storage()
    storage.put("to/delete.pdf", b"data")
    assert storage.exists("to/delete.pdf") is True
    storage.delete("to/delete.pdf")
    assert storage.exists("to/delete.pdf") is False


def test_delete_nonexistent_key_does_not_raise(s3_env):
    storage = S3Storage()
    storage.delete("never/existed.pdf")  # should not raise


def test_missing_bucket_config_raises_clear_error(monkeypatch):
    monkeypatch.setattr(config_module.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(config_module.settings, "S3_BUCKET", "")
    with mock_aws():
        with pytest.raises(StorageError, match="S3_BUCKET"):
            S3Storage()


def test_r2_style_endpoint_url_is_passed_through(s3_env, monkeypatch):
    """R2 requires a custom endpoint_url pointing at Cloudflare's S3-compatible
    API instead of AWS. Confirms that config actually reaches the boto3 client
    rather than being silently ignored."""
    monkeypatch.setattr(
        config_module.settings, "S3_ENDPOINT_URL",
        "https://fake-account-id.r2.cloudflarestorage.com"
    )
    storage = S3Storage()
    assert storage.client.meta.endpoint_url == "https://fake-account-id.r2.cloudflarestorage.com"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
