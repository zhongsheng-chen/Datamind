"""模型生命周期服务测试.

验证模型和版本的激活、停用及活动部署保护。

核心功能：
  - test_activate_model:
    验证激活模型及其 inactive 版本
  - test_activate_model_requires_available_version:
    验证模型激活要求存在可用版本
  - test_activate_model_version:
    验证激活模型和指定版本
  - test_activate_audit_records_only_status_changes:
    验证审计仅记录实际状态变化
  - test_activate_rejects_archived_version:
    验证归档版本按非法状态迁移拒绝激活
  - test_deactivate_model:
    验证停用模型及其 active 版本
  - test_deactivate_model_version:
    验证停用指定版本
  - test_deactivate_version_keeps_model_with_other_active_version:
    验证仍有激活版本时保持模型激活
  - test_deactivate_rejects_model_with_active_deployment:
    验证存在活动部署时拒绝停用模型
  - test_deactivate_rejects_version_with_active_deployment:
    验证存在活动部署时拒绝停用版本
  - test_deprecate_model:
    验证弃用模型及其可弃用版本
  - test_deprecate_model_version:
    验证弃用指定模型版本
  - test_deprecate_version_keeps_model_with_other_active_version:
    验证仍有激活版本时保持模型激活
  - test_deprecate_rejects_version_with_active_deployment:
    验证存在活动部署时拒绝弃用版本
  - test_deprecate_rejects_model_with_active_deployment:
    验证存在活动部署时拒绝弃用模型
  - test_lifecycle_rejects_missing_model:
    验证激活和停用要求模型存在
  - test_lifecycle_rejects_missing_version:
    验证版本操作要求模型版本存在
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.lifecycle as lifecycle_module
from datamind.models.errors import (
    InvalidModelStateError,
    ModelNotFoundError,
    VersionNotFoundError,
)
from datamind.services import ModelLifecycleService
from datamind.services.mutation import MutationResult


class FakeUnitOfWork:
    """生命周期服务测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def configure_repositories(
        monkeypatch: pytest.MonkeyPatch,
        *,
        model_status: str = "active",
        version_status: str = "active",
        deployments: list[object] | None = None,
        active_versions: list[object] | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """配置生命周期服务仓储替身."""
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(
        return_value=SimpleNamespace(
            model_id="mdl_test",
            name="scorecard",
            status=model_status,
        )
    )
    resolver.resolve_version = AsyncMock(
        return_value=SimpleNamespace(
            version_id="ver_test",
            version="1.0.0",
            status=version_status,
        )
    )
    deployment_repo = MagicMock()
    deployment_repo.list_active_deployments = AsyncMock(
        return_value=(
            deployments
            if deployments is not None
            else [SimpleNamespace(deployment_id="dep_test")]
        )
    )
    version_repo = MagicMock()
    version_repo.get_version = AsyncMock(
        return_value=SimpleNamespace(
            version_id="ver_test",
            model_id="mdl_test",
            version="1.0.0",
            status=version_status,
        )
    )
    version_repo.list_versions = AsyncMock(
        return_value=(
            active_versions
            if active_versions is not None
            else [resolver.resolve_version.return_value]
        )
    )

    def deprecate_version(
            version_record: SimpleNamespace,
            *,
            updated_by: str | None = None,
    ) -> SimpleNamespace:
        version_record.status = "deprecated"
        version_record.updated_by = updated_by
        return version_record

    version_repo.deprecate_version.side_effect = (
        deprecate_version
    )
    metadata_repo = MagicMock()
    resolver.metadata_repo = metadata_repo

    monkeypatch.setitem(
        vars(lifecycle_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "ModelResolver",
        lambda **_kwargs: resolver,
    )

    return resolver, deployment_repo, version_repo


@pytest.mark.asyncio
async def test_activate_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型及其全部 inactive 版本."""
    inactive_versions = [
        SimpleNamespace(
            version_id="ver_first",
            status="inactive",
            updated_by=None,
        ),
        SimpleNamespace(
            version_id="ver_second",
            status="inactive",
            updated_by=None,
        ),
    ]
    resolver, _, version_repo = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
        active_versions=inactive_versions,
    )

    result = await ModelLifecycleService().activate(
        model_id="mdl_test",
        updated_by="operator",
    )

    model = resolver.resolve_model.return_value
    assert model.status == "active"
    assert model.updated_by == "operator"
    assert result["model_status"] == "active"
    assert result["activated_version_count"] == 2
    assert isinstance(result, MutationResult)
    assert result.before == {
        "model_status": "inactive",
        "versions": [
            {"version_id": "ver_first", "status": "inactive"},
            {"version_id": "ver_second", "status": "inactive"},
        ],
    }
    assert result.after == {
        "model_status": "active",
        "versions": [
            {"version_id": "ver_first", "status": "active"},
            {"version_id": "ver_second", "status": "active"},
        ],
    }
    assert all(
        version_record.status == "active"
        for version_record in inactive_versions
    )
    assert all(
        version_record.updated_by == "operator"
        for version_record in inactive_versions
    )
    resolver.resolve_version.assert_not_awaited()
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        status=lifecycle_module.VersionStatus.INACTIVE,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model_status", ["inactive", "active"])
@pytest.mark.parametrize("version_status", ["inactive", "active"])
async def test_activate_audit_records_only_status_changes(
        monkeypatch: pytest.MonkeyPatch,
        model_status: str,
        version_status: str,
) -> None:
    """测试指定版本激活及重复激活的状态审计."""
    configure_repositories(
        monkeypatch,
        model_status=model_status,
        version_status=version_status,
        deployments=[],
    )
    result = await ModelLifecycleService().activate(
        model_id="mdl_test", version_id="ver_test",
    )
    before = {}
    after = {}
    if model_status == "inactive":
        before["model_status"] = "inactive"
        after["model_status"] = "active"
    if version_status == "inactive":
        before["versions"] = [{"version_id": "ver_test", "status": "inactive"}]
        after["versions"] = [{"version_id": "ver_test", "status": "active"}]
    assert result.before == before
    assert result.after == after
    assert result["activated_version_count"] == int(version_status == "inactive")


@pytest.mark.asyncio
async def test_activate_model_requires_available_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试没有 inactive 或 active 版本时拒绝激活模型."""
    resolver, _, version_repo = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
        active_versions=[],
    )

    with pytest.raises(
        InvalidModelStateError,
        match="没有可激活版本",
    ):
        await ModelLifecycleService().activate(
            model_id="mdl_test",
        )

    assert resolver.resolve_model.return_value.status == "inactive"
    assert version_repo.list_versions.await_count == 2
    version_repo.list_versions.assert_any_await(
        model_id="mdl_test",
        status=lifecycle_module.VersionStatus.INACTIVE,
    )
    version_repo.list_versions.assert_any_await(
        model_id="mdl_test",
        status=lifecycle_module.VersionStatus.ACTIVE,
        limit=1,
    )


@pytest.mark.asyncio
async def test_activate_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型元数据和指定版本."""
    resolver, _, _ = configure_repositories(
        monkeypatch,
        model_status="inactive",
        version_status="inactive",
        deployments=[],
    )

    result = await ModelLifecycleService().activate(
        model_id="mdl_test",
        version_id="ver_test",
        updated_by="operator",
    )

    model = resolver.resolve_model.return_value
    version_record = resolver.resolve_version.return_value
    assert model.status == "active"
    assert version_record.status == "active"
    assert version_record.updated_by == "operator"
    assert result["version_id"] == "ver_test"
    assert result["version_status"] == "active"


@pytest.mark.asyncio
async def test_activate_model_version_by_version_id(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试仅凭版本 ID 激活模型版本."""
    resolver, _, version_repo = configure_repositories(
        monkeypatch,
        model_status="inactive",
        version_status="inactive",
        deployments=[],
    )

    result = await ModelLifecycleService().activate(
        version_id="ver_test",
        updated_by="operator",
    )

    version_record = version_repo.get_version.return_value
    version_repo.get_version.assert_awaited_once_with(
        "ver_test"
    )
    resolver.resolve_model.assert_awaited_once_with(
        model_id="mdl_test",
    )
    resolver.resolve_version.assert_not_awaited()
    assert version_record.status == "active"
    assert version_record.updated_by == "operator"
    assert result["model_id"] == "mdl_test"
    assert result["version_id"] == "ver_test"
    assert result["version_status"] == "active"


@pytest.mark.asyncio
async def test_activate_rejects_archived_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试归档版本按非法状态迁移拒绝激活."""
    resolver, _, _ = configure_repositories(
        monkeypatch,
        model_status="active",
        version_status="archived",
        deployments=[],
    )

    with pytest.raises(
        InvalidModelStateError,
        match="archived.*active",
    ):
        await ModelLifecycleService().activate(
            model_id="mdl_test",
            version="1.0.0",
        )

    resolver.resolve_version.assert_awaited_once_with(
        model_id="mdl_test",
        version="1.0.0",
        version_id=None,
    )


@pytest.mark.asyncio
async def test_deactivate_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用没有活动部署的模型及其 active 版本."""
    other_version = SimpleNamespace(
        version_id="ver_other",
        status="active",
        updated_by=None,
    )
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        deployments=[],
        active_versions=[
            other_version,
            SimpleNamespace(
                version_id="ver_test",
                status="active",
                updated_by=None,
            ),
        ],
    )

    result = await ModelLifecycleService().deactivate(
        model_id="mdl_test",
        updated_by="operator",
    )

    model = resolver.resolve_model.return_value
    assert model.status == "inactive"
    assert model.updated_by == "operator"
    assert result["model_status"] == "inactive"
    assert result["deactivated_version_count"] == 2
    active_versions = version_repo.list_versions.return_value
    assert all(
        version_record.status == "inactive"
        for version_record in active_versions
    )
    assert all(
        version_record.updated_by == "operator"
        for version_record in active_versions
    )
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test"
    )
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        status=lifecycle_module.VersionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_deactivate_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用没有活动部署的模型版本."""
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        deployments=[],
    )

    result = await ModelLifecycleService().deactivate(
        model_id="mdl_test",
        version_id="ver_test",
        updated_by="operator",
    )

    version_record = resolver.resolve_version.return_value
    assert version_record.status == "inactive"
    assert version_record.updated_by == "operator"
    assert result["version_id"] == "ver_test"
    assert result["version_status"] == "inactive"
    assert resolver.resolve_model.return_value.status == "inactive"
    assert result["model_status"] == "inactive"
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        status=lifecycle_module.VersionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_deactivate_version_keeps_model_with_other_active_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用版本后仍有激活版本时保持模型激活."""
    other_version = SimpleNamespace(
        version_id="ver_other",
        status="active",
    )
    resolver, _, _ = configure_repositories(
        monkeypatch,
        deployments=[],
        active_versions=[other_version],
    )

    result = await ModelLifecycleService().deactivate(
        model_id="mdl_test",
        version_id="ver_test",
        updated_by="operator",
    )

    assert resolver.resolve_model.return_value.status == "active"
    assert result["model_status"] == "active"


@pytest.mark.asyncio
async def test_deprecate_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试弃用模型及其 active、inactive 版本."""
    active_version = SimpleNamespace(
        version_id="ver_active",
        version="2.0.0",
        status="active",
    )
    inactive_version = SimpleNamespace(
        version_id="ver_inactive",
        version="1.0.0",
        status="inactive",
    )
    deprecated_version = SimpleNamespace(
        version_id="ver_deprecated",
        version="0.9.0",
        status="deprecated",
    )
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
        active_versions=[
            active_version,
            inactive_version,
            deprecated_version,
        ],
    )

    result = await ModelLifecycleService().deprecate(
        model_id="mdl_test",
        updated_by="operator",
    )

    assert resolver.resolve_model.return_value.status == "deprecated"
    assert active_version.status == "deprecated"
    assert inactive_version.status == "deprecated"
    assert deprecated_version.status == "deprecated"
    assert result["model_status"] == "deprecated"
    assert result["version_id"] is None
    assert result["deprecated_version_count"] == 2
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
    )
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
    )
    assert version_repo.deprecate_version.call_count == 2


@pytest.mark.asyncio
async def test_deprecate_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试弃用最后一个 active 版本时同时停用模型."""
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        deployments=[],
    )

    result = await ModelLifecycleService().deprecate(
        model_id="mdl_test",
        version_id="ver_test",
        updated_by="operator",
    )

    version_record = resolver.resolve_version.return_value
    assert version_record.status == "deprecated"
    assert version_record.updated_by == "operator"
    assert result["version_status"] == "deprecated"
    assert result["deprecated_version_count"] == 1
    assert resolver.resolve_model.return_value.status == "inactive"
    assert result["model_status"] == "inactive"
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )
    version_repo.deprecate_version.assert_called_once_with(
        version_record,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_deprecate_version_keeps_model_with_other_active_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试弃用版本后仍有 active 版本时保持模型激活."""
    other_version = SimpleNamespace(
        version_id="ver_other",
        status="active",
    )
    resolver, _, _ = configure_repositories(
        monkeypatch,
        deployments=[],
        active_versions=[other_version],
    )

    result = await ModelLifecycleService().deprecate(
        model_id="mdl_test",
        version_id="ver_test",
        updated_by="operator",
    )

    assert resolver.resolve_model.return_value.status == "active"
    assert result["model_status"] == "active"


@pytest.mark.asyncio
async def test_archive_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试归档未激活的模型版本."""
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        version_status="inactive",
        deployments=[],
    )

    def archive_version(
            version_record: SimpleNamespace,
            *,
            updated_by: str | None = None,
    ) -> SimpleNamespace:
        version_record.status = "archived"
        version_record.updated_by = updated_by
        return version_record

    version_repo.archive_version.side_effect = archive_version
    result = await ModelLifecycleService().archive(
        version_id="ver_test",
        updated_by="operator",
    )

    assert result["version_status"] == "archived"
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )
    version_repo.archive_version.assert_called_once_with(
        version_repo.get_version.return_value,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_archive_model_and_remaining_versions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试归档模型时级联归档尚未归档的版本."""
    versions = [
        SimpleNamespace(version_id="ver_inactive", status="inactive"),
        SimpleNamespace(version_id="ver_deprecated", status="deprecated"),
        SimpleNamespace(version_id="ver_archived", status="archived"),
    ]
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
        active_versions=versions,
    )
    metadata_repo = resolver.metadata_repo

    def archive_version(
            version_record: SimpleNamespace,
            *,
            updated_by: str,
    ) -> SimpleNamespace:
        version_record.status = "archived"
        version_record.updated_by = updated_by
        return version_record

    def archive_model(
            model_record: SimpleNamespace,
            *,
            updated_by: str,
    ) -> SimpleNamespace:
        model_record.status = "archived"
        model_record.updated_by = updated_by
        return model_record

    version_repo.archive_version.side_effect = archive_version
    metadata_repo.archive_model.side_effect = archive_model

    result = await ModelLifecycleService().archive(
        model_id="mdl_test",
        updated_by="operator",
    )

    assert result["model_status"] == "archived"
    assert result["archived_version_count"] == 2
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
    )
    assert version_repo.archive_version.call_count == 2
    metadata_repo.archive_model.assert_called_once_with(
        resolver.resolve_model.return_value,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_deprecate_rejects_version_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝弃用模型版本."""
    resolver, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
    )

    with pytest.raises(
        InvalidModelStateError,
        match="活动部署",
    ):
        await ModelLifecycleService().deprecate(
            model_id="mdl_test",
            version_id="ver_test",
        )

    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )
    version_repo.deprecate_version.assert_not_called()
    assert resolver.resolve_version.return_value.status == "active"


@pytest.mark.asyncio
async def test_deprecate_rejects_model_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝弃用模型."""
    _, deployment_repo, version_repo = configure_repositories(
        monkeypatch,
    )

    with pytest.raises(
            InvalidModelStateError,
            match="活动部署",
    ):
        await ModelLifecycleService().deprecate(
            model_id="mdl_test",
        )

    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
    )
    version_repo.list_versions.assert_not_awaited()
    version_repo.deprecate_version.assert_not_called()


@pytest.mark.asyncio
async def test_deactivate_rejects_model_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝停用模型."""
    _, deployment_repo, _ = configure_repositories(monkeypatch)

    with pytest.raises(InvalidModelStateError, match="活动部署"):
        await ModelLifecycleService().deactivate(model_id="mdl_test")

    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test"
    )


@pytest.mark.asyncio
async def test_deactivate_rejects_version_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝停用版本."""
    resolver, deployment_repo, _ = configure_repositories(monkeypatch)

    with pytest.raises(InvalidModelStateError, match="活动部署"):
        await ModelLifecycleService().deactivate(
            model_id="mdl_test",
            version_id="ver_test",
        )

    resolver.resolve_version.assert_awaited_once()
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "activate",
        "deactivate",
    ],
)
async def test_lifecycle_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
        operation: str,
) -> None:
    """测试激活和停用不存在的模型时报错."""
    resolver, _, _ = configure_repositories(
        monkeypatch,
        deployments=[],
    )
    resolver.resolve_model.side_effect = ModelNotFoundError(
        "模型不存在"
    )
    service = ModelLifecycleService()

    with pytest.raises(ModelNotFoundError, match="模型不存在"):
        if operation == "activate":
            await service.activate(
                model_id="mdl_missing"
            )
        else:
            await service.deactivate(
                model_id="mdl_missing"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "activate",
        "deactivate",
    ],
)
async def test_lifecycle_rejects_missing_version(
        monkeypatch: pytest.MonkeyPatch,
        operation: str,
) -> None:
    """测试激活和停用不存在的模型版本时报错."""
    resolver, _, _ = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
    )
    resolver.resolve_version.side_effect = VersionNotFoundError(
        "模型版本不存在"
    )
    service = ModelLifecycleService()

    with pytest.raises(VersionNotFoundError, match="模型版本不存在"):
        if operation == "activate":
            await service.activate(
                model_id="mdl_test",
                version_id="ver_missing",
            )
        else:
            await service.deactivate(
                model_id="mdl_test",
                version_id="ver_missing",
            )
