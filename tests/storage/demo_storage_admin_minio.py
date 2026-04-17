from datamind.storage.admin import StorageAdmin
from datamind.config.storage import StorageConfig, MinIOStorageConfig


def main():
    config = StorageConfig(
        type="minio",
        model_dir="models",
        minio=MinIOStorageConfig(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="test-bucket",
            secure=False,
            region=None,
        ),
    )

    storage = StorageAdmin(config)

    print("👉 SAVE model")
    key = storage.save("modelA", "model.pkl", b"abjejsjebc-123")
    print("key =", key)

    print("👉 LOAD model")
    data = storage.load("modelA", "model.pkl")
    print("data =", data)

    print("👉 EXISTS")
    print(storage.exists("modelA", "model.pkl"))

    print("👉 LIST")
    print(storage.list("modelA"))

    print("👉 DELETE")
    storage.delete("modelA", "model.pkl")

    print("👉 EXISTS after delete")
    print(storage.exists("modelA", "model.pkl"))


if __name__ == "__main__":
    main()