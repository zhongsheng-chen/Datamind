from datamind.storage.strategy import StorageKeyStrategy


def test_model_key():
    s = StorageKeyStrategy("models")

    key = s.model_key("modelA", "a.pkl")
    assert key == "models/modelA/a.pkl"


def test_model_prefix():
    s = StorageKeyStrategy("models")

    prefix = s.model_prefix("modelA")
    assert prefix == "models/modelA/"


def test_extract_filename():
    assert StorageKeyStrategy.extract_filename("a/b/c.pkl") == "c.pkl"