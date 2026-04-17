import pytest
from datamind.storage.local import LocalStorageBackend


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(tmp_path)


def test_put_and_get(backend):
    key = "modelA/v1/model.pkl"
    data = b"hello"

    backend.put_object(key, data)
    assert backend.get_object(key) == data


def test_exists(backend):
    key = "modelA/v1/model.pkl"

    backend.put_object(key, b"data")
    assert backend.object_exists(key) is True


def test_delete(backend):
    key = "modelA/v1/model.pkl"

    backend.put_object(key, b"data")
    backend.delete_object(key)

    assert backend.object_exists(key) is False


def test_list_objects(backend):
    backend.put_object("modelA/v1/a.pkl", b"1")
    backend.put_object("modelA/v1/b.pkl", b"2")

    keys = backend.list_objects("modelA/v1/")

    assert "modelA/v1/a.pkl" in keys
    assert "modelA/v1/b.pkl" in keys