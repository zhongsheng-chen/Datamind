"""真实评分卡制品推理集成测试.

验证 optbinning.Scorecard 经 joblib 序列化、统一制品加载器重载后，
ScoringService 的总分、概率、特征分和分箱命中均保持一致。

核心功能：
  - test_persisted_scorecard_preserves_scoring_behavior:
    验证评分卡制品加载前后的完整评分行为
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import joblib
import numpy as np
from optbinning import BinningProcess, Scorecard
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from datamind.models.artifact import ModelArtifactLoader
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.scoring_service import ScoringService
from datamind.storage.local import LocalStorageBackend


pytestmark = pytest.mark.integration


def fit_scorecard() -> Scorecard:
    """拟合包含数值与类别变量的真实评分卡."""
    records: list[dict[str, object]] = []
    labels: list[int] = []

    categories = ["salaried", "contract", "unemployed", None]
    ages = [20.0, 35.0, 45.0, np.nan]

    for category_index, category in enumerate(categories):
        for age_index, age in enumerate(ages):
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


def serialize_scorecard(model: Scorecard) -> bytes:
    """将评分卡序列化为 pkl 制品."""
    buffer = BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


def create_service(model: Scorecard) -> ScoringService:
    """为重载后的真实评分卡创建运行服务."""
    return ScoringService(
        runtime_model=RuntimeModel(
            deployment_id="dep_scorecard_integration",
            model_id="mdl_scorecard_integration",
            version_id="ver_scorecard_integration",
            framework="sklearn",
            model=model,
            metadata={},
        )
    )


def test_persisted_scorecard_preserves_scoring_behavior(tmp_path: Path) -> None:
    """测试评分卡持久化前后的分数、概率与分箱明细一致."""
    model = fit_scorecard()
    features = {
        "employment_type": "contract",
        "age": 35.0,
    }
    frame = pd.DataFrame([features])

    expected_score = float(model.score(frame)[0])
    expected_probability = float(model.predict_proba(frame)[0, 1])

    storage = LocalStorageBackend(tmp_path / "artifacts")
    model_key = "models/scorecard/1.0.0/scorecard.pkl"
    storage.put_object(model_key, serialize_scorecard(model))

    restored = ModelArtifactLoader.load(
        framework="sklearn",
        data=storage.get_object(model_key),
    )
    result = create_service(restored).predict(features)
    feature_scores = result["features"]

    assert restored.score(frame) == pytest.approx(model.score(frame))
    assert restored.predict_proba(frame) == pytest.approx(model.predict_proba(frame))

    assert result["score"] == pytest.approx(expected_score)
    assert result["probability"] == pytest.approx(expected_probability)
    assert set(feature_scores) == {"employment_type", "age"}

    for detail in feature_scores.values():
        assert set(detail) == {"value", "bin", "woe", "points"}
        assert detail["bin"]

    assert result["score"] == pytest.approx(
        sum(detail["points"] for detail in feature_scores.values())
        + result["score_intercept"]
    )
