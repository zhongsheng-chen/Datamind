"""MinIO 模型制品与 Artifact 元数据集成测试

验证真实 sklearn 模型经 Storage facade 写入 MinIO，并由 ArtifactRepository
持久化完整性元数据后，可以在新会话中读取、校验和重新加载。

核心功能：
  - test_model_artifact_round_trips_through_minio_and_repository:
    验证模型制品内容与数据库元数据保持一致
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import uuid

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sqlalchemy.ext.asyncio import AsyncEngine

from datamind.config.storage import MinIOStorageConfig, StorageConfig
from datamind.constants import StorageType
from datamind.db.core import UnitOfWork
from datamind.db.repositories import ArtifactRepository
from datamind.models.artifact import ModelArtifactLoader
from datamind.storage import Storage
from datamind.storage.admin import StorageAdmin


pytestmark = pytest.mark.integration


def serialize_model(model: LogisticRegression) -> bytes:
    """将真实 sklearn 模型序列化为制品字节"""
    buffer = BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_model_artifact_round_trips_through_minio_and_repository(
    datamind_database: AsyncEngine,
    minio_settings: MinIOStorageConfig,
) -> None:
    """测试真实模型通过 MinIO 和 ArtifactRepository 完整往返"""
    del datamind_database
    suffix = uuid.uuid4().hex
    artifact_id = f"art_{suffix}"
    version_id = f"ver_{suffix}"

    model = LogisticRegression(random_state=0).fit(
        np.array(
            [
                [-2.0, -1.0],
                [-1.0, -0.5],
                [0.5, 0.8],
                [1.5, 2.0],
            ]
        ),
        np.array([0, 0, 1, 1]),
    )
    payload = serialize_model(model)
    sha256 = hashlib.sha256(payload).hexdigest()

    storage = Storage(
        StorageAdmin(
            StorageConfig(
                type=StorageType.MINIO,
                minio=minio_settings,
            )
        )
    )
    model_key = storage.save(
        "integration-classifier",
        "1.0.0",
        artifact_id,
        "model.pkl",
        payload,
    )

    try:
        async with UnitOfWork() as uow:
            ArtifactRepository(uow.session).create_artifact(
                artifact_id=artifact_id,
                version_id=version_id,
                revision=1,
                sha256=sha256,
                digest=sha256,
                source_path="integration/model.pkl",
                model_key=model_key,
                bento_tag=f"integration-classifier:{suffix[:12]}",
                created_by="integration-test",
            )

        async with UnitOfWork() as uow:
            artifact = await ArtifactRepository(uow.session).get_artifact(artifact_id)

        downloaded = storage.load_by_key(model_key)
        restored = ModelArtifactLoader.load(
            framework="sklearn",
            data=downloaded,
        )

        assert artifact is not None
        assert artifact.version_id == version_id
        assert artifact.model_key == model_key
        assert artifact.sha256 == sha256
        assert artifact.digest == sha256
        assert hashlib.sha256(downloaded).hexdigest() == artifact.sha256
        assert restored.predict_proba([[0.75, 1.25]]) == pytest.approx(
            model.predict_proba([[0.75, 1.25]])
        )
    finally:
        storage.delete_by_key(model_key, strict=False)
