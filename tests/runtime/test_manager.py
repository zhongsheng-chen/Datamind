# tests/runtime/test_manager.py

"""运行时管理器测试

验证模型加载、卸载、查询、错误处理、并发单飞和重载失败回退能力。

核心功能：
  - test_concurrent_load_requests_load_model_once:
    验证并发请求只加载一次模型
  - test_failed_reload_preserves_previous_runtime:
    验证重载失败时保留原运行模型
  - test_load_returns_loaded_runtime_without_reloading:
    验证重复加载直接返回已有运行模型
  - test_load_validates_deployment_artifact:
    验证加载前校验部署与模型制品
  - test_failed_initial_load_marks_runtime_failed:
    验证首次加载失败时记录失败状态
  - test_load_creates_missing_runtime_record:
    验证加载时创建缺失的运行记录
  - test_unload_unregisters_model_and_marks_runtime_unloaded:
    验证卸载时注销模型并更新运行状态
  - test_unload_ignores_missing_runtime_record:
    验证卸载时忽略缺失的运行记录
  - test_reload_forces_model_reload:
    验证重载操作强制重新加载模型
  - test_get_status_combines_memory_and_database_state:
    验证运行状态合并内存与数据库信息
  - test_get_status_returns_empty_runtime_state:
    验证缺少运行记录时返回空状态
  - test_manager_rejects_empty_deployment_id:
    验证运行时管理器拒绝空部署 ID
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.runtime.manager as manager_module
from datamind.constants import Framework
from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    ModelNotFoundError,
    RuntimeRouteError,
    VersionNotFoundError,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.registry import RuntimeRegistry


class FakeUnitOfWork:
    """运行时管理器测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def configure_manager(
        monkeypatch: pytest.MonkeyPatch,
        *,
        loader: MagicMock,
) -> tuple[
    RuntimeManager,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    """配置运行时管理器及仓储替身"""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            deployment_id="dep_test",
            model_id="mdl_test",
            version_id="ver_test",
            framework="sklearn",
            environment="production",
            rollout_type="full",
            role="champion",
            config=None,
            status="active",
        )
    )
    metadata_repo = MagicMock()
    metadata_repo.get_model = AsyncMock(
        return_value=SimpleNamespace(
            model_type="logistic_regression",
            task_type="scoring",
        )
    )
    version_repo = MagicMock()
    version_repo.get_version = AsyncMock(
        return_value=SimpleNamespace(
            bento_tag="scorecard:test",
            model_path=None,
            model_key="models/mdl_test/1.0.0/model.pkl",
        )
    )
    runtime = SimpleNamespace(runtime_id="rtm_test")
    runtime_repo = MagicMock()
    runtime_repo.get_deployment_runtime = AsyncMock(return_value=runtime)

    monkeypatch.setitem(
        vars(manager_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(manager_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(manager_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(manager_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(manager_module),
        "RuntimeRepository",
        lambda _session: runtime_repo,
    )

    return (
        RuntimeManager(
            loader=loader,
            registry=RuntimeRegistry(),
            worker_id="worker_test",
        ),
        runtime_repo,
        deployment_repo,
        metadata_repo,
        version_repo,
    )


@pytest.mark.asyncio
async def test_concurrent_load_requests_load_model_once(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试并发请求只加载一次模型"""
    loader = MagicMock()
    loader.load.return_value = object()
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=loader,
    )

    first, second = await asyncio.gather(
        manager.load("dep_test"),
        manager.load("dep_test"),
    )

    assert first is second
    loader.load.assert_called_once_with(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl_test/1.0.0/model.pkl",
    )
    runtime_repo.mark_running.assert_called_once()


@pytest.mark.asyncio
async def test_failed_reload_preserves_previous_runtime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重载失败时继续保留旧模型"""
    loader = MagicMock()
    loader.load.side_effect = RuntimeError("invalid new model")
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=loader,
    )
    previous = manager.registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_old",
        framework="sklearn",
        model=object(),
    )

    with pytest.raises(BackendError, match="模型加载失败"):
        await manager.reload("dep_test")

    assert manager.registry.get("dep_test", touch=False) is previous
    runtime_repo.mark_failed.assert_not_called()
    runtime_repo.mark_running.assert_called_once()


@pytest.mark.asyncio
async def test_load_returns_loaded_runtime_without_reloading(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已加载部署直接返回内存运行时模型"""
    loader = MagicMock()
    manager, _, deployment_repo, _, _ = configure_manager(
        monkeypatch,
        loader=loader,
    )
    existing = manager.registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
    )

    result = await manager.load("dep_test")

    assert result is existing
    loader.load.assert_not_called()
    deployment_repo.get_deployment.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository", "value", "error_type", "message"),
    [
        ("deployment", None, DeploymentNotFoundError, "部署不存在"),
        (
            "deployment_status",
            "inactive",
            InvalidDeploymentStateError,
            "部署不是启用状态",
        ),
        ("metadata", None, ModelNotFoundError, "模型元数据不存在"),
        ("version", None, VersionNotFoundError, "版本不存在"),
        ("model_key", None, VersionNotFoundError, "缺少模型制品存储键"),
        ("bento_tag", None, VersionNotFoundError, "缺少 BentoML 模型标签"),
    ],
)
async def test_load_validates_deployment_artifact(
        monkeypatch: pytest.MonkeyPatch,
        repository: str,
        value: object | None,
        error_type: type[Exception],
        message: str,
) -> None:
    """测试加载前校验部署、模型和版本制品"""
    loader = MagicMock()
    manager, _, deployment_repo, metadata_repo, version_repo = (
        configure_manager(
            monkeypatch,
            loader=loader,
        )
    )

    if repository == "deployment":
        deployment_repo.get_deployment.return_value = value
    elif repository == "deployment_status":
        deployment_repo.get_deployment.return_value.status = value
    elif repository == "metadata":
        metadata_repo.get_model.return_value = value
    elif repository == "version":
        version_repo.get_version.return_value = value
    elif repository == "model_key":
        version_repo.get_version.return_value.model_key = value
    else:
        version_repo.get_version.return_value.bento_tag = value

    with pytest.raises(
            error_type,
            match=message,
    ):
        await manager.load("dep_test")

    loader.load.assert_not_called()


@pytest.mark.asyncio
async def test_failed_initial_load_marks_runtime_failed(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次加载失败时标记运行记录失败"""
    loader = MagicMock()
    loader.load.side_effect = RuntimeError("invalid model")
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=loader,
    )

    with pytest.raises(
            BackendError,
            match="模型加载失败",
    ):
        await manager.load("dep_test")

    assert "dep_test" not in manager.registry
    runtime_repo.mark_failed.assert_called_once()
    runtime_repo.mark_running.assert_not_called()


@pytest.mark.asyncio
async def test_load_creates_missing_runtime_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试加载时创建缺失的运行记录"""
    loader = MagicMock()
    loader.load.return_value = object()
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=loader,
    )
    created = SimpleNamespace(
        runtime_id="rtm_created",
    )
    runtime_repo.get_deployment_runtime.side_effect = [
        None,
        created,
    ]
    runtime_repo.create_runtime.return_value = created
    monkeypatch.setitem(
        vars(manager_module),
        "generate_random_id",
        lambda **_kwargs: "rtm_created",
    )

    result = await manager.load(
        "dep_test",
        operator="operator",
    )

    assert result.metadata["runtime_id"] == "rtm_created"
    runtime_repo.create_runtime.assert_called_once_with(
        runtime_id="rtm_created",
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework=Framework.SKLEARN,
        worker_id="worker_test",
        started_by="operator",
        context={
            "worker_id": "worker_test",
        },
    )
    runtime_repo.mark_running.assert_called_once()


@pytest.mark.asyncio
async def test_unload_unregisters_model_and_marks_runtime_unloaded(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试卸载模型并更新运行记录"""
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )
    runtime_model = manager.registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
    )

    result = await manager.unload(
        "dep_test",
        operator="operator",
    )

    assert result is runtime_model
    assert "dep_test" not in manager.registry
    runtime_repo.mark_stopped.assert_called_once_with(
        runtime_repo.get_deployment_runtime.return_value,
        stopped_by="operator",
        context={
            "worker_id": "worker_test",
        },
    )


@pytest.mark.asyncio
async def test_unload_ignores_missing_runtime_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库运行记录不存在时仍可完成卸载"""
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )
    runtime_repo.get_deployment_runtime.return_value = None

    assert await manager.unload("dep_missing") is None
    runtime_repo.mark_stopped.assert_not_called()


@pytest.mark.asyncio
async def test_reload_forces_model_reload(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新加载使用强制加载流程"""
    manager, _, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )
    expected = MagicMock()
    load = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        manager,
        "_load",
        load,
    )

    result = await manager.reload(
        "dep_test",
        operator="operator",
    )

    assert result is expected
    load.assert_awaited_once_with(
        "dep_test",
        operator="operator",
        force=True,
    )


@pytest.mark.asyncio
async def test_get_status_combines_memory_and_database_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行状态合并内存和数据库信息"""
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )
    loaded_at = datetime.now(timezone.utc)
    runtime_repo.get_deployment_runtime.return_value = SimpleNamespace(
        runtime_id="rtm_test",
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        status="running",
        worker_id="worker_test",
        loaded_at=loaded_at,
        unloaded_at=None,
        last_heartbeat_at=loaded_at,
        error=None,
        context={"source": "test"},
    )
    manager.registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
    )

    result = await manager.get_status("dep_test")

    assert result["loaded_in_memory"] is True
    assert result["memory"]["deployment_id"] == "dep_test"
    assert result["runtime"] == {
        "runtime_id": "rtm_test",
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "status": "running",
        "worker_id": "worker_test",
        "loaded_at": loaded_at.isoformat(),
        "unloaded_at": None,
        "last_heartbeat_at": loaded_at.isoformat(),
        "error": None,
        "context": {"source": "test"},
    }


@pytest.mark.asyncio
async def test_get_status_returns_empty_runtime_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未知部署返回空运行状态"""
    manager, runtime_repo, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )
    runtime_repo.get_deployment_runtime.return_value = None

    result = await manager.get_status("dep_missing")

    assert result["loaded_in_memory"] is False
    assert result["memory"] is None
    assert result["runtime"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "load",
        "unload",
        "reload",
        "get_status",
    ],
)
async def test_manager_rejects_empty_deployment_id(
        monkeypatch: pytest.MonkeyPatch,
        operation: str,
) -> None:
    """测试运行时操作拒绝空部署标识"""
    manager, _, _, _, _ = configure_manager(
        monkeypatch,
        loader=MagicMock(),
    )

    with pytest.raises(
            RuntimeRouteError,
            match="deployment_id 不能为空",
    ):
        await getattr(manager, operation)("")
