"""运行时服务缓存测试

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

from datamind.runtime.server.cache import ServiceCacheEntry


@pytest.mark.asyncio
async def test_services_returns_cached_service_information(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务列表返回运行时和缓存信息"""
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
        runtime_identity=100,
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
    """测试本地模型收敛后创建并缓存运行时服务"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_model = object()
    service.manager.registry.get.side_effect = [
        None,
        runtime_model,
        runtime_model,
    ]
    service.reconciler.get_applied_generation.return_value = 2
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


@pytest.mark.asyncio
async def test_get_service_rejects_unloaded_runtime(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试状态收敛后仍未加载模型时拒绝服务"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.manager.registry.get.return_value = None
    service_cache = runtime_server.get_service_cache(service)
    service_cache["dep_test"] = object()

    with pytest.raises(
            RuntimeError,
            match="当前 Worker 尚未加载部署模型",
    ):
        await service._get_service("dep_test")

    assert "dep_test" not in service_cache
