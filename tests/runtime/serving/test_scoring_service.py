# tests/runtime/serving/test_scoring_service.py

"""评分卡运行服务测试

验证单条与批量评分、决策阈值和模型能力约束。

核心功能：
  - test_predict_uses_scorecard_score:
    验证单条预测使用评分卡分数
  - test_predict_batch_uses_scorecard_score:
    验证批量预测使用评分卡分数
  - test_score_below_threshold_is_rejected:
    验证低于阈值的分数被拒绝
  - test_rejects_model_without_score:
    验证拒绝不支持评分的模型
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.scoring_service import ScoringService


class InferenceStub:
    """概率推理替身"""

    def __init__(self, **_kwargs: object) -> None:
        self.adapter = AdapterStub()

    @staticmethod
    def predict(features: object) -> float | list[float]:
        if isinstance(features, list):
            return [0.2 for _ in features]
        return 0.2


class AdapterStub:
    """模型能力替身"""

    capabilities = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    def get_capabilities(self) -> ModelCapability:
        """返回测试能力"""
        return self.capabilities

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验测试能力"""
        if self.capabilities & capability != capability:
            raise NotImplementedError


class ScorecardStub:
    """OptBinning Scorecard 替身"""

    score: MagicMock = MagicMock()


def create_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        threshold: float = 600.0,
) -> tuple[ScoringService, ScorecardStub]:
    """创建评分服务"""
    monkeypatch.setattr(
        "datamind.runtime.serving.base.Inference",
        InferenceStub,
    )
    monkeypatch.setattr(
        "datamind.runtime.serving.scoring_service.Scorecard",
        ScorecardStub,
    )
    model = ScorecardStub()
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


def test_rejects_model_without_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝非 Scorecard 模型"""
    monkeypatch.setattr(
        "datamind.runtime.serving.base.Inference",
        InferenceStub,
    )
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
