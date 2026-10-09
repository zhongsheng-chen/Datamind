"""模型删除服务测试.

验证逻辑删除、恢复、永久清理和关键安全约束。

核心功能：
  - test_delete_version:
    验证逻辑删除模型版本
  - test_delete_model:
    验证逻辑删除模型及其版本
  - test_restore_version:
    验证恢复模型版本
  - test_restore_model:
    验证恢复模型及同批次版本
  - test_purge_records_partial_failure:
    验证记录部分清理失败
  - test_purge_deletes_storage_and_bento_artifacts:
    验证清理存储对象和 BentoML 模型
  - test_delete_version_rejects_active_deployment:
    验证存在活动部署时拒绝删除版本
  - test_purge_allows_missing_reason:
    验证永久清理原因可以省略
  - test_purge_rejects_loaded_runtime:
    验证存在已加载运行实例时拒绝永久清理
  - test_request_purge_builds_artifact_targets:
    验证持久化模型或版本清理请求
  - test_record_purge_result_updates_artifact:
    验证记录制品清理结果
  - test_restore_rejects_invalid_deletion_state:
    验证拒绝恢复状态不正确的模型或版本
  - test_restore_model_rejects_permanently_purged_versions:
    验证模型版本均已永久清理时拒绝恢复模型
  - test_delete_last_active_version_deactivates_model:
    测试删除最后一个激活版本时同步停用模型
  - test_purge_rejects_running_runtime:
    测试仍有已加载运行实例时拒绝永久清理
  - test_request_purge_requires_logical_deletion:
    测试永久清理要求目标已完成逻辑删除
  - test_request_purge_rejects_missing_artifacts:
    测试版本缺少制品记录时拒绝永久清理
  - test_record_purge_result_rejects_missing_artifact:
    测试清理结果找不到制品记录时抛出异常
  - test_restore_version_requires_restorable_artifact:
    测试恢复版本要求逻辑删除状态和完整当前制品
  - test_purge_ignores_absent_optional_objects:
    测试清理时忽略空 Schema 键和不存在的 BentoML 模型
"""

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.deletion as deleter_module
from datamind.db.models import Version
from datamind.models.errors import InvalidModelStateError
from datamind.services import ModelDeletionService


class FakeUnitOfWork:
    """删除服务测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def on_commit(self, _callback: object) -> None:
        """记录提交回调."""


def configure_repositories(
        monkeypatch: pytest.MonkeyPatch,
        *,
        metadata: object,
        version_record: object | None = None,
        versions: list[object] | None = None,
        artifact: object | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """配置删除服务仓储替身."""
    metadata_repo = MagicMock()
    version_repo = MagicMock()
    version_repo.get_version = AsyncMock(
        return_value=version_record
    )
    version_repo.list_versions = AsyncMock(
        return_value=versions or []
    )
    artifact_repo = MagicMock()
    artifact_repo.get_current_artifact = AsyncMock(
        return_value=artifact
    )
    deployment_repo = MagicMock()
    deployment_repo.list_active_deployments = AsyncMock(
        return_value=[]
    )
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(
        return_value=metadata
    )
    resolver.resolve_version = AsyncMock(
        return_value=version_record
    )

    monkeypatch.setitem(
        vars(deleter_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "ArtifactRepository",
        lambda _session: artifact_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "ModelResolver",
        lambda *_args, **_kwargs: resolver,
    )

    return (
        metadata_repo,
        version_repo,
        artifact_repo,
        deployment_repo,
    )


def mark_deleted(
        record: Any,
        **values: Any,
) -> Any:
    """更新测试对象的逻辑删除字段."""
    for field, value in values.items():
        setattr(
            record,
            field,
            value,
        )

    return record


@pytest.mark.asyncio
async def test_delete_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除没有活动部署的模型版本."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
    )
    version_record = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        version="1.0.0",
        deletion_id=None,
    )
    _, version_repo, _, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
    )
    version_repo.mark_deleted.side_effect = mark_deleted
    monkeypatch.setitem(
        vars(deleter_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_test",
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    result = await ModelDeletionService().delete(
        version_id="ver_test",
        reason="版本停用",
        operator="operator",
    )

    assert result["action"] == "delete_version"
    assert result["deletion_id"] == "del_test"
    version_repo.get_version.assert_awaited_once_with(
        "ver_test"
    )
    version_repo.mark_deleted.assert_called_once()


@pytest.mark.asyncio
async def test_delete_last_active_version_deactivates_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试删除最后一个激活版本时同步停用模型."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        status="active",
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        version="1.0.0",
        status="active",
        deletion_id=None,
    )
    _, version_repo, _, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
        versions=[version_record],
    )
    version_repo.mark_deleted.side_effect = mark_deleted
    monkeypatch.setitem(
        vars(deleter_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_test",
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    await ModelDeletionService().delete(
        model_id="mdl_test",
        version_id="ver_test",
        reason="版本停用",
        operator="operator",
    )

    assert metadata.status == "inactive"
    assert metadata.updated_by == "operator"
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        status=deleter_module.VersionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_delete_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除模型及其全部版本."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deletion_id=None,
    )
    versions = [
        SimpleNamespace(version_id="ver_1"),
        SimpleNamespace(version_id="ver_2"),
    ]
    metadata_repo, version_repo, _, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        versions=versions,
    )
    metadata_repo.mark_deleted.side_effect = mark_deleted
    version_repo.mark_deleted.side_effect = mark_deleted
    monkeypatch.setitem(
        vars(deleter_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_test",
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    result = await ModelDeletionService().delete(
        model_id="mdl_test",
        reason="模型停用",
        operator="operator",
    )

    assert result["action"] == "delete_model"
    assert result["version_count"] == 2
    assert version_repo.mark_deleted.call_count == 2
    metadata_repo.mark_deleted.assert_called_once()


@pytest.mark.asyncio
async def test_restore_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试恢复当前制品完整的模型版本."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=None,
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        version="1.0.0",
        deleted_at=object(),
    )
    artifact = SimpleNamespace(status="active")
    _, version_repo, _, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
        artifact=artifact,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    result = await ModelDeletionService().restore(
        model_id="mdl_test",
        version_id="ver_test",
        operator="operator",
    )

    assert result["action"] == "restore_version"
    version_repo.restore_version.assert_called_once_with(
        version_record,
        restored_by="operator",
    )


@pytest.mark.asyncio
async def test_restore_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试恢复模型及同一删除批次中的版本."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=object(),
        deletion_id="del_test",
    )
    matching_version = SimpleNamespace(
        version_id="ver_1",
        deleted_at=object(),
        deletion_id="del_test",
    )
    other_version = SimpleNamespace(
        version_id="ver_2",
        deleted_at=object(),
        deletion_id="del_other",
    )
    artifact = SimpleNamespace(status="active")
    metadata_repo, version_repo, _, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        versions=[matching_version, other_version],
        artifact=artifact,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    result = await ModelDeletionService().restore(
        model_id="mdl_test",
        operator="operator",
    )

    assert result["action"] == "restore_model"
    assert result["version_count"] == 1
    version_repo.restore_version.assert_called_once_with(
        matching_version,
        restored_by="operator",
    )
    metadata_repo.restore_model.assert_called_once_with(
        metadata,
        restored_by="operator",
    )


@pytest.mark.asyncio
async def test_restore_model_rejects_permanently_purged_versions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本均已永久清理时拒绝恢复模型."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=object(),
        deletion_id="del_model",
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        deleted_at=object(),
        deletion_id="del_model",
    )
    metadata_repo, version_repo, artifact_repo, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        versions=[version_record],
        artifact=None,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    with pytest.raises(
            InvalidModelStateError,
            match="相关模型版本的制品不存在或已永久清理",
    ):
        await ModelDeletionService().restore(
            model_id="mdl_test",
            operator="operator",
        )

    artifact_repo.get_current_artifact.assert_awaited_once_with(
        "ver_test"
    )
    version_repo.restore_version.assert_not_called()
    metadata_repo.restore_model.assert_not_called()


@pytest.mark.asyncio
async def test_purge_records_partial_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试永久清理继续处理并记录单个制品失败."""
    storage = MagicMock()
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        lambda: storage,
    )
    service = ModelDeletionService()
    targets = [
        SimpleNamespace(artifact_id="art_ok"),
        SimpleNamespace(artifact_id="art_failed"),
    ]
    request_purge = AsyncMock(
        return_value=(
            {
                "model_id": "mdl_test",
                "name": "scorecard",
            },
            targets,
        )
    )
    purge_artifact = MagicMock(
        side_effect=[
            None,
            OSError("storage unavailable"),
        ]
    )
    record_result = AsyncMock()
    monkeypatch.setattr(
        service,
        "_request_purge",
        request_purge,
    )
    monkeypatch.setattr(
        service,
        "_purge_artifact",
        purge_artifact,
    )
    monkeypatch.setattr(
        service,
        "_record_purge_result",
        record_result,
    )

    result = await service.purge(
        model_id="mdl_test",
        reason="超过保留期",
        operator="operator",
    )

    assert result["action"] == "purge_failed"
    assert result["artifact_count"] == 2
    assert result["purged_count"] == 1
    assert result["failed_count"] == 1
    assert result["errors"] == [{
        "artifact_id": "art_failed",
        "error": "storage unavailable",
    }]
    assert record_result.await_args_list[0].kwargs["error"] is None
    assert (
        record_result.await_args_list[1].kwargs["error"]
        == "storage unavailable"
    )


@pytest.mark.asyncio
async def test_purge_deletes_storage_and_bento_artifacts(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试永久清理删除全部存储对象和 BentoML 模型."""
    storage = MagicMock()
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        lambda: storage,
    )
    other_bento_model = SimpleNamespace(
        tag="scorecard:other"
    )
    bento_model = SimpleNamespace(tag="scorecard:old")
    list_models = MagicMock(
        return_value=[
            other_bento_model,
            bento_model,
        ]
    )
    delete_model = MagicMock()
    monkeypatch.setitem(
        vars(deleter_module),
        "bentoml",
        SimpleNamespace(
            models=SimpleNamespace(
                list=list_models,
                delete=delete_model,
            )
        ),
    )
    service = ModelDeletionService()
    target = SimpleNamespace(
        artifact_id="art_test",
        model_key="models/model.pkl",
        bento_tag="scorecard:old",
    )
    request_purge = AsyncMock(
        return_value=(
            {
                "model_id": "mdl_test",
                "name": "scorecard",
            },
            [target],
        )
    )
    record_result = AsyncMock()
    monkeypatch.setattr(
        service,
        "_request_purge",
        request_purge,
    )
    monkeypatch.setattr(
        service,
        "_record_purge_result",
        record_result,
    )

    result = await service.purge(
        model_id="mdl_test",
        reason="超过保留期",
        operator="operator",
    )

    assert result["action"] == "purge_completed"
    assert result["purged_count"] == 1
    list_models.assert_called_once_with()
    assert storage.delete_by_key.call_count == 1
    storage.delete_by_key.assert_any_call(
        key="models/model.pkl",
        strict=False,
    )
    delete_model.assert_called_once_with(
        bento_model.tag
    )
    record_result.assert_awaited_once_with(
        artifact_id="art_test",
        error=None,
        operator="operator",
    )


@pytest.mark.asyncio
async def test_delete_version_rejects_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝删除版本."""
    storage = MagicMock()
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(
        return_value=SimpleNamespace(
            model_id="mdl_test",
            name="scorecard",
        )
    )
    resolver.resolve_version = AsyncMock(
        return_value=SimpleNamespace(
            version_id="ver_test",
            version="1.0.0",
        )
    )
    deployment_repo = MagicMock()
    deployment_repo.list_active_deployments = AsyncMock(
        return_value=[SimpleNamespace(deployment_id="dep_test")]
    )

    monkeypatch.setitem(
        vars(deleter_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "MetadataRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "VersionRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "ModelResolver",
        lambda *_args, **_kwargs: resolver,
    )

    service = ModelDeletionService()

    with pytest.raises(InvalidModelStateError, match="活动部署"):
        await service.delete(
            model_id="mdl_test",
            version_id="ver_test",
        )

    storage.delete_by_key.assert_not_called()


@pytest.mark.asyncio
async def test_purge_allows_missing_reason(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试永久清理原因可以省略."""
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )
    service = ModelDeletionService()
    request_purge = AsyncMock(
        return_value=(
            {
                "model_id": "mdl_test",
                "name": "scorecard",
            },
            [],
        )
    )
    monkeypatch.setattr(
        service,
        "_request_purge",
        request_purge,
    )

    result = await service.purge(
        model_id="mdl_test",
        reason="  ",
    )

    request_purge.assert_awaited_once_with(
        model_id="mdl_test",
        name=None,
        version=None,
        version_id=None,
        reason=None,
        operator=None,
    )
    assert result["reason"] is None
    assert result["purged_count"] == 0


@pytest.mark.asyncio
async def test_purge_rejects_running_runtime() -> None:
    """测试仍有已加载运行实例时拒绝永久清理."""
    deployment_repo = MagicMock()
    deployment_repo.list_active_deployments = AsyncMock(return_value=[])
    runtime_repo = MagicMock()
    runtime_repo.list_runtimes = AsyncMock(
        return_value=[SimpleNamespace(status="running")]
    )

    with pytest.raises(InvalidModelStateError, match="运行实例"):
        await ModelDeletionService._ensure_purge_safe(
            deployment_repo,
            runtime_repo,
            model_id="mdl_test",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target_version",
    [
        False,
        True,
    ],
)
async def test_request_purge_builds_artifact_targets(
        monkeypatch: pytest.MonkeyPatch,
        target_version: bool,
) -> None:
    """测试持久化清理请求并忽略已清理制品."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=object(),
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        version="1.0.0",
        deleted_at=object(),
    )
    active_artifact = SimpleNamespace(
        artifact_id="art_active",
        status="active",
        model_key="models/model.pkl",
        bento_tag="scorecard:active",
    )
    purged_artifact = SimpleNamespace(
        artifact_id="art_purged",
        status="purged",
    )
    _, _, artifact_repo, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
        versions=[version_record],
    )
    artifact_repo.list_artifacts = AsyncMock(
        return_value=[
            purged_artifact,
            active_artifact,
        ]
    )
    runtime_repo = MagicMock()
    runtime_repo.list_runtimes = AsyncMock(
        return_value=[]
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "RuntimeRepository",
        lambda _session: runtime_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )
    service = ModelDeletionService()

    info, targets = await service._request_purge(
        model_id="mdl_test",
        name=None,
        version=None,
        version_id=(
            "ver_test"
            if target_version
            else None
        ),
        reason="超过保留期",
        operator="operator",
    )

    assert info["model_id"] == "mdl_test"
    assert info["already_purged_count"] == 1
    if target_version:
        assert info["version_id"] == "ver_test"
    else:
        assert info["version_count"] == 1
    assert len(targets) == 1
    assert targets[0].artifact_id == "art_active"
    assert targets[0].model_key == "models/model.pkl"
    artifact_repo.request_purge.assert_called_once_with(
        active_artifact,
        reason="超过保留期",
        requested_by="operator",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "target_version",
        "metadata_deleted_at",
        "version_deleted_at",
        "message",
    ),
    [
        (
            False,
            None,
            object(),
            "模型必须先逻辑删除",
        ),
        (
            True,
            object(),
            None,
            "模型版本必须先逻辑删除",
        ),
    ],
)
async def test_request_purge_requires_logical_deletion(
        monkeypatch: pytest.MonkeyPatch,
        target_version: bool,
        metadata_deleted_at: object | None,
        version_deleted_at: object | None,
        message: str,
) -> None:
    """测试永久清理要求目标已完成逻辑删除."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=metadata_deleted_at,
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        version="1.0.0",
        deleted_at=version_deleted_at,
    )
    configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "RuntimeRepository",
        MagicMock(),
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    with pytest.raises(InvalidModelStateError, match=message):
        await ModelDeletionService()._request_purge(
            model_id="mdl_test",
            name=None,
            version=None,
            version_id=(
                "ver_test"
                if target_version
                else None
            ),
            reason="超过保留期",
            operator="operator",
        )


@pytest.mark.asyncio
async def test_request_purge_rejects_missing_artifacts(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试版本缺少制品记录时拒绝永久清理."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=object(),
    )
    version_record = SimpleNamespace(
        version_id="ver_test",
        version="1.0.0",
        deleted_at=object(),
    )
    _, _, artifact_repo, _ = configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=version_record,
    )
    artifact_repo.list_artifacts = AsyncMock(
        return_value=[]
    )
    runtime_repo = MagicMock()
    runtime_repo.list_runtimes = AsyncMock(
        return_value=[]
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "RuntimeRepository",
        lambda _session: runtime_repo,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    with pytest.raises(InvalidModelStateError, match="缺少制品记录"):
        await ModelDeletionService()._request_purge(
            model_id="mdl_test",
            name=None,
            version=None,
            version_id="ver_test",
            reason="超过保留期",
            operator="operator",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        None,
        "storage unavailable",
    ],
)
async def test_record_purge_result_updates_artifact(
        monkeypatch: pytest.MonkeyPatch,
        error: str | None,
) -> None:
    """测试记录制品清理成功或失败状态."""
    artifact = SimpleNamespace(
        artifact_id="art_test"
    )
    repository = MagicMock()
    repository.get_artifact = AsyncMock(
        return_value=artifact
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "ArtifactRepository",
        lambda _session: repository,
    )

    await ModelDeletionService._record_purge_result(
        artifact_id="art_test",
        error=error,
        operator="operator",
    )

    if error is None:
        repository.mark_purged.assert_called_once_with(
            artifact,
            purged_by="operator",
        )
        repository.mark_purge_failed.assert_not_called()
    else:
        repository.mark_purge_failed.assert_called_once_with(
            artifact,
            error=error,
        )
        repository.mark_purged.assert_not_called()


@pytest.mark.asyncio
async def test_record_purge_result_rejects_missing_artifact(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试清理结果找不到制品记录时抛出异常."""
    repository = MagicMock()
    repository.get_artifact = AsyncMock(
        return_value=None
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "ArtifactRepository",
        lambda _session: repository,
    )

    with pytest.raises(RuntimeError, match="制品不存在"):
        await ModelDeletionService._record_purge_result(
            artifact_id="art_missing",
            error=None,
            operator="operator",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "target_version",
        "metadata_deleted_at",
        "message",
    ),
    [
        (
            False,
            None,
            "模型未被逻辑删除",
        ),
        (
            True,
            object(),
            "模型已被整体删除",
        ),
    ],
)
async def test_restore_rejects_invalid_deletion_state(
        monkeypatch: pytest.MonkeyPatch,
        target_version: bool,
        metadata_deleted_at: object | None,
        message: str,
) -> None:
    """测试拒绝恢复状态不正确的模型或版本."""
    metadata = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        deleted_at=metadata_deleted_at,
    )
    configure_repositories(
        monkeypatch,
        metadata=metadata,
        version_record=(
            SimpleNamespace(
                model_id="mdl_test",
                version_id="ver_test",
                version="1.0.0",
                deleted_at=object(),
            )
            if target_version
            else None
        ),
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        MagicMock(),
    )

    with pytest.raises(InvalidModelStateError, match=message):
        await ModelDeletionService().restore(
            model_id="mdl_test",
            version_id=(
                "ver_test"
                if target_version
                else None
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "deleted_at",
        "artifact",
        "message",
    ),
    [
        (
            None,
            SimpleNamespace(status="active"),
            "模型版本未被逻辑删除",
        ),
        (
            datetime.now(timezone.utc),
            None,
            "当前制品不存在",
        ),
    ],
)
async def test_restore_version_requires_restorable_artifact(
        deleted_at: datetime | None,
        artifact: object | None,
        message: str,
) -> None:
    """测试恢复版本要求逻辑删除状态和完整当前制品."""
    repository = MagicMock()
    repository.get_current_artifact = AsyncMock(
        return_value=artifact
    )
    version_record = Version(
        version_id="ver_test",
    )

    if deleted_at is not None:
        version_record.deleted_at = deleted_at

    with pytest.raises(InvalidModelStateError, match=message):
        await ModelDeletionService._ensure_version_restorable(
            repository,
            version_record,
        )


@pytest.mark.asyncio
async def test_purge_ignores_absent_optional_objects(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试清理时忽略空 Schema 键和不存在的 BentoML 模型."""
    storage = MagicMock()
    monkeypatch.setitem(
        vars(deleter_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(deleter_module),
        "bentoml",
        SimpleNamespace(
            models=SimpleNamespace(
                list=MagicMock(return_value=[]),
                delete=MagicMock(),
            )
        ),
    )
    target = SimpleNamespace(
        artifact_id="art_test",
        model_key="models/model.pkl",
        bento_tag="scorecard:missing",
    )
    service = ModelDeletionService()
    monkeypatch.setattr(
        service,
        "_request_purge",
        AsyncMock(
            return_value=(
                {"model_id": "mdl_test"},
                [target],
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_record_purge_result",
        AsyncMock(),
    )

    result = await service.purge(
        model_id="mdl_test",
        reason="超过保留期",
    )

    assert result["action"] == "purge_completed"
    storage.delete_by_key.assert_called_once_with(
        key="models/model.pkl",
        strict=False,
    )
