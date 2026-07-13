# tests/core/scoring/test_scorer.py

"""评分器测试

验证评分器的模型能力要求、评分计算、批量评分、
评分转换委托、正类方向和返回类型校验。

核心功能：
  - 验证评分能力声明
  - 验证逻辑回归评分
  - 验证批量评分
  - 验证正类方向
  - 验证自定义评分转换器
  - 验证评分上下限
  - 验证非逻辑回归模型拒绝
  - 验证 Logit 返回类型
"""

from typing import Any

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from datamind.config.scorecard import ScorecardConfig
from datamind.core.capability import ScorecardCapability
from datamind.core.inference import Inference
from datamind.core.scoring.scorer import Scorer
from datamind.core.scoring.transformer import ScoreTransformer


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


@pytest.fixture
def binary_training_data(
) -> tuple[np.ndarray, np.ndarray]:
    """提供二分类训练数据"""
    X = np.array([
        [-2.0, -1.5],
        [-1.5, -0.8],
        [-1.0, -1.2],
        [-0.5, -0.2],
        [0.2, 0.1],
        [0.8, 0.6],
        [1.3, 1.0],
        [2.0, 1.5],
    ])

    y = np.array([
        1,
        1,
        1,
        1,
        0,
        0,
        0,
        0,
    ])

    return (
        X,
        y,
    )


@pytest.fixture
def logistic_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> LogisticRegression:
    """提供已训练逻辑回归模型"""
    X, y = binary_training_data

    model = LogisticRegression(
        max_iter=1000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.fixture
def inference(
        logistic_model: LogisticRegression,
) -> Inference:
    """提供统一推理实例"""
    return Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


@pytest.fixture
def transformer(
) -> ScoreTransformer:
    """提供自定义评分转换器"""
    return ScoreTransformer(
        config=ScorecardConfig(
            base_score=600.0,
            base_odds=50.0,
            pdo=20.0,
            min_score=0.0,
            max_score=1000.0,
        )
    )


@pytest.fixture
def scorer(
        inference: Inference,
        transformer: ScoreTransformer,
) -> Scorer:
    """提供评分器"""
    return Scorer(
        inference=inference,
        transformer=transformer,
    )


def test_scorer_capabilities(
        scorer: Scorer,
) -> None:
    """测试评分器仅声明总评分能力"""
    assert (
        scorer.get_capabilities()
        == ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert scorer.has_capability(
        ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert not scorer.has_capability(
        ScorecardCapability.SCORECARD_FEATURE_SCORE
    )

    assert not scorer.has_capability(
        ScorecardCapability.SCORECARD_LOGIT
    )


def test_init_uses_provided_inference_and_transformer(
        inference: Inference,
        transformer: ScoreTransformer,
) -> None:
    """测试初始化保留推理接口和评分转换器"""
    scorer = Scorer(
        inference=inference,
        transformer=transformer,
    )

    assert scorer.inference is inference
    assert scorer.transformer is transformer


def test_init_creates_default_transformer(
        inference: Inference,
) -> None:
    """测试未传入转换器时创建默认实例"""
    scorer = Scorer(
        inference=inference
    )

    assert isinstance(
        scorer.transformer,
        ScoreTransformer,
    )


def test_score_matches_logit_conversion(
        logistic_model: LogisticRegression,
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试评分与模型 Logit 转换结果一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    logit = float(
        logistic_model.decision_function(
            array
        )[0]
    )

    expected = transformer.logit_to_score(
        logit
    )

    result = scorer.score(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_score_batch_matches_logit_conversion(
        logistic_model: LogisticRegression,
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试批量评分与模型 Logit 转换结果一致"""
    features = [
        {
            "feature_b": 0.25,
            "feature_a": -0.75,
        },
        {
            "feature_b": 0.80,
            "feature_a": 1.20,
        },
    ]

    array = np.array([
        [-0.75, 0.25],
        [1.20, 0.80],
    ])

    logits = logistic_model.decision_function(
        array
    )

    expected = [
        transformer.logit_to_score(
            float(logit)
        )
        for logit in logits
    ]

    result = scorer.score_batch(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_score_accepts_numpy_vector(
        logistic_model: LogisticRegression,
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试评分接口接受一维数组"""
    features = np.array([
        -0.75,
        0.25,
    ])

    logit = float(
        logistic_model.decision_function(
            features.reshape(
                1,
                -1,
            )
        )[0]
    )

    expected = transformer.logit_to_score(
        logit
    )

    result = scorer.score(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_score_batch_accepts_numpy_matrix(
        logistic_model: LogisticRegression,
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试批量评分接口接受二维数组"""
    features = np.array([
        [-0.75, 0.25],
        [1.20, 0.80],
    ])

    logits = logistic_model.decision_function(
        features
    )

    expected = [
        transformer.logit_to_score(
            float(logit)
        )
        for logit in logits
    ]

    result = scorer.score_batch(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_positive_class_zero_uses_reversed_logit(
        logistic_model: LogisticRegression,
        transformer: ScoreTransformer,
) -> None:
    """测试正类为类别零时使用反向 Logit"""
    inference = Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    scorer = Scorer(
        inference=inference,
        transformer=transformer,
    )

    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    logit = -float(
        logistic_model.decision_function(
            array
        )[0]
    )

    expected = transformer.logit_to_score(
        logit
    )

    result = scorer.score(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_probability_to_score_delegates_to_transformer(
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试违约概率转评分委托给转换器"""
    probability = 0.2

    expected = transformer.probability_to_score(
        probability
    )

    result = scorer.probability_to_score(
        probability
    )

    assert result == pytest.approx(
        expected
    )


def test_logit_to_score_delegates_to_transformer(
        scorer: Scorer,
        transformer: ScoreTransformer,
) -> None:
    """测试 Logit 转评分委托给转换器"""
    logit = 1.25

    expected = transformer.logit_to_score(
        logit
    )

    result = scorer.logit_to_score(
        logit
    )

    assert result == pytest.approx(
        expected
    )


def test_score_applies_minimum_limit(
        scorer: Scorer,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分应用最小值限制"""

    def return_large_logit(
            _features: Any,
    ) -> float:
        """返回极大 Logit"""
        return 1000.0

    monkeypatch.setattr(
        scorer.inference,
        "predict_logit",
        return_large_logit,
    )

    result = scorer.score({
        "feature_a": 0.0,
        "feature_b": 0.0,
    })

    assert (
        result
        == scorer.transformer.config.min_score
    )


def test_score_applies_maximum_limit(
        scorer: Scorer,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分应用最大值限制"""

    def return_small_logit(
            _features: Any,
    ) -> float:
        """返回极小 Logit"""
        return -1000.0

    monkeypatch.setattr(
        scorer.inference,
        "predict_logit",
        return_small_logit,
    )

    result = scorer.score({
        "feature_a": 0.0,
        "feature_b": 0.0,
    })

    assert (
        result
        == scorer.transformer.config.max_score
    )


def test_score_rejects_logit_list(
        scorer: Scorer,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分接口拒绝 Logit 列表"""

    def return_logit_list(
            _features: Any,
    ) -> list[float]:
        """返回 Logit 列表"""
        return [
            0.1,
            0.2,
        ]

    monkeypatch.setattr(
        scorer.inference,
        "predict_logit",
        return_logit_list,
    )

    with pytest.raises(
            TypeError,
            match="评分接口收到 Logit 列表",
    ):
        scorer.score({
            "feature_a": 0.0,
            "feature_b": 0.0,
        })


def test_score_batch_rejects_scalar_logit(
        scorer: Scorer,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量评分接口拒绝标量 Logit"""

    def return_scalar_logit(
            _features: Any,
    ) -> float:
        """返回标量 Logit"""
        return 0.5

    monkeypatch.setattr(
        scorer.inference,
        "predict_logit",
        return_scalar_logit,
    )

    with pytest.raises(
            TypeError,
            match="批量评分接口收到标量 Logit",
    ):
        scorer.score_batch([
            {
                "feature_a": 0.0,
                "feature_b": 0.0,
            },
        ])


def test_score_batch_returns_empty_list_for_empty_input(
        scorer: Scorer,
) -> None:
    """测试空批量输入返回空评分列表"""
    assert scorer.score_batch(
        []
    ) == []


def test_random_forest_is_rejected(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试非逻辑回归模型不能初始化评分器"""
    X, y = binary_training_data

    model = RandomForestClassifier(
        n_estimators=20,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    inference = Inference(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        Scorer(
            inference=inference
        )


def test_invalid_probability_is_delegated_to_transformer(
        scorer: Scorer,
) -> None:
    """测试非法概率由转换器校验"""
    with pytest.raises(
            ValueError,
            match=r"probability 必须在 \(0, 1\) 区间内",
    ):
        scorer.probability_to_score(
            1.0
        )


def test_invalid_logit_is_delegated_to_transformer(
        scorer: Scorer,
) -> None:
    """测试非法 Logit 由转换器校验"""
    with pytest.raises(
            ValueError,
            match="logit 必须是有限数值",
    ):
        scorer.logit_to_score(
            np.nan
        )
