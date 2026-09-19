"""Classification 后端完整业务链路 E2E

验证真实 sklearn 分类模型从注册、激活、部署和路由，到 RuntimeManager
加载、预测以及 Request/Decision/Execution/Audit 持久化的完整流程。

核心功能：
  - test_classification_backend_flow:
    验证分类模型后端完整业务链路
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from datamind.db.core import UnitOfWork
from datamind.db.models import Audit, Decision, Execution, Request
from tests.e2e._backend_support import (
    configure_isolated_runtime,
    invoke_prediction,
    register_and_deploy,
    write_model,
)


pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_classification_backend_flow(
    datamind_database: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试分类模型从注册到预测、执行记录及审计持久化"""
    del datamind_database
    configure_isolated_runtime(tmp_path=tmp_path, monkeypatch=monkeypatch)

    training_features = np.array(
        [
            [-2.0, -1.0],
            [-1.0, -0.5],
            [0.5, 0.8],
            [1.5, 2.0],
        ]
    )
    training_labels = np.array([0, 0, 1, 1])
    model = LogisticRegression(random_state=0).fit(
        pd.DataFrame(
            training_features,
            columns=["feature_0", "feature_1"],
        ),
        training_labels,
    )
    model_path = write_model(tmp_path / "classifier.pkl", model)

    deployment = await register_and_deploy(
        model_path=model_path,
        task_type="classification",
    )
    response, request_id = await invoke_prediction(
        deployment=deployment,
        features={
            "feature_0": 0.75,
            "feature_1": 1.25,
        },
    )

    async with UnitOfWork() as uow:
        request_record = await uow.session.scalar(
            select(Request).where(Request.request_id == request_id)
        )
        decision = await uow.session.scalar(
            select(Decision).where(Decision.request_id == request_id)
        )

        assert isinstance(request_record, Request)
        assert isinstance(decision, Decision)

        execution = await uow.session.scalar(
            select(Execution).where(Execution.decision_id == decision.decision_id)
        )
        audit = await uow.session.scalar(
            select(Audit).where(
                Audit.request_id == request_id,
                Audit.action == "prediction.invoke",
            )
        )

        assert isinstance(execution, Execution)
        assert isinstance(audit, Audit)

    expected_probability = float(
        model.predict_proba(
            pd.DataFrame(
                [[0.75, 1.25]],
                columns=["feature_0", "feature_1"],
            )
        )[0, 1]
    )

    assert response["success"] is True
    assert response["probability"] == pytest.approx(expected_probability)

    assert request_record.status == "success"
    assert decision.deployment_id == deployment["deployment_id"]
    assert decision.version_id == deployment["version_id"]

    assert execution.status == "success"
    assert execution.deployment_id == deployment["deployment_id"]
    assert execution.version_id == deployment["version_id"]
    assert execution.routing_id == deployment["routing_id"]

    assert audit.target_type == "request"
    assert audit.target_id == request_id
    assert audit.status == "success"
    assert audit.source == "http"
    assert audit.user == "system"
