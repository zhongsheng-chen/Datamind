"""运行时服务共享夹具

通过 pytest 夹具提供运行时服务对象、请求上下文、工作单元和仓储替身。

核心功能：
  - runtime_server: 注入运行时服务测试所需的共享构造能力
"""

import asyncio
from contextlib import asynccontextmanager
from importlib import import_module
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.config import get_settings


def patch_server_dependency(
        monkeypatch: pytest.MonkeyPatch,
        service_module: Any,
        name: str,
        value: Any,
) -> None:
    """替换服务或预测模块依赖"""
    dependency_modules = (
        service_module,
        import_module("datamind.runtime.server.authentication"),
        import_module("datamind.runtime.server.control"),
        import_module("datamind.runtime.server.prediction"),
    )

    for target_module in dependency_modules:
        if name in vars(target_module):
            monkeypatch.setitem(
                vars(target_module),
                name,
                value,
            )


def load_service_module(
        monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """在隔离服务环境中加载运行时服务模块"""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "testing",
    )
    get_settings.cache_clear()
    service_config = get_settings().service

    service_module = import_module(
        "datamind.runtime.server.service"
    )
    patch_server_dependency(
        monkeypatch,
        service_module,
        "service_config",
        service_config,
    )
    get_settings.cache_clear()

    return service_module


def create_service(
        service_module: Any,
) -> Any:
    """创建跳过初始化的运行时服务对象"""
    service_class = service_module.DatamindRuntimeService.inner
    service = object.__new__(
        service_class
    )
    service._logger = MagicMock()
    service.manager = MagicMock()
    service.manager.worker_id = "worker_test"
    service.manager.registry.all.return_value = []
    service.manager.registry.__len__.return_value = 0
    service.manager.registry.snapshot.return_value = []
    service.manager.get_status = AsyncMock(return_value={})
    service.manager.unload = AsyncMock()
    service.router = MagicMock()
    service.router.resolve = AsyncMock()
    service._resolve_model_id = AsyncMock(
        return_value="mdl_test"
    )
    service.executor = MagicMock()
    service.executor.execute = AsyncMock()
    service.controller = MagicMock()
    service.controller.load = AsyncMock()
    service.controller.unload = AsyncMock()
    service.controller.reload = AsyncMock()
    service.controller.get_status = AsyncMock()
    service.reconciler = MagicMock()
    service.reconciler.is_running = True
    service.reconciler.reconcile_once = AsyncMock()
    service.reconciler.start = AsyncMock()
    service.reconciler.stop = AsyncMock()
    service.reconciler.get_applied_generation.return_value = None
    service.reconciler.get_applied_generations.return_value = {}
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    service.shadow_dispatcher = MagicMock()
    service.shadow_dispatcher.is_running = True
    service.shadow_dispatcher.pending_count = 0
    service.shadow_dispatcher.start = AsyncMock()
    service.shadow_dispatcher.stop = AsyncMock()
    service.shadow_dispatcher.submit.return_value = True
    vars(service).update({
        "_service_cache": {},
        "_service_lock": asyncio.Lock(),
        "_audit_recorder": audit_recorder,
    })
    return service


def create_score_details(score: float) -> dict[str, Any]:
    """创建总分可核对的评分明细"""
    return {
        "score_intercept": 20.0,
        "features": {
            "age": {"value": 35, "bin": "[30, 40)", "woe": 0.15, "points": score - 20.0},
        },
    }


def get_service_cache(
        service: Any,
) -> dict[str, Any]:
    """获取测试服务的本地服务缓存"""
    return vars(service)["_service_cache"]


def get_audit_recorder(
        service: Any,
) -> MagicMock:
    """获取测试服务的审计记录器替身"""
    return vars(service)["_audit_recorder"]


class FakeUnitOfWork:
    """运行时服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.execute = AsyncMock()
        FakeUnitOfWork.latest = self

    latest: "FakeUnitOfWork | None" = None

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


class SecurityStub:
    """运行时安全请求作用域替身"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @asynccontextmanager
    async def request_scope(
            self,
            **kwargs: Any,
    ):
        """进入测试身份请求作用域"""
        self.calls.append(kwargs)
        yield SimpleNamespace(
            username="alice"
        )


def install_repositories(
        service_module: Any,
        monkeypatch: pytest.MonkeyPatch,
        *,
        request_repo: MagicMock | None = None,
        decision_repo: MagicMock | None = None,
        execution_repo: MagicMock | None = None,
        deployment_repo: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """安装运行时服务仓储替身"""
    request_repository = request_repo or MagicMock()
    decision_repository = decision_repo or MagicMock()
    execution_repository = execution_repo or MagicMock()
    deployment_repository = deployment_repo or MagicMock()

    if not isinstance(
            request_repository.get_request,
            AsyncMock,
    ):
        request_repository.get_request = AsyncMock()

    if not isinstance(
            deployment_repository.get_deployment,
            AsyncMock,
    ):
        deployment_repository.get_deployment = AsyncMock()

    if not isinstance(
            execution_repository.get_execution,
            AsyncMock,
    ):
        execution_repository.get_execution = AsyncMock()

    patch_server_dependency(
        monkeypatch,
        service_module,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    patch_server_dependency(
        monkeypatch,
        service_module,
        "RequestRepository",
        lambda _session: request_repository,
    )
    patch_server_dependency(
        monkeypatch,
        service_module,
        "DecisionRepository",
        lambda _session: decision_repository,
    )
    patch_server_dependency(
        monkeypatch,
        service_module,
        "ExecutionRepository",
        lambda _session: execution_repository,
    )
    patch_server_dependency(
        monkeypatch,
        service_module,
        "DeploymentRepository",
        lambda _session: deployment_repository,
    )

    return (
        request_repository,
        decision_repository,
        execution_repository,
        deployment_repository,
    )


class RuntimeServerFixtures:
    """汇集运行时服务测试使用的构造能力"""

    FakeUnitOfWork = FakeUnitOfWork
    SecurityStub = SecurityStub
    create_score_details = staticmethod(create_score_details)
    create_service = staticmethod(create_service)
    get_audit_recorder = staticmethod(get_audit_recorder)
    get_service_cache = staticmethod(get_service_cache)
    install_repositories = staticmethod(install_repositories)
    load_service_module = staticmethod(load_service_module)
    patch_server_dependency = staticmethod(patch_server_dependency)


@pytest.fixture
def runtime_server() -> RuntimeServerFixtures:
    """提供运行时服务测试共享构造能力"""
    FakeUnitOfWork.latest = None
    return RuntimeServerFixtures()
