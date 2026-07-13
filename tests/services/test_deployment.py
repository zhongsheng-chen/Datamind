# tests/services/test_deployment.py

"""模型部署生命周期服务测试

验证部署创建、启用、禁用、运行控制同步和配置校验。

核心功能：
  - test_create_deployment_passes_normalized_values:
    验证创建部署及参数传递
  - test_create_deployment_rejects_missing_model: 验证模型不存在
  - test_create_deployment_rejects_missing_version: 验证版本不存在
  - test_create_deployment_rejects_invalid_environment: 验证非法环境
  - test_validate_config_accepts_supported_tasks:
    验证分类和评分配置
  - test_validate_config_rejects_unsupported_task:
    验证拒绝不支持的任务类型
  - test_validate_config_wraps_validation_error:
    验证统一转换配置校验异常
  - test_enable_deployment_activates_valid_deployment:
    验证启用有效部署
  - test_enable_rejects_missing_deployment: 验证部署不存在
  - test_enable_rejects_inactive_version: 验证版本未激活
  - test_disable_sets_runtime_control_unloaded: 验证禁用并卸载
  - test_disable_creates_runtime_control: 验证首次禁用创建控制记录
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

import datamind.services.deployment as deployment_module
from datamind.constants import Environment
from datamind.models.errors import (
    DeploymentError,
    DeploymentNotFoundError,
    InvalidModelStateError,
)
from datamind.services import DeploymentLifecycleService


class FakeUnitOfWork:
    """部署服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_deployment(*, status: str = "inactive") -> SimpleNamespace:
    """创建部署测试对象"""
    return SimpleNamespace(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        environment="production",
        rollout_type="full",
        role="champion",
        status=status,
    )


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        deployment: object | None = None,
        model_status: str = "active",
        version_status: str = "active",
        task_type: str = "classification",
        model_exists: bool = True,
        version_exists: bool = True,
        control: object | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """配置部署服务依赖替身"""
    model = (
        SimpleNamespace(
            model_id="mdl_test",
            status=model_status,
            task_type=task_type,
            framework="sklearn",
        )
        if model_exists
        else None
    )
    version = (
        SimpleNamespace(
            version_id="ver_test",
            model_id="mdl_test",
            status=version_status,
        )
        if version_exists
        else None
    )
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=deployment
    )
    deployment_repo.create_deployment.return_value = (
        deployment or create_deployment()
    )
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(return_value=model)
    resolver.resolve_version = AsyncMock(return_value=version)
    control_repo = MagicMock()
    control_repo.get_deployment_control = AsyncMock(
        return_value=control
    )

    monkeypatch.setitem(
        vars(deployment_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "MetadataRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "VersionRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "ControlRepository",
        lambda _session: control_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "ModelResolver",
        lambda **_kwargs: resolver,
    )

    return deployment_repo, control_repo, resolver


@pytest.mark.asyncio
async def test_create_deployment_passes_normalized_values(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建部署并向仓储传递规范化参数"""
    deployment_repo, _, resolver = configure_service(
        monkeypatch,
    )

    result = await DeploymentLifecycleService().create_deployment(
        model_id="mdl_test",
        version_id="ver_test",
        environment="production",
        config={"threshold": 0.5},
        description="分类部署",
        deployed_by="operator",
    )

    assert result["deployment_id"] == "dep_test"
    resolver.resolve_model.assert_awaited_once_with(
        model_id="mdl_test",
        name=None,
    )
    deployment_repo.create_deployment.assert_called_once_with(
        deployment_id=ANY,
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        environment=Environment.PRODUCTION,
        rollout_type="full",
        role="champion",
        config={"threshold": 0.5},
        description="分类部署",
        deployed_by="operator",
    )


@pytest.mark.asyncio
async def test_create_deployment_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝创建部署"""
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test"
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_create_deployment_rejects_missing_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本不存在时拒绝创建部署"""
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        version_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型版本不存在"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test",
            version_id="ver_test",
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_create_deployment_rejects_invalid_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝未知部署环境"""
    deployment_repo, _, _ = configure_service(monkeypatch)

    with pytest.raises(ValueError, match="not a valid Environment"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test",
            version_id="ver_test",
            environment="unknown",
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.parametrize(
    ("task_type", "config"),
    [
        ("classification", {"threshold": 0.5}),
        (
            "scoring",
            {
                "base_score": 600.0,
                "base_odds": 50.0,
                "pdo": 20.0,
                "min_score": 0,
                "max_score": 1000,
            },
        ),
    ],
)
def test_validate_config_accepts_supported_tasks(
        task_type: str,
        config: dict[str, Any],
) -> None:
    """测试接受合法的分类和评分配置"""
    DeploymentLifecycleService._validate_config(
        task_type=task_type,
        config=config,
    )


def test_validate_config_rejects_unsupported_task() -> None:
    """测试有配置时拒绝未知任务类型"""
    with pytest.raises(DeploymentError, match="不支持的任务类型"):
        DeploymentLifecycleService._validate_config(
            task_type="unknown",
            config={"value": 1},
        )


def test_validate_config_wraps_validation_error() -> None:
    """测试将配置模型校验异常转换为部署异常"""
    with pytest.raises(DeploymentError, match="配置校验失败"):
        DeploymentLifecycleService._validate_config(
            task_type="classification",
            config={
                "threshold": 2.0,
            },
        )


@pytest.mark.asyncio
async def test_enable_deployment_activates_valid_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用满足条件的部署"""
    deployment = create_deployment()
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        deployment=deployment,
    )

    result = await DeploymentLifecycleService().enable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    assert result["deployment_id"] == "dep_test"
    deployment_repo.activate_deployment.assert_called_once_with(
        deployment,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_enable_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用不存在的部署时报错"""
    deployment_repo, _, _ = configure_service(monkeypatch)

    with pytest.raises(DeploymentNotFoundError, match="部署不存在"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_missing"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_enable_rejects_inactive_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非活动版本不能启用部署"""
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        version_status="inactive",
    )

    with pytest.raises(InvalidModelStateError, match="版本未激活"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_enable_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝启用部署"""
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_disable_sets_runtime_control_unloaded(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试禁用部署同步请求 Worker 卸载模型"""
    deployment = create_deployment(status="active")
    control = SimpleNamespace(
        desired_status="loaded",
        generation=1,
    )
    deployment_repo, control_repo, _ = configure_service(
        monkeypatch,
        deployment=deployment,
        control=control,
    )

    await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    deployment_repo.deactivate_deployment.assert_called_once_with(
        deployment,
        updated_by="operator",
    )
    control_repo.set_unloaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_disable_creates_runtime_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次禁用部署时创建 unloaded 控制记录"""
    deployment = create_deployment(status="active")
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=deployment,
    )

    await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    control_repo.create_control.assert_called_once_with(
        control_id=ANY,
        deployment_id="dep_test",
        environment=Environment.PRODUCTION,
        created_by="operator",
    )
    control_repo.set_unloaded.assert_not_called()


@pytest.mark.asyncio
async def test_disable_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试禁用不存在的部署时报错"""
    deployment_repo, _, _ = configure_service(
        monkeypatch
    )

    with pytest.raises(DeploymentNotFoundError, match="部署不存在"):
        await DeploymentLifecycleService().disable_deployment(
            deployment_id="dep_missing"
        )

    deployment_repo.deactivate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_disable_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝禁用部署"""
    deployment_repo, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="active"),
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().disable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.deactivate_deployment.assert_not_called()
