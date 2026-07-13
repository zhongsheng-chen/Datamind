# tests/db/repositories/test_artifact.py

"""模型制品仓储测试

验证制品修订的创建、查询和永久清理状态转换。

核心功能：
  - test_create_artifact: 验证创建 active 制品修订
  - test_get_current_artifact: 验证查询当前制品
  - test_artifact_lifecycle: 验证制品生命周期状态转换
"""

from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.models.artifacts import Artifact
from datamind.db.repositories.artifact import ArtifactRepository


def create_repository() -> tuple[ArtifactRepository, AsyncMock, MagicMock]:
    """创建制品仓储及会话替身"""
    result = MagicMock()
    execute = AsyncMock(return_value=result)
    add = MagicMock()
    session_mock = MagicMock(spec=AsyncSession)
    session_mock.execute = execute
    session_mock.add = add
    session = cast(AsyncSession, cast(object, session_mock))

    return ArtifactRepository(session), execute, result


def create_artifact(**overrides: object) -> Artifact:
    """创建制品测试对象"""
    values: dict[str, object] = {
        "artifact_id": "art_0123456789abcdef",
        "version_id": "ver_0123456789abcdef",
        "revision": 1,
        "sha256": "a" * 64,
        "digest": "b" * 64,
        "source_path": "models/scorecard.pkl",
        "model_key": "models/mdl/1.0.0/artifacts/art/model.pkl",
        "bento_tag": "scorecard:abc",
        "status": "active",
        "purge_attempts": 0,
    }
    values.update(overrides)
    return Artifact(**values)


def test_create_artifact() -> None:
    """验证创建 active 制品修订"""
    repository, _, _ = create_repository()

    artifact = repository.create_artifact(
        artifact_id="art_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        revision=2,
        sha256="a" * 64,
        digest="b" * 64,
        source_path="models/scorecard.pkl",
        model_key="models/mdl/1.0.0/artifacts/art/model.pkl",
        bento_tag="scorecard:abc",
        created_by="admin",
    )

    assert artifact.revision == 2
    assert artifact.status == "active"
    assert artifact.created_by == "admin"


@pytest.mark.asyncio
async def test_get_current_artifact() -> None:
    """验证查询当前生效制品"""
    expected = create_artifact()
    repository, execute, result = create_repository()
    result.scalar_one_or_none.return_value = expected

    artifact = await repository.get_current_artifact(
        expected.version_id,
        for_update=True,
    )

    assert artifact is expected
    execute.assert_awaited_once()


def test_artifact_lifecycle() -> None:
    """验证制品生命周期状态转换"""
    artifact = create_artifact()

    ArtifactRepository.retire_artifact(
        artifact,
        retired_by="admin",
    )
    assert artifact.status == "retired"
    assert artifact.retired_at is not None

    ArtifactRepository.request_purge(
        artifact,
        reason="超过保留期",
        requested_by="admin",
    )
    assert artifact.status == "purge_pending"
    assert artifact.purge_requested_at is not None

    ArtifactRepository.mark_purge_failed(
        artifact,
        error="storage unavailable",
    )
    assert artifact.status == "purge_failed"
    assert artifact.purge_attempts == 1

    ArtifactRepository.mark_purged(
        artifact,
        purged_by="admin",
    )
    assert artifact.status == "purged"
    assert artifact.purged_at is not None
    assert artifact.purge_attempts == 2
