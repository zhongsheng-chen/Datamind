"""运行时服务缓存测试.

验证 Worker 服务缓存的查询、创建及失效行为。

核心功能：
  - test_services_returns_cached_service_information:
    验证服务列表返回运行时和缓存信息
  - test_get_service_reconciles_and_caches_runtime_service:
    验证本地模型收敛后创建并缓存运行时服务
  - test_get_service_rejects_unloaded_runtime:
    验证状态收敛后仍未加载模型时拒绝服务
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog
from structlog.testing import CapturingLogger

from datamind.runtime.server.cache import ServiceCacheEntry


@pytest.mark.asyncio
async def test_services_returns_cached_service_information(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务列表返回运行时和缓存信息."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_service = MagicMock()
    runtime_service.deployment_id = "dep_test"
    runtime_service.model_id = "mdl_test"
    runtime_service.version_id = "ver_test"
    runtime_service.framework = "sklearn"
    runtime_service.SERVICE_TYPE = "scoring"
    runtime_service.get_capability_names.return_value = [
        "PREDICT_PROBA"
    ]
    runtime_server.get_service_cache(service)[
        "dep_test"
    ] = ServiceCacheEntry(
        service=runtime_service,
        generation=1,
        identity=100,
    )
    service.manager.registry.__len__.return_value = 1
    service.manager.registry.snapshot.return_value = [
        {"deployment_id": "dep_test"}
    ]
    service.reconciler.get_applied_generations.return_value = {
        "dep_test": 1
    }

    result = await service._services()

    assert result["runtime_count"] == 1
    assert result["service_cache_count"] == 1
    assert result["services"] == [{
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "service_type": "scoring",
        "capabilities": ["PREDICT_PROBA"],
    }]


@pytest.mark.asyncio
async def test_get_service_reconciles_and_caches_runtime_service(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地模型收敛后创建并缓存运行时服务."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_model = object()
    service.manager.registry.get.side_effect = [
        None,
        runtime_model,
        runtime_model,
    ]
    service.reconciler.get_applied_generation.return_value = 2
    captured = CapturingLogger()
    service._logger = structlog.wrap_logger(
        captured,
        processors=[],
        wrapper_class=structlog.make_filtering_bound_logger(0),
    ).bind(worker_id="worker_test", pid=123, service_id="startup_test")
    original_context = dict(structlog.get_context(service._logger))
    runtime_service = MagicMock()
    runtime_service.SERVICE_TYPE = "scoring"
    factory = MagicMock(return_value=runtime_service)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "RuntimeServiceFactory",
        SimpleNamespace(create=factory),
    )

    first = await service._get_service("dep_test")
    second = await service._get_service("dep_test")

    assert first is runtime_service
    assert second is runtime_service
    service.reconciler.reconcile_once.assert_awaited_once()
    factory.assert_called_once_with(
        runtime_model=runtime_model
    )
    cache_entry = runtime_server.get_service_cache(service)["dep_test"]
    instance_id = cache_entry.instance_id
    assert len(instance_id) == 32
    assert len(captured.calls) == 1
    call = captured.calls[0]
    assert call.method_name == "debug"
    assert call.kwargs["event"] == "模型服务实例已创建"
    assert list(call.kwargs)[:4] == [
        "instance_id", "service_id", "worker_id", "pid",
    ]
    assert call.kwargs["instance_id"] == instance_id
    assert call.kwargs["service_id"] == "startup_test"
    assert call.kwargs["deployment_id"] == "dep_test"
    assert structlog.get_context(service._logger) == original_context

    service.manager.registry.get.side_effect = None
    service.manager.registry.get.return_value = runtime_model
    service.reconciler.get_applied_generation.return_value = 3
    await service._get_service("dep_test")
    replacement = runtime_server.get_service_cache(service)["dep_test"]
    assert replacement.instance_id != instance_id
    assert replacement.generation == 3
    assert factory.call_count == 2
    assert len(captured.calls) == 2
    assert structlog.get_context(service._logger) == original_context


@pytest.mark.asyncio
async def test_get_service_rejects_unloaded_runtime(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试状态收敛后仍未加载模型时拒绝服务."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.manager.registry.get.return_value = None
    service_cache = runtime_server.get_service_cache(service)
    service_cache["dep_test"] = object()

    with pytest.raises(
            RuntimeError,
            match="当前 Worker 尚未加载该模型",
    ):
        await service._get_service("dep_test")

    assert "dep_test" not in service_cache
