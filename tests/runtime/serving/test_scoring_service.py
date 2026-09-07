# tests/runtime/serving/test_scoring_service.py

"""评分卡运行服务测试

验证单条与批量评分、决策阈值和模型能力约束。

核心功能：
  - test_predict_uses_scorecard_score:
    验证单条预测使用评分卡分数
  - test_predict_batch_uses_scorecard_score:
    验证批量预测使用评分卡分数
  - test_predict_reuses_feature_frame:
    验证概率预测与评分复用特征表
  - test_predict_uses_probability_for_default_label:
    验证根据模型类别顺序提取违约概率
  - test_predict_rejects_invalid_probability_output:
    验证拒绝无效概率预测结果
  - test_score_below_threshold_is_rejected:
    验证低于阈值的分数被拒绝
  - test_service_exposes_scoring_capabilities:
    验证评分服务公开固定能力
  - test_rejects_model_without_score:
    验证拒绝不支持评分的模型
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.scoring_service import ScoringService


class ScorecardStub:
    """OptBinning Scorecard 替身"""

    score: MagicMock = MagicMock()
    predict_proba: MagicMock = MagicMock()
    estimator_: SimpleNamespace = SimpleNamespace(
        classes_=np.array([0, 1])
    )


def create_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        threshold: float = 600.0,
) -> tuple[ScoringService, ScorecardStub]:
    """创建评分服务"""
    monkeypatch.setattr(
        "datamind.runtime.serving.scoring_service.Scorecard",
        ScorecardStub,
    )
    model = ScorecardStub()
    model.estimator_ = SimpleNamespace(
        classes_=np.array([0, 1])
    )
    model.predict_proba = MagicMock()
    model.predict_proba.side_effect = lambda frame: [
        [0.8, 0.2]
        for _ in range(len(frame))
    ]
    model.score = MagicMock()
    model.score.side_effect = lambda frame: [
        600.0 + index
        for index in range(len(frame))
    ]
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=model,
        metadata={},
    )
    service = ScoringService(
        runtime_model=runtime_model,
        feature_names=["age"],
        threshold=threshold,
    )
    return service, model


def test_predict_uses_scorecard_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条评分直接调用 Scorecard"""
    service, model = create_service(monkeypatch)

    result = service.predict({"age": 35})

    assert result["probability"] == pytest.approx(0.2)
    assert result["score"] == pytest.approx(600.0)
    assert result["decision"] == "approve"
    assert result["threshold"] == pytest.approx(600.0)
    assert list(model.score.call_args.args[0].columns) == ["age"]


def test_predict_batch_uses_scorecard_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量评分直接调用 Scorecard"""
    service, _ = create_service(monkeypatch)

    result = service.predict_batch([
        {"age": 35},
        {"age": 45},
    ])

    assert result["count"] == 2
    assert result["predictions"] == [
        {
            "probability": 0.2,
            "score": 600.0,
            "decision": "approve",
            "threshold": 600.0,
        },
        {
            "probability": 0.2,
            "score": 601.0,
            "decision": "approve",
            "threshold": 600.0,
        },
    ]


def test_predict_reuses_feature_frame(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概率预测和评分复用同一个特征表"""
    service, model = create_service(monkeypatch)

    service.predict({"age": 35})

    probability_frame = (
        model.predict_proba.call_args.args[0]
    )
    score_frame = model.score.call_args.args[0]

    assert probability_frame is score_frame


def test_predict_uses_probability_for_default_label(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试根据模型类别顺序提取违约概率"""
    service, model = create_service(monkeypatch)
    model.estimator_.classes_ = np.array([1, 0])
    model.predict_proba.side_effect = None
    model.predict_proba.return_value = [
        [0.2, 0.8]
    ]

    result = service.predict({"age": 35})

    assert result["probability"] == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            [[0.8]],
            "评分卡概率预测结果形状不正确",
        ),
        (
            [[float("nan"), 0.2]],
            "必须是 0 到 1 之间的有限数值",
        ),
        (
            [[-0.1, 1.1]],
            "必须是 0 到 1 之间的有限数值",
        ),
    ],
)
def test_predict_rejects_invalid_probability_output(
        monkeypatch: pytest.MonkeyPatch,
        values: list[list[float]],
        message: str,
) -> None:
    """测试拒绝无效概率预测结果"""
    service, model = create_service(monkeypatch)
    model.predict_proba.side_effect = None
    model.predict_proba.return_value = values

    with pytest.raises(ValueError, match=message):
        service.predict({"age": 35})


def test_score_below_threshold_is_rejected(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试低于评分阈值时拒绝"""
    service, _ = create_service(
        monkeypatch,
        threshold=601.0,
    )

    result = service.predict({"age": 35})

    assert result["decision"] == "reject"


def test_service_exposes_scoring_capabilities(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分服务公开固定能力"""
    service, _ = create_service(monkeypatch)

    assert service.get_capabilities() == (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )


def test_rejects_model_without_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝非 Scorecard 模型"""
    monkeypatch.setattr(
        "datamind.runtime.serving.scoring_service.Scorecard",
        ScorecardStub,
    )
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=SimpleNamespace(),
        metadata={},
    )

    with pytest.raises(
            TypeError,
            match=(
                "模型类型不匹配："
                f"期望 {ScorecardStub.__name__}，"
                "实际 SimpleNamespace"
            ),
    ):
        ScoringService(
            runtime_model=runtime_model,
            feature_names=["age"],
        )
