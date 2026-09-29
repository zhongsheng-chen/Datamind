"""后端 E2E 测试辅助工具.

封装分类、评分和 Canary 场景共用的环境隔离、模型制品写入、
注册部署以及运行时预测流程。

核心功能：
  - configure_isolated_runtime: 配置测试独享的本地运行环境
  - write_model: 写入待注册的模型制品
  - register_and_deploy: 完成模型注册、激活、部署和路由创建
  - invoke_prediction: 加载部署并执行真实运行时预测
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

import bentoml
import joblib
import pytest
from starlette.requests import Request as StarletteRequest

from datamind.storage import get_storage


def configure_isolated_runtime(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置仅用于当前 E2E case 的本地制品与 BentoML 目录."""
    monkeypatch.setenv("DATAMIND_STORAGE_TYPE", "local")
    monkeypatch.setenv("DATAMIND_AUTH_ENABLED", "false")
    monkeypatch.setenv("DATAMIND_SERVICE_ENVIRONMENT", "testing")
    monkeypatch.setenv(
        "DATAMIND_STORAGE_LOCAL_BASE_DIR",
        str(tmp_path / "storage"),
    )
    monkeypatch.setenv("BENTOML_HOME", str(tmp_path / "bentoml"))
    get_storage.cache_clear()


def write_model(path: Path, model: Any) -> Path:
    """将真实训练模型写为注册服务可读取的 pkl 文件."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


async def register_and_deploy(
    *,
    model_path: Path,
    task_type: str,
    threshold: float | None = None,
) -> dict[str, str]:
    """通过真实业务 Service 完成注册、激活、部署和路由启用."""
    from datamind.services import (
        DeploymentLifecycleService,
        ModelLifecycleService,
        ModelRegistrationService,
        RoutingLifecycleService,
    )

    name = f"e2e-{task_type}-{uuid.uuid4().hex[:12]}"
    registration = await ModelRegistrationService().register(
        name=name,
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type=task_type,
        model_path=str(model_path),
        created_by="e2e-test",
    )
    await ModelLifecycleService().activate(
        model_id=registration["model_id"],
        version_id=registration["version_id"],
        updated_by="e2e-test",
    )

    deployment = await DeploymentLifecycleService().create_deployment(
        model_id=registration["model_id"],
        version_id=registration["version_id"],
        environment="testing",
        threshold=threshold,
        deployed_by="e2e-test",
    )
    await DeploymentLifecycleService().enable_deployment(
        deployment_id=deployment["deployment_id"],
        updated_by="e2e-test",
    )

    routing = await RoutingLifecycleService().create_routing(
        name=f"route-{name}",
        deployment_id=deployment["deployment_id"],
        environment="testing",
        traffic_ratio=1.0,
        enabled=True,
        created_by="e2e-test",
    )

    return {
        "name": name,
        "model_id": registration["model_id"],
        "version_id": registration["version_id"],
        "deployment_id": deployment["deployment_id"],
        "routing_id": routing["routing_id"],
    }


async def invoke_prediction(
    *,
    deployment: dict[str, str],
    features: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """使用真实 RuntimeManager、Router 与 PredictionExecutor 执行预测."""
    from datamind.runtime.server.schemas import PredictRequest
    from datamind.runtime.server.service import DatamindRuntimeService

    service_class = getattr(DatamindRuntimeService, "inner")
    service = service_class()
    context = bentoml.Context()
    http_request = StarletteRequest(
        {
            "type": "http",
            "headers": [],
            "client": ("127.0.0.1", 0),
        }
    )

    await service.manager.load(
        deployment_id=deployment["deployment_id"],
        operator="e2e-test",
    )

    try:
        with context.in_request(http_request):
            response = await service.predict(
                request=PredictRequest(
                    model_name=deployment["name"],
                    features=features,
                ),
                ctx=context,
            )
    finally:
        await service.manager.unload(
            deployment_id=deployment["deployment_id"],
            operator="e2e-test",
        )

    request_id = str(response["request_id"])
    return response, request_id
