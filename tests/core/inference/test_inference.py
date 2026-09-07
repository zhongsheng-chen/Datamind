# tests/core/inference/test_inference.py

"""统一推理接口测试

验证统一推理入口的适配器创建、概率预测、对数几率预测、
特征转换、特征校验、特征重要性和能力查询。

核心功能：
  - test_init_creates_sklearn_adapter:
    验证初始化时创建 Sklearn 适配器
  - test_predict_matches_model:
    验证概率预测与原始模型一致
  - test_predict_batch_matches_model:
    验证批量概率预测与原始模型一致
  - test_predict_logit_matches_model:
    验证对数几率预测与原始模型一致
  - test_predict_logit_batch_matches_model:
    验证批量对数几率预测与原始模型一致
  - test_positive_class_zero_reverses_logit_direction:
    验证正类为类别零时反转对数几率方向
  - test_transform_uses_configured_feature_order:
    验证特征转换使用配置顺序
  - test_transform_fills_missing_feature_with_nan:
    验证特征转换填充缺失值
  - test_transform_batch_uses_configured_feature_order:
    验证批量特征转换使用配置顺序
  - test_transform_requires_feature_names:
    验证特征转换必须配置特征名称
  - test_validate_features_delegates_to_adapter:
    验证特征校验结果
  - test_get_feature_importance_matches_coefficients:
    验证特征重要性与逻辑回归系数一致
  - test_capability_query_and_requirement:
    验证能力查询和能力校验
  - test_random_forest_does_not_support_logit:
    验证非逻辑回归模型不提供对数几率能力
  - test_invalid_prediction_input_is_delegated:
    验证非法推理输入由适配器校验
  - test_unsupported_model_is_rejected:
    验证拒绝未支持的模型框架"""

from typing import Any

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.inference import Inference
from datamind.core.inference.adapters.sklearn import SklearnAdapter


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


DATA_TYPES = {
    "feature_a": DataType.NUMERIC,
    "feature_b": DataType.NUMERIC,
}


def require_scalar(
        value: float | list[float],
) -> float:
    """校验推理结果为标量"""
    if isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "推理结果应为 float"
        )

    return value


def require_batch(
        value: float | list[float],
) -> list[float]:
    """校验推理结果为列表"""
    if not isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "推理结果应为 list[float]"
        )

    return value


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
        data_types=DATA_TYPES,
        positive_class=1,
    )


def test_init_creates_sklearn_adapter(
        logistic_model: LogisticRegression,
) -> None:
    """测试初始化时创建 Sklearn 适配器"""
    inference = Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        data_types=DATA_TYPES,
        positive_class=0,
    )

    assert isinstance(
        inference.adapter,
        SklearnAdapter,
    )

    assert inference.adapter.model is logistic_model
    assert inference.adapter.feature_names == FEATURE_NAMES
    assert inference.adapter.data_types == DATA_TYPES
    assert inference.adapter.positive_class == 0


def test_predict_matches_model(
        logistic_model: LogisticRegression,
        inference: Inference,
) -> None:
    """测试概率预测与原始模型一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected = float(
        logistic_model.predict_proba(
            array
        )[0, 1]
    )

    result = require_scalar(
        inference.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_batch_matches_model(
        logistic_model: LogisticRegression,
        inference: Inference,
) -> None:
    """测试批量概率预测与原始模型一致"""
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

    expected = (
        logistic_model.predict_proba(
            array
        )[:, 1]
    )

    result = require_batch(
        inference.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_predict_logit_matches_model(
        logistic_model: LogisticRegression,
        inference: Inference,
) -> None:
    """测试对数几率预测与原始模型一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected = float(
        logistic_model.decision_function(
            array
        )[0]
    )

    result = require_scalar(
        inference.predict_logit(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_logit_batch_matches_model(
        logistic_model: LogisticRegression,
        inference: Inference,
) -> None:
    """测试批量对数几率预测与原始模型一致"""
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

    expected = logistic_model.decision_function(
        array
    )

    result = require_batch(
        inference.predict_logit(
            features
        )
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_positive_class_zero_reverses_logit_direction(
        logistic_model: LogisticRegression,
) -> None:
    """测试正类为类别零时反转对数几率方向"""
    inference = Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        data_types=DATA_TYPES,
        positive_class=0,
    )

    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected_probability = float(
        logistic_model.predict_proba(
            array
        )[0, 0]
    )

    expected_logit = -float(
        logistic_model.decision_function(
            array
        )[0]
    )

    probability = require_scalar(
        inference.predict(
            features
        )
    )

    logit = require_scalar(
        inference.predict_logit(
            features
        )
    )

    assert probability == pytest.approx(
        expected_probability
    )

    assert logit == pytest.approx(
        expected_logit
    )


def test_transform_uses_configured_feature_order(
        inference: Inference,
) -> None:
    """测试特征转换使用配置顺序"""
    result = inference.transform({
        "feature_b": 2,
        "feature_a": 1,
        "extra": 99,
    })

    assert result.shape == (
        1,
        2,
    )

    assert result.tolist() == [[
        1.0,
        2.0,
    ]]


def test_transform_fills_missing_feature_with_nan(
        inference: Inference,
) -> None:
    """测试特征转换填充缺失值"""
    result = inference.transform({
        "feature_a": 1,
    })

    assert result[0, 0] == 1.0

    assert np.isnan(
        result[0, 1]
    )


def test_transform_batch_uses_configured_feature_order(
        inference: Inference,
) -> None:
    """测试批量特征转换使用配置顺序"""
    result = inference.transform_batch([
        {
            "feature_b": 2,
            "feature_a": 1,
        },
        {
            "feature_a": 3,
        },
    ])

    assert result.shape == (
        2,
        2,
    )

    assert result[0].tolist() == [
        1.0,
        2.0,
    ]

    assert result[1, 0] == 3.0

    assert np.isnan(
        result[1, 1]
    )


def test_transform_requires_feature_names(
        logistic_model: LogisticRegression,
) -> None:
    """测试特征转换必须配置特征名称"""
    inference = Inference(
        model=logistic_model,
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="feature_names 不能为空",
    ):
        inference.transform({
            "feature_a": 1,
        })


def test_validate_features_delegates_to_adapter(
        logistic_model: LogisticRegression,
) -> None:
    """测试特征校验结果"""
    inference = Inference(
        model=logistic_model,
        feature_names=[
            "amount",
            "approved",
            "segment",
            "missing_feature",
        ],
        data_types={
            "amount": DataType.NUMERIC,
            "approved": DataType.BOOLEAN,
            "segment": DataType.CATEGORICAL,
            "missing_feature": DataType.NUMERIC,
        },
        positive_class=1,
    )

    missing, type_errors = (
        inference.validate_features({
            "amount": True,
            "approved": 2,
            "segment": 3,
        })
    )

    assert missing == [
        "missing_feature",
    ]

    assert type_errors == [
        (
            "amount",
            "numeric",
            "bool",
        ),
        (
            "approved",
            "boolean",
            "int",
        ),
        (
            "segment",
            "categorical",
            "int",
        ),
    ]


def test_get_feature_importance_matches_coefficients(
        logistic_model: LogisticRegression,
        inference: Inference,
) -> None:
    """测试特征重要性与逻辑回归系数一致"""
    expected = np.abs(
        logistic_model.coef_[0]
    )

    result = inference.get_feature_importance()

    assert list(
        result
    ) == FEATURE_NAMES

    assert list(
        result.values()
    ) == pytest.approx(
        expected.tolist()
    )


def test_capability_query_and_requirement(
        inference: Inference,
) -> None:
    """测试能力查询和能力校验"""
    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        inference.get_capabilities()
        == expected
    )

    assert inference.has_capability(
        ModelCapability.PREDICT_PROBA
    )

    assert inference.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )

    inference.require_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )


def test_random_forest_does_not_support_logit(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试非逻辑回归模型不提供对数几率能力"""
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
        data_types=DATA_TYPES,
        positive_class=1,
    )

    assert not inference.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        inference.predict_logit({
            "feature_a": 0.1,
            "feature_b": 0.2,
        })


def test_invalid_prediction_input_is_delegated(
        inference: Inference,
) -> None:
    """测试非法推理输入由适配器校验"""
    none_input: Any = None
    string_input: Any = "invalid"

    with pytest.raises(
            ValueError,
            match="输入不能为 None",
    ):
        inference.predict(
            none_input
        )

    with pytest.raises(
            TypeError,
            match="不支持输入类型: str",
    ):
        inference.predict(
            string_input
        )


def test_unsupported_model_is_rejected(
) -> None:
    """测试拒绝未支持的模型框架"""

    class UnsupportedModel:
        """未支持模型测试类"""

    with pytest.raises(
            ValueError,
            match="不支持的模型类型: UnsupportedModel",
    ):
        Inference(
            model=UnsupportedModel()
        )
