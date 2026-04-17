from datamind.config.storage import StorageConfig, LocalStorageConfig
from datamind.storage.admin import StorageAdmin
import pytest


@pytest.fixture
def admin(tmp_path):
    config = StorageConfig(
        type="local",
        model_dir="models",
        local=LocalStorageConfig(
            base_dir=tmp_path
        )
    )

    return StorageAdmin(config)

def test_save_and_load(admin):
    key = admin.save("modelA", "model.pkl", b"abc")

    data = admin.load("modelA", "model.pkl")

    assert data == b"abc"
    assert key == "models/modelA/model.pkl"


def test_exists(admin):
    admin.save("modelA", "model.pkl", b"abc")
    assert admin.exists("modelA", "model.pkl") is True


def test_list(admin):
    admin.save("modelA", "a.pkl", b"1")
    admin.save("modelA", "b.pkl", b"2")

    files = admin.list("modelA")

    assert "a.pkl" in files
    assert "b.pkl" in files