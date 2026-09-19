"""Scoring 后端完整业务链路 E2E

验证真实 optbinning.Scorecard 从注册、激活、部署和路由，到 RuntimeManager
加载、评分以及 Request/Decision/Execution/Audit 持久化的完整流程。

核心功能：
  - test_scoring_backend_flow:
    验证评分卡后端完整业务链路
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from optbinning import BinningProcess, Scorecard
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


def fit_scorecard() -> Scorecard:
    """拟合用于完整后端流程的真实评分卡"""
    records: list[dict[str, object]] = []
    labels: list[int] = []

    for category_index, category in enumerate(
        ["salaried", "contract", "unemployed", None]
    ):
        for age_index, age in enumerate([20.0, 35.0, 45.0, np.nan]):
            for repeat in range(12):
                records.append(
                    {
                        "employment_type": category,
                        "age": age,
                    }
                )
                labels.append(int(repeat < 2 + (category_index + age_index) % 7))

    process = BinningProcess(
        variable_names=["employment_type", "age"],
        categorical_variables=["employment_type"],
        fixed_variables=["employment_type", "age"],
        binning_fit_params={
            "employment_type": {
                "user_splits": [
                    ["salaried"],
                    ["contract", "unemployed"],
                ],
                "user_splits_fixed": [True, True],
                "monotonic_trend": None,
            },
            "age": {
                "user_splits": [30, 40],
                "user_splits_fixed": [True, True],
                "monotonic_trend": None,
            },
        },
        n_jobs=1,
    )

    return Scorecard(
        binning_process=process,
        estimator=LogisticRegression(max_iter=1000),
        scaling_method="pdo_odds",
        scaling_method_params={
            "pdo": 40,
            "odds": 45,
            "scorecard_points": 650,
        },
        intercept_based=True,
    ).fit(
        pd.DataFrame(records),
        np.asarray(labels),
        metric_missing="empirical",
    )


@pytest.mark.asyncio
async def test_scoring_backend_flow(
    datamind_database: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分卡从注册到评分、执行记录及审计持久化"""
    del datamind_database
    configure_isolated_runtime(tmp_path=tmp_path, monkeypatch=monkeypatch)

    model = fit_scorecard()
    model_path = write_model(tmp_path / "scorecard.pkl", model)
    features = {
        "employment_type": "contract",
        "age": 35.0,
    }
    frame = pd.DataFrame([features])

    deployment = await register_and_deploy(
        model_path=model_path,
        task_type="scoring",
        threshold=600.0,
    )
    response, request_id = await invoke_prediction(
        deployment=deployment,
        features=features,
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

    expected_score = float(model.score(frame)[0])
    expected_probability = float(model.predict_proba(frame)[0, 1])
    feature_scores = response["features"]

    assert response["success"] is True
    assert response["score"] == pytest.approx(expected_score)
    assert response["probability"] == pytest.approx(expected_probability)
    assert set(feature_scores) == {"employment_type", "age"}

    for detail in feature_scores.values():
        assert detail["bin"]
        assert isinstance(detail["points"], float)

    assert response["score"] == pytest.approx(
        sum(detail["points"] for detail in feature_scores.values())
        + response["score_intercept"]
    )

    assert request_record.status == "success"
    assert decision.deployment_id == deployment["deployment_id"]
    assert decision.version_id == deployment["version_id"]

    assert execution.status == "success"
    assert execution.score == pytest.approx(expected_score)
    assert execution.probability == pytest.approx(expected_probability)
    assert execution.routing_id == deployment["routing_id"]

    assert audit.target_type == "request"
    assert audit.target_id == request_id
    assert audit.status == "success"
    assert audit.source == "http"
    assert audit.user == "system"
