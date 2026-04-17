import pytest
from datamind.storage.minio import MinIOStorageBackend


@pytest.fixture
def backend():
    return MinIOStorageBackend(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",
        secure=False,
    )


def test_minio_put_get(backend):
    key = "modelA/v1/model.pkl"
    data = b"hello-minio"

    backend.put_object(key, data)

    assert backend.get_object(key) == data


def test_minio_exists_and_delete(backend):
    key = "modelA/v1/x.pkl"

    backend.put_object(key, b"data")

    assert backend.object_exists(key) is True

    backend.delete_object(key)

    assert backend.object_exists(key) is False