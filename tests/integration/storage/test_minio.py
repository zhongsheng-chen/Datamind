"""MinIO 真实集成测试

验证 Datamind MinIO 后端的上传、下载、哈希、删除、不存在对象和路径约束。

核心功能：
  - test_upload_download_hash_delete_and_missing_object: 验证对象生命周期和路径约束
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from datamind.config.storage import MinIOStorageConfig
from datamind.storage.errors import StorageKeyError, StorageNotFoundError
from datamind.storage.minio import MinIOStorageBackend


pytestmark = pytest.mark.integration


def test_upload_download_hash_delete_and_missing_object(
    minio_settings: MinIOStorageConfig,
) -> None:
    """测试真实 MinIO 对象可上传、校验、删除并报告缺失"""
    storage = MinIOStorageBackend(
        minio_settings.endpoint,
        access_key=minio_settings.access_key,
        secret_key=minio_settings.secret_key,
        bucket=minio_settings.bucket,
        secure=minio_settings.secure,
    )
    key = f"datamind-integration/{uuid.uuid4().hex}/model.bin"
    payload = b"datamind-real-minio-integration"
    try:
        storage.put_object(key, payload)
        downloaded = storage.get_object(key)
        assert downloaded == payload
        assert (
            hashlib.sha256(downloaded).hexdigest()
            == hashlib.sha256(payload).hexdigest()
        )
        storage.delete_object(key)
        with pytest.raises(StorageNotFoundError):
            storage.get_object(key)
        for unsafe_key in ("../model.bin", "/absolute/model.bin", "model//file.bin"):
            with pytest.raises(StorageKeyError):
                storage.put_object(unsafe_key, payload)
    finally:
        storage.delete_object(key)
