# tests/services/test_lifecycle.py

"""模型生命周期服务测试

验证模型和版本的激活、停用及活动部署保护。

核心功能：
  - test_activate_model: 验证激活模型
  - test_activate_model_version: 验证激活模型和指定版本
  - test_deactivate_model: 验证停用模型
  - test_deactivate_model_version: 验证停用指定版本
  - test_deactivate_rejects_model_with_active_deployment:
    验证存在活动部署时拒绝停用模型
  - test_deactivate_rejects_version_with_active_deployment:
    验证存在活动部署时拒绝停用版本
  - test_lifecycle_rejects_missing_model:
    验证激活和停用要求模型存在
  - test_lifecycle_rejects_missing_version:
    验证版本操作要求模型版本存在
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.lifecycle as lifecycle_module
from datamind.models.errors import InvalidModelStateError
from datamind.services import ModelLifecycleService


class FakeUnitOfWork:
    """生命周期服务测试工作单元"""

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
) -> tuple[MagicMock, MagicMock]:
    """配置生命周期服务仓储替身"""
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

    monkeypatch.setitem(
        vars(lifecycle_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "MetadataRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(lifecycle_module),
        "VersionRepository",
        lambda _session: MagicMock(),
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

    return resolver, deployment_repo


@pytest.mark.asyncio
async def test_activate_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型元数据"""
    resolver, _ = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
    )

    result = await ModelLifecycleService().activate(
        model_id="mdl_test",
        updated_by="operator",
    )

    model = resolver.resolve_model.return_value
    assert model.status == "active"
    assert model.updated_by == "operator"
    assert result["model_status"] == "active"
    assert result["version_id"] is None
    resolver.resolve_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_activate_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型元数据和指定版本"""
    resolver, _ = configure_repositories(
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
async def test_deactivate_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用没有活动部署的模型"""
    resolver, deployment_repo = configure_repositories(
        monkeypatch,
        deployments=[],
    )

    result = await ModelLifecycleService().deactivate(
        model_id="mdl_test",
        updated_by="operator",
    )

    model = resolver.resolve_model.return_value
    assert model.status == "inactive"
    assert model.updated_by == "operator"
    assert result["model_status"] == "inactive"
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test"
    )


@pytest.mark.asyncio
async def test_deactivate_model_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用没有活动部署的模型版本"""
    resolver, deployment_repo = configure_repositories(
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
    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
    )


@pytest.mark.asyncio
async def test_deactivate_rejects_model_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝停用模型"""
    _, deployment_repo = configure_repositories(monkeypatch)

    with pytest.raises(InvalidModelStateError, match="活动部署"):
        await ModelLifecycleService().deactivate(model_id="mdl_test")

    deployment_repo.list_active_deployments.assert_awaited_once_with(
        model_id="mdl_test"
    )


@pytest.mark.asyncio
async def test_deactivate_rejects_version_with_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存在活动部署时拒绝停用版本"""
    resolver, deployment_repo = configure_repositories(monkeypatch)

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
    """测试激活和停用不存在的模型时报错"""
    resolver, _ = configure_repositories(
        monkeypatch,
        deployments=[],
    )
    resolver.resolve_model.return_value = None
    service = ModelLifecycleService()

    with pytest.raises(ValueError, match="模型不存在"):
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
    """测试激活和停用不存在的模型版本时报错"""
    resolver, _ = configure_repositories(
        monkeypatch,
        model_status="inactive",
        deployments=[],
    )
    resolver.resolve_version.return_value = None
    service = ModelLifecycleService()

    with pytest.raises(ValueError, match="模型版本不存在"):
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
