# tests/core/inference/adapters/test_xgboost.py

"""XGBoost 模型适配器测试

验证 XGBoost 二分类模型的能力检测、概率预测、批量预测、
正类选择、Gain 特征重要性和异常处理。

核心功能：
  - test_xgboost_capabilities:
    验证 XGBoost 声明分类推理能力
  - test_predict_probability_matches_model:
    验证概率预测与原始模型一致
  - test_predict_probability_batch_matches_model:
    验证批量概率预测与原始模型一致
  - test_positive_class_zero_selects_first_probability_column:
    验证正类为类别零时选择第一列概率
  - test_predict_logit_is_not_supported:
    验证 XGBoost 不提供对数几率预测
  - test_gain_feature_importance_matches_booster:
    验证 Gain 特征重要性与 Booster 一致
  - test_feature_importance_fills_unused_feature_with_zero:
    验证未参与分裂的特征重要性补零
  - test_feature_importance_uses_booster_feature_names:
    验证 Booster 特征名与展示特征名映射
  - test_feature_importance_uses_sorted_score_names_as_fallback:
    验证缺少特征元数据时按名称排序
  - test_feature_name_count_must_match_model:
    验证展示特征数量必须与模型一致
  - test_invalid_model_feature_count_is_rejected:
    验证拒绝非整数模型特征数量
  - test_probability_only_model_does_not_support_importance:
    验证无 Booster 模型不声明特征重要性
  - test_missing_probability_interface_is_rejected:
    验证拒绝不提供概率接口的模型
  - test_untrained_model_is_rejected:
    验证拒绝未训练模型
  - test_multiclass_model_is_rejected:
    验证拒绝多分类模型
  - test_missing_positive_class_is_rejected:
    验证模型类别中必须存在指定正类
  - test_invalid_probability_output_is_rejected:
    验证拒绝非法概率预测结果
  - test_invalid_probability_for_positive_class_zero_is_rejected:
    验证正类为类别零时校验第一列概率"""

from typing import Any

import numpy as np
import pytest

pytest.importorskip(
    "xgboost"
)

from xgboost import XGBClassifier

from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.xgboost import XGBoostAdapter


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


class FakeBooster:
    """XGBoost Booster 测试替身"""

    def __init__(
            self,
            score: dict[str, float],
            feature_names: list[str] | None = None,
    ) -> None:
        self._score = dict(
            score
        )
        self.feature_names = feature_names

    def get_score(
            self,
            *,
            importance_type: str,
    ) -> dict[str, float]:
        """返回固定特征重要性"""
        if importance_type != "gain":
            raise AssertionError(
                "importance_type 应为 gain"
            )

        return dict(
            self._score
        )


class FakeXGBoostModel:
    """XGBoost 分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
    ])

    def __init__(
            self,
            probabilities: Any,
            *,
            booster: FakeBooster | None = None,
            feature_count: Any = 2,
    ) -> None:
        self._probabilities = probabilities
        self._booster = (
            booster
            if booster is not None
            else FakeBooster({})
        )

        if feature_count is not None:
            self.n_features_in_ = feature_count

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> Any:
        """返回固定概率结果"""
        values = np.asarray(
            self._probabilities
        )

        sample_count = len(
            np.asarray(X)
        )

        if (
                values.ndim == 2
                and values.shape[0] == 1
                and sample_count > 1
        ):
            return np.repeat(
                values,
                sample_count,
                axis=0,
            )

        return values

    def get_booster(
            self,
    ) -> FakeBooster:
        """返回 Booster 测试替身"""
        return self._booster


class ProbabilityOnlyModel:
    """不提供 Booster 的分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
    ])

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.4,
                0.6,
            ],
        ])

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """返回固定概率"""
        sample_count = len(
            np.asarray(X)
        )

        return np.repeat(
            self.probabilities,
            sample_count,
            axis=0,
        )


class MissingProbabilityModel:
    """未提供概率接口的测试模型"""

    classes_ = np.array([
        0,
        1,
    ])


class UntrainedModel:
    """未训练分类模型测试替身"""

    classes_ = None

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.4,
                0.6,
            ],
        ])

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """返回固定概率"""
        sample_count = len(
            np.asarray(X)
        )

        return np.repeat(
            self.probabilities,
            sample_count,
            axis=0,
        )


class MulticlassModel:
    """多分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
        2,
    ])

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.2,
                0.3,
                0.5,
            ],
        ])

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """返回多分类概率"""
        sample_count = len(
            np.asarray(X)
        )

        return np.repeat(
            self.probabilities,
            sample_count,
            axis=0,
        )


def require_importance_value(
        value: float | list[float],
) -> float:
    """校验特征重要性为标量"""
    if isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "Gain 特征重要性应为 float"
        )

    return value


def require_scalar(
        value: float | list[float],
) -> float:
    """校验预测结果为标量"""
    if isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "预测结果应为 float"
        )

    return value


def require_batch(
        value: float | list[float],
) -> list[float]:
    """校验预测结果为列表"""
    if not isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "预测结果应为 list[float]"
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
def xgboost_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> XGBClassifier:
    """提供已训练 XGBoost 二分类模型"""
    X, y = binary_training_data

    model = XGBClassifier(
        n_estimators=12,
        max_depth=2,
        learning_rate=0.3,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=0,
        n_jobs=1,
        verbosity=0,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.fixture
def xgboost_adapter(
        xgboost_model: XGBClassifier,
) -> XGBoostAdapter:
    """提供 XGBoost 模型适配器"""
    return XGBoostAdapter(
        model=xgboost_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


def test_xgboost_capabilities(
        xgboost_adapter: XGBoostAdapter,
) -> None:
    """测试 XGBoost 声明分类推理能力"""
    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        xgboost_adapter.get_capabilities()
        == expected
    )

    assert not xgboost_adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )


def test_predict_probability_matches_model(
        xgboost_model: XGBClassifier,
        xgboost_adapter: XGBoostAdapter,
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
        xgboost_model.predict_proba(
            array
        )[0, 1]
    )

    result = require_scalar(
        xgboost_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_probability_batch_matches_model(
        xgboost_model: XGBClassifier,
        xgboost_adapter: XGBoostAdapter,
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
        xgboost_model.predict_proba(
            array
        )[:, 1]
    )

    result = require_batch(
        xgboost_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_positive_class_zero_selects_first_probability_column(
        xgboost_model: XGBClassifier,
) -> None:
    """测试正类为类别零时选择第一列概率"""
    adapter = XGBoostAdapter(
        model=xgboost_model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected = float(
        xgboost_model.predict_proba(
            array
        )[0, 0]
    )

    result = require_scalar(
        adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_logit_is_not_supported(
        xgboost_adapter: XGBoostAdapter,
) -> None:
    """测试 XGBoost 不提供对数几率预测"""
    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        xgboost_adapter.predict_logit(
            np.array([
                -0.75,
                0.25,
            ])
        )


def test_gain_feature_importance_matches_booster(
        xgboost_model: XGBClassifier,
        xgboost_adapter: XGBoostAdapter,
) -> None:
    """测试 Gain 特征重要性与 Booster 一致"""
    raw_score = (
        xgboost_model.get_booster().get_score(
            importance_type="gain"
        )
    )

    expected = {
        name: require_importance_value(
            raw_score.get(
                f"f{index}",
                0.0,
            )
        )
        for index, name in enumerate(
            FEATURE_NAMES
        )
    }

    result = (
        xgboost_adapter.get_feature_importance()
    )

    assert list(
        result
    ) == FEATURE_NAMES

    assert result == pytest.approx(
        expected
    )


def test_feature_importance_fills_unused_feature_with_zero(
) -> None:
    """测试未参与分裂的特征重要性补零"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster({
            "f0": 2.5,
        }),
        feature_count=2,
    )

    adapter = XGBoostAdapter(
        model=model,
        feature_names=[
            "used_feature",
            "unused_feature",
        ],
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "used_feature": 2.5,
        "unused_feature": 0.0,
    }


def test_feature_importance_uses_booster_feature_names(
) -> None:
    """测试 Booster 特征名与展示特征名映射"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            {
                "raw_age": 1.5,
                "raw_income": 3.0,
            },
            feature_names=[
                "raw_age",
                "raw_income",
            ],
        ),
        feature_count=2,
    )

    adapter = XGBoostAdapter(
        model=model,
        feature_names=[
            "age",
            "income",
        ],
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "age": 1.5,
        "income": 3.0,
    }


def test_feature_importance_uses_sorted_score_names_as_fallback(
) -> None:
    """测试缺少特征元数据时按名称排序"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster({
            "f10": 1.0,
            "custom": 3.0,
            "f2": 2.0,
        }),
        feature_count=None,
    )

    adapter = XGBoostAdapter(
        model=model,
        positive_class=1,
    )

    result = adapter.get_feature_importance()

    assert list(
        result
    ) == [
        "f2",
        "f10",
        "custom",
    ]

    assert result == {
        "f2": 2.0,
        "f10": 1.0,
        "custom": 3.0,
    }


def test_feature_name_count_must_match_model(
) -> None:
    """测试展示特征数量必须与模型一致"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster({
            "f0": 1.0,
            "f1": 2.0,
        }),
        feature_count=2,
    )

    adapter = XGBoostAdapter(
        model=model,
        feature_names=[
            "feature_a",
        ],
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征名称数量与模型特征数量不一致",
    ):
        adapter.get_feature_importance()


@pytest.mark.parametrize(
    "feature_count",
    [
        True,
        "2",
    ],
)
def test_invalid_model_feature_count_is_rejected(
        feature_count: Any,
) -> None:
    """测试拒绝非整数模型特征数量"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        feature_count=feature_count,
    )
    adapter = XGBoostAdapter(
        model=model,
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="模型特征数量必须为整数",
    ):
        adapter._get_feature_count()


def test_probability_only_model_does_not_support_importance(
) -> None:
    """测试无 Booster 模型不声明特征重要性"""
    adapter = XGBoostAdapter(
        model=ProbabilityOnlyModel(),
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        adapter.get_capabilities()
        == expected
    )

    with pytest.raises(
            NotImplementedError,
            match="FEATURE_IMPORTANCE",
    ):
        adapter.get_feature_importance()


def test_missing_probability_interface_is_rejected(
) -> None:
    """测试拒绝不提供概率接口的模型"""
    with pytest.raises(
            TypeError,
            match="仅支持提供 predict_proba 接口",
    ):
        XGBoostAdapter(
            model=MissingProbabilityModel(),
            feature_names=FEATURE_NAMES,
        )


def test_untrained_model_is_rejected(
) -> None:
    """测试拒绝未训练模型"""
    with pytest.raises(
            ValueError,
            match="模型尚未训练或不属于分类模型",
    ):
        XGBoostAdapter(
            model=UntrainedModel(),
            feature_names=FEATURE_NAMES,
        )


def test_multiclass_model_is_rejected(
) -> None:
    """测试拒绝多分类模型"""
    with pytest.raises(
            ValueError,
            match="仅支持二分类模型",
    ):
        XGBoostAdapter(
            model=MulticlassModel(),
            feature_names=FEATURE_NAMES,
            positive_class=1,
        )


def test_missing_positive_class_is_rejected(
        xgboost_model: XGBClassifier,
) -> None:
    """测试模型类别中必须存在指定正类"""
    with pytest.raises(
            ValueError,
            match="模型类别中不存在指定正类",
    ):
        XGBoostAdapter(
            model=xgboost_model,
            feature_names=FEATURE_NAMES,
            positive_class="bad",
        )


@pytest.mark.parametrize(
    (
        "probabilities",
        "error_type",
        "message",
    ),
    [
        (
            [
                0.4,
                0.6,
            ],
            NotImplementedError,
            "仅支持二维概率预测结果",
        ),
        (
            [
                [
                    0.2,
                    0.3,
                    0.5,
                ],
            ],
            NotImplementedError,
            "仅支持二分类概率预测",
        ),
        (
            [
                [
                    -0.1,
                    1.1,
                ],
            ],
            ValueError,
            "模型返回了非法概率值",
        ),
        (
            [
                [
                    0.4,
                    np.nan,
                ],
            ],
            ValueError,
            "模型返回了非法概率值",
        ),
    ],
)
def test_invalid_probability_output_is_rejected(
        probabilities: Any,
        error_type: type[Exception],
        message: str,
) -> None:
    """测试拒绝非法概率预测结果"""
    model = FakeXGBoostModel(
        probabilities=probabilities,
    )

    adapter = XGBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            error_type,
            match=message,
    ):
        adapter.predict(
            np.array([
                0.1,
                0.2,
            ])
        )


def test_invalid_probability_for_positive_class_zero_is_rejected(
) -> None:
    """测试正类为类别零时校验第一列概率"""
    model = FakeXGBoostModel(
        probabilities=[
            [
                np.nan,
                0.6,
            ],
        ],
    )

    adapter = XGBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    with pytest.raises(
            ValueError,
            match="模型返回了非法概率值",
    ):
        adapter.predict(
            np.array([
                0.1,
                0.2,
            ])
        )
