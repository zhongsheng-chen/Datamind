"""Canary 后端完整业务链路 E2E.

验证同一模型的 champion 与 challenger 版本完成注册、激活、部署后，
真实运行时路由能够按稳定哈希执行灰度分流，并持久化正确的决策和执行记录。

核心功能：
  - test_canary_backend_flow:
    验证灰度主体稳定命中同一部署及版本
"""

from __future__ import annotations

from pathlib import Path
import uuid

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from datamind.db.core import UnitOfWork
from datamind.db.models import Decision, Execution
from datamind.runtime.routing import RuntimeRouter
from datamind.runtime.server.schemas import PredictRequest
from datamind.services import (
    DeploymentLifecycleService,
    ModelLifecycleService,
    ModelRegistrationService,
    RoutingLifecycleService,
)
from tests.e2e._backend_support import (
    configure_isolated_runtime,
    write_model,
)


pytestmark = pytest.mark.e2e


def train_classifier(*, inverted: bool) -> LogisticRegression:
    """训练具有相反分类结果的两个真实模型版本."""
    features = pd.DataFrame(
        [
            [-2.0, -1.0],
            [-1.0, -0.5],
            [0.5, 0.8],
            [1.5, 2.0],
        ],
        columns=["feature_0", "feature_1"],
    )
    labels = np.array([0, 0, 1, 1])

    if inverted:
        labels = 1 - labels

    return LogisticRegression(random_state=0).fit(
        features,
        labels,
    )


async def create_canary_deployments(
    *,
    tmp_path: Path,
) -> dict[str, str]:
    """通过真实业务 Service 创建 champion 与 challenger 部署."""
    name = f"e2e-canary-{uuid.uuid4().hex[:12]}"
    registration_service = ModelRegistrationService()
    lifecycle_service = ModelLifecycleService()
    deployment_service = DeploymentLifecycleService()

    champion = await registration_service.register(
        name=name,
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="classification",
        model_path=str(
            write_model(
                tmp_path / "champion.pkl",
                train_classifier(inverted=False),
            )
        ),
        created_by="e2e-test",
    )
    challenger = await registration_service.register(
        name=name,
        version="2.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="classification",
        model_path=str(
            write_model(
                tmp_path / "challenger.pkl",
                train_classifier(inverted=True),
            )
        ),
        created_by="e2e-test",
    )

    for registration in (champion, challenger):
        await lifecycle_service.activate(
            model_id=registration["model_id"],
            version_id=registration["version_id"],
            updated_by="e2e-test",
        )

    champion_deployment = await deployment_service.create_deployment(
        model_id=champion["model_id"],
        version_id=champion["version_id"],
        environment="testing",
        rollout_type="full",
        role="champion",
        deployed_by="e2e-test",
    )
    challenger_deployment = await deployment_service.create_deployment(
        model_id=challenger["model_id"],
        version_id=challenger["version_id"],
        environment="testing",
        rollout_type="canary",
        role="challenger",
        deployed_by="e2e-test",
    )

    for deployment in (champion_deployment, challenger_deployment):
        await deployment_service.enable_deployment(
            deployment_id=deployment["deployment_id"],
            updated_by="e2e-test",
        )

    routing = await RoutingLifecycleService().create_routing(
        name=f"route-{name}-challenger",
        deployment_id=challenger_deployment["deployment_id"],
        environment="testing",
        traffic_ratio=0.25,
        enabled=True,
        created_by="e2e-test",
    )

    return {
        "name": name,
        "model_id": champion["model_id"],
        "champion_version_id": champion["version_id"],
        "challenger_version_id": challenger["version_id"],
        "champion_deployment_id": champion_deployment["deployment_id"],
        "challenger_deployment_id": challenger_deployment["deployment_id"],
        "challenger_routing_id": routing["routing_id"],
    }


async def find_canary_subject(
    *,
    model_id: str,
    challenger_deployment_id: str,
) -> str:
    """从真实哈希路由中寻找一个命中 challenger 的稳定主体."""
    router = RuntimeRouter()

    for index in range(100):
        subject_key = f"customer_{index:04d}"
        plan = await router.resolve(
            model_id=model_id,
            environment="testing",
            subject_key=subject_key,
            subject_type="customer",
            include_shadows=False,
        )

        if plan.primary.deployment_id == challenger_deployment_id:
            return subject_key

    raise AssertionError("前 100 个测试主体均未命中 25% challenger 流量")


@pytest.mark.asyncio
async def test_canary_backend_flow(
    datamind_database: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试灰度路由对同一主体稳定命中 challenger 版本."""
    del datamind_database
    configure_isolated_runtime(tmp_path=tmp_path, monkeypatch=monkeypatch)

    from datamind.runtime.server.service import DatamindRuntimeService

    deployment = await create_canary_deployments(tmp_path=tmp_path)
    subject_key = await find_canary_subject(
        model_id=deployment["model_id"],
        challenger_deployment_id=deployment["challenger_deployment_id"],
    )

    service_class = getattr(DatamindRuntimeService, "inner")
    service = service_class()

    for deployment_id in (
        deployment["champion_deployment_id"],
        deployment["challenger_deployment_id"],
    ):
        await service.manager.load(
            deployment_id=deployment_id,
            operator="e2e-test",
        )

    request_ids: list[str] = []
    responses: list[dict[str, object]] = []

    try:
        for _ in range(2):
            request_id = f"req_{uuid.uuid4().hex}"
            response = await service._predict(
                request=PredictRequest(
                    model_name=deployment["name"],
                    features={
                        "feature_0": 0.75,
                        "feature_1": 1.25,
                    },
                    subject_key=subject_key,
                    subject_type="customer",
                ),
                request_id=request_id,
            )
            request_ids.append(request_id)
            responses.append(response)
    finally:
        for deployment_id in (
            deployment["champion_deployment_id"],
            deployment["challenger_deployment_id"],
        ):
            await service.manager.unload(
                deployment_id=deployment_id,
                operator="e2e-test",
            )

    async with UnitOfWork() as uow:
        decisions = list(
            (
                await uow.session.scalars(
                    select(Decision).where(
                        Decision.request_id.in_(request_ids)
                    )
                )
            ).all()
        )
        decision_ids = [decision.decision_id for decision in decisions]
        executions = list(
            (
                await uow.session.scalars(
                    select(Execution).where(
                        Execution.decision_id.in_(decision_ids)
                    )
                )
            ).all()
        )

    assert all(response["success"] is True for response in responses)
    assert responses[0]["prediction"] == responses[1]["prediction"]

    assert len(decisions) == 2
    assert {
        decision.deployment_id for decision in decisions
    } == {deployment["challenger_deployment_id"]}
    assert {
        decision.version_id for decision in decisions
    } == {deployment["challenger_version_id"]}
    assert {decision.subject_key for decision in decisions} == {subject_key}

    assert len(executions) == 2
    assert {
        execution.deployment_id for execution in executions
    } == {deployment["challenger_deployment_id"]}
    assert {
        execution.version_id for execution in executions
    } == {deployment["challenger_version_id"]}
    assert {
        execution.routing_id for execution in executions
    } == {deployment["challenger_routing_id"]}
