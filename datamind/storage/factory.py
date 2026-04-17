from datamind.config.settings import get_settings
from datamind.storage.local import LocalStorage
from datamind.storage.minio import MinioStorage


def get_storage():
    cfg = get_settings().storage

    if cfg.backend == "local":
        return LocalStorage()

    if cfg.backend == "minio":
        from minio import Minio

        client = Minio(
            cfg.endpoint,
            access_key=cfg.access_key,
            secret_key=cfg.secret_key,
            secure=False,
        )

        storage = MinioStorage(client, cfg.bucket)

        storage.ensure_bucket(cfg.bucket)

        return storage

    raise ValueError(f"Unknown storage backend: {cfg.backend}")