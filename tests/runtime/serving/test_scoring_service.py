# tests/runtime/serving/test_scoring_service.py

"""评分模型运行服务测试

验证概率、Logit、评分转换和特征贡献分解行为。

核心功能：
  - 验证单条评分及特征贡献明细
  - 验证批量评分和空批次
  - 验证推理结果数量及类型校验
  - 验证评分卡配置来源优先级
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

import datamind.runtime.serving.base as base_module
import datamind.runtime.serving.scoring_service as scoring_module
from datamind.config.scorecard import ScorecardConfig
from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.scoring_service import ScoringService


EXPLANATION = {
    "intercept_score": 500.0,
    "feature_score": 120.0,
    "total_score": 620.0,
    "age": 20.0,
    "annual_income": 100.0,
}


class TransformerStub:
    """保留评分卡配置的转换器替身"""

    def __init__(
            self,
            *,
            config: ScorecardConfig,
    ) -> None:
        self.config = config


def create_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        probability: Any = 0.8,
        logit: Any = 1.2,
        model_type: str = "tree",
        scorecard_config: ScorecardConfig | dict[str, Any] | None = None,
        metadata_config: dict[str, Any] | None = None,
) -> tuple[ScoringService, MagicMock, MagicMock, MagicMock]:
    """创建使用组件替身的评分服务"""
    adapter = MagicMock()
    inference = MagicMock()
    inference.adapter = adapter
    inference.predict.return_value = probability
    inference.predict_logit.return_value = logit
    scorer = MagicMock()
    scorer.logit_to_score.side_effect = lambda value: 600.0 + value
    contrib = MagicMock()
    contrib.explain.return_value = EXPLANATION
    contrib.explain_batch.return_value = [
        EXPLANATION,
        EXPLANATION,
    ]
    monkeypatch.setitem(
        vars(base_module),
        "Inference",
        lambda **_kwargs: inference,
    )
    monkeypatch.setitem(
        vars(scoring_module),
        "ScoreTransformer",
        TransformerStub,
    )
    monkeypatch.setitem(
        vars(scoring_module),
        "Scorer",
        lambda **_kwargs: scorer,
    )
    monkeypatch.setitem(
        vars(scoring_module),
        "LRContrib",
        lambda **_kwargs: contrib,
    )
    metadata: dict[str, Any] = {
        "model_type": model_type,
    }

    if metadata_config is not None:
        metadata["config"] = metadata_config

    service = ScoringService(
        runtime_model=RuntimeModel(
            deployment_id="dep_test",
            model_id="mdl_test",
            version_id="ver_test",
            framework="sklearn",
            model=object(),
            metadata=metadata,
        ),
        scorecard_config=scorecard_config,
    )

    return service, inference, scorer, contrib


def test_service_requires_scoring_capabilities(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分服务校验概率和 Logit 能力"""
    _, inference, _, _ = create_service(monkeypatch)

    assert inference.adapter.require_capability.call_args_list == [
        ((ModelCapability.PREDICT_PROBA,),),
        ((ModelCapability.PREDICT_LOG_ODDS,),),
    ]


def test_predict_returns_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条评分返回统一结果"""
    service, inference, scorer, _ = create_service(monkeypatch)

    result = service.predict({
        "age": 35,
    })

    inference.predict.assert_called_once_with({"age": 35})
    inference.predict_logit.assert_called_once_with({"age": 35})
    scorer.logit_to_score.assert_called_once_with(1.2)
    assert result["probability"] == 0.8
    assert result["logit"] == 1.2
    assert result["score"] == 601.2
    assert result["score_detail"] is None
    assert result["service_type"] == "scoring"
    assert service.runtime_model.access_count == 1


def test_predict_returns_logistic_score_detail(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑回归评分返回特征贡献明细"""
    service, _, _, contrib = create_service(
        monkeypatch,
        model_type="logistic_regression",
    )

    result = service.predict({
        "age": 35,
    })

    contrib.explain.assert_called_once_with({"age": 35})
    assert result["score_detail"] == {
        "intercept_score": 500.0,
        "feature_score": 120.0,
        "raw_score": 620.0,
        "feature_scores": {
            "age": 20.0,
            "annual_income": 100.0,
        },
    }


def test_predict_rejects_empty_features(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条评分拒绝空特征"""
    service, _, _, _ = create_service(monkeypatch)

    with pytest.raises(
            ValueError,
            match="features 不能为空",
    ):
        service.predict({})


@pytest.mark.parametrize(
    ("probability", "logit", "message"),
    [
        ([0.8], 1.2, "批量概率结果"),
        (0.8, [1.2], "批量 Logit 结果"),
    ],
)
def test_predict_rejects_batch_results(
        monkeypatch: pytest.MonkeyPatch,
        probability: Any,
        logit: Any,
        message: str,
) -> None:
    """测试单条评分拒绝批量推理结果"""
    service, _, _, _ = create_service(
        monkeypatch,
        probability=probability,
        logit=logit,
    )

    with pytest.raises(
            TypeError,
            match=message,
    ):
        service.predict({"age": 35})


def test_predict_batch_returns_scores(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量评分返回逐条评分结果"""
    service, inference, scorer, _ = create_service(
        monkeypatch,
        probability=[0.2, 0.8],
        logit=[-1.0, 1.0],
    )
    features = [
        {"age": 25},
        {"age": 45},
    ]

    result = service.predict_batch(features)

    inference.adapter.require_capability.assert_any_call(
        ModelCapability.BATCH_PREDICT
    )
    assert result["count"] == 2
    assert result["predictions"] == [
        {
            "probability": 0.2,
            "logit": -1.0,
            "score": 599.0,
            "score_detail": None,
        },
        {
            "probability": 0.8,
            "logit": 1.0,
            "score": 601.0,
            "score_detail": None,
        },
    ]
    assert scorer.logit_to_score.call_count == 2
    assert service.runtime_model.access_count == 1


def test_predict_batch_returns_logistic_score_details(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑回归批量评分返回特征贡献明细"""
    service, _, _, contrib = create_service(
        monkeypatch,
        probability=[0.2, 0.8],
        logit=[-1.0, 1.0],
        model_type="logistic_regression",
    )

    result = service.predict_batch([
        {"age": 25},
        {"age": 45},
    ])

    assert contrib.explain_batch.call_count == 1
    assert result["predictions"][0]["score_detail"] is not None
    assert result["predictions"][1]["score_detail"] is not None


def test_predict_batch_returns_empty_result(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试空批次返回空评分列表"""
    service, inference, _, _ = create_service(monkeypatch)

    result = service.predict_batch([])

    assert result["count"] == 0
    assert result["predictions"] == []
    inference.predict.assert_not_called()


@pytest.mark.parametrize(
    ("probability", "logit", "error_type", "message"),
    [
        (0.8, [1.0], TypeError, "未返回概率列表"),
        ([0.8], 1.0, TypeError, "未返回 Logit 列表"),
        ([0.2, 0.8], [1.0], RuntimeError, "结果数量不一致"),
    ],
)
def test_predict_batch_rejects_invalid_results(
        monkeypatch: pytest.MonkeyPatch,
        probability: Any,
        logit: Any,
        error_type: type[Exception],
        message: str,
) -> None:
    """测试批量评分拒绝非法推理结果"""
    service, _, _, _ = create_service(
        monkeypatch,
        probability=probability,
        logit=logit,
    )

    with pytest.raises(
            error_type,
            match=message,
    ):
        service.predict_batch([
            {"age": 35},
        ])


def test_predict_batch_rejects_mismatched_explanations(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量评分拒绝数量不一致的贡献结果"""
    service, _, _, contrib = create_service(
        monkeypatch,
        probability=[0.2, 0.8],
        logit=[-1.0, 1.0],
        model_type="logistic_regression",
    )
    contrib.explain_batch.return_value = [EXPLANATION]

    with pytest.raises(
            RuntimeError,
            match="特征贡献分解结果数量",
    ):
        service.predict_batch([
            {"age": 25},
            {"age": 45},
        ])


@pytest.mark.parametrize(
    ("explicit_config", "metadata_config", "base_score"),
    [
        ({"base_score": 650.0}, {"base_score": 620.0}, 650.0),
        (None, {"base_score": 620.0}, 620.0),
        (None, None, 600.0),
    ],
)
def test_service_resolves_scorecard_config(
        monkeypatch: pytest.MonkeyPatch,
        explicit_config: dict[str, Any] | None,
        metadata_config: dict[str, Any] | None,
        base_score: float,
) -> None:
    """测试评分卡配置按照优先级解析"""
    service, _, _, _ = create_service(
        monkeypatch,
        scorecard_config=explicit_config,
        metadata_config=metadata_config,
    )

    config = service.transformer.config
    assert isinstance(config, ScorecardConfig)
    assert config.base_score == base_score


def test_service_preserves_scorecard_config_instance(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务保留显式评分卡配置实例"""
    config = ScorecardConfig(
        base_score=650.0
    )

    service, _, _, _ = create_service(
        monkeypatch,
        scorecard_config=config,
    )

    assert service.transformer.config is config
