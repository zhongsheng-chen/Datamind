# tests/core/model/adapters/test_base.py

"""基础模型适配器测试

验证模型适配器基类的输入转换、推理调度、特征校验、
正类解析、能力检查和默认回退行为。

核心功能：
  - 验证初始化和特征名称校验
  - 验证特征字典和批量特征转换
  - 验证概率预测和 Logit 预测调度
  - 验证批量预测回退实现
  - 验证特征类型校验
  - 验证正类索引解析
  - 验证单项和组合能力检查
  - 验证特征重要性接口
"""

from typing import Any
from types import SimpleNamespace

import numpy as np
import pytest

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.base import BaseModelAdapter


class BinaryModel:
    """二分类测试模型"""

    classes_ = np.array([
        0,
        1,
    ])


class NoClassesModel:
    """未提供类别信息的测试模型"""


class MulticlassModel:
    """多分类测试模型"""

    classes_ = np.array([
        0,
        1,
        2,
    ])


class ProbabilityAdapter(BaseModelAdapter):
    """概率预测测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """返回首行特征之和"""
        array = np.asarray(
            X,
            dtype=float,
        )

        return float(
            array[0].sum()
        )


class NoBatchAdapter(BaseModelAdapter):
    """不支持批量推理的测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
    )

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """返回首行特征之和"""
        array = np.asarray(
            X,
            dtype=float,
        )

        return float(
            array[0].sum()
        )


class LogitAdapter(ProbabilityAdapter):
    """Logit 预测测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.BATCH_PREDICT
    )

    def decision_function(
            self,
            X: np.ndarray,
    ) -> float:
        """返回首行特征之和作为 Logit"""
        array = np.asarray(
            X,
            dtype=float,
        )

        return float(
            array[0].sum()
        )


class DeclaredLogitAdapter(ProbabilityAdapter):
    """声明但未实现 Logit 接口的测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.BATCH_PREDICT
    )


class DeclaredImportanceAdapter(ProbabilityAdapter):
    """声明但未实现特征重要性接口的测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )


class ImportanceAdapter(ProbabilityAdapter):
    """特征重要性测试适配器"""

    SUPPORTED_CAPABILITIES = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    def get_feature_importance(
            self,
    ) -> dict[str, float]:
        """构造特征重要性结果"""
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        return self._build_feature_importance(
            [
                0.25,
                0.75,
            ],
            names=self.feature_names,
        )


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


def test_init_rejects_none_model(
) -> None:
    """测试模型不能为空"""
    with pytest.raises(
            ValueError,
            match="model 不能为空",
    ):
        ProbabilityAdapter(
            model=None
        )


def test_feature_names_are_copied_and_empty_list_becomes_none(
) -> None:
    """测试特征名称复制和空列表标准化"""
    feature_names = [
        "feature_a",
        "feature_b",
    ]

    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=feature_names,
    )

    feature_names.append(
        "feature_c"
    )

    assert adapter.feature_names == [
        "feature_a",
        "feature_b",
    ]

    empty_adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[],
    )

    assert empty_adapter.feature_names is None


@pytest.mark.parametrize(
    "feature_names",
    [
        [
            "feature_a",
            "",
        ],
        [
            "feature_a",
            "   ",
        ],
        [
            "feature_a",
            1,
        ],
        [
            "feature_a",
            "feature_a",
        ],
    ],
)
def test_invalid_feature_names_are_rejected(
        feature_names: list[Any],
) -> None:
    """测试拒绝非法特征名称"""
    with pytest.raises(
            ValueError,
            match="feature_names",
    ):
        ProbabilityAdapter(
            model=BinaryModel(),
            feature_names=feature_names,
        )


def test_capability_query_and_requirement(
) -> None:
    """测试能力查询和能力校验"""
    adapter = ProbabilityAdapter(
        model=BinaryModel()
    )

    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        adapter.get_capabilities()
        == expected
    )

    assert adapter.has_capability(
        ModelCapability.PREDICT_PROBA
    )

    assert not adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )

    adapter.require_capability(
        ModelCapability.PREDICT_PROBA
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        adapter.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )


def test_combined_capability_requires_all_requested_capabilities(
) -> None:
    """测试组合能力必须全部满足"""
    adapter = ProbabilityAdapter(
        model=BinaryModel()
    )
    requested = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
    )

    assert not adapter.has_capability(
        requested
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_PROBA.*PREDICT_LOG_ODDS",
    ):
        adapter.require_capability(
            requested
        )


def test_to_array_uses_configured_feature_order_and_converts_values(
) -> None:
    """测试特征转换顺序和值标准化"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "number",
            "flag",
            "category",
        ],
    )

    result = adapter.to_array({
        "category": "A",
        "flag": True,
        "number": 3,
    })

    assert result.shape == (
        1,
        3,
    )

    assert result.tolist() == [[
        3.0,
        1.0,
        "A",
    ]]


def test_to_array_ignores_extra_features_and_fills_missing_with_nan(
) -> None:
    """测试忽略额外字段并填充缺失值"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
            "feature_b",
        ],
    )

    result = adapter.to_array({
        "feature_a": 2,
        "extra": 99,
    })

    assert result[0, 0] == 2.0
    assert np.isnan(
        result[0, 1]
    )


def test_to_array_requires_features_and_feature_names(
) -> None:
    """测试特征转换前置条件"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
        ],
    )

    with pytest.raises(
            ValueError,
            match="features 不能为空",
    ):
        adapter.to_array({})

    adapter_without_names = ProbabilityAdapter(
        model=BinaryModel()
    )

    with pytest.raises(
            ValueError,
            match="feature_names 不能为空",
    ):
        adapter_without_names.to_array({
            "feature_a": 1,
        })


def test_to_array_batch_uses_configured_feature_order(
) -> None:
    """测试批量特征转换使用固定顺序"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
            "feature_b",
        ],
    )

    result = adapter.to_array_batch([
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


def test_to_array_batch_without_feature_names_uses_sorted_union(
) -> None:
    """测试未配置特征名称时按字段名排序"""
    adapter = ProbabilityAdapter(
        model=BinaryModel()
    )

    result = adapter.to_array_batch([
        {
            "feature_b": 2,
        },
        {
            "feature_a": 1,
        },
    ])

    assert result.shape == (
        2,
        2,
    )

    assert np.isnan(
        result[0, 0]
    )

    assert result[0, 1] == 2.0
    assert result[1, 0] == 1.0
    assert np.isnan(
        result[1, 1]
    )


def test_to_array_batch_rejects_invalid_input(
) -> None:
    """测试拒绝非法批量特征输入"""
    adapter = ProbabilityAdapter(
        model=BinaryModel()
    )

    with pytest.raises(
            ValueError,
            match="features_list 不能为空",
    ):
        adapter.to_array_batch([])

    invalid_batch: Any = [
        {
            "feature_a": 1,
        },
        2,
    ]

    with pytest.raises(
            TypeError,
            match="第 1 个元素类型为 int",
    ):
        adapter.to_array_batch(
            invalid_batch
        )

    with pytest.raises(
            ValueError,
            match="批量特征中不存在可用字段",
    ):
        adapter.to_array_batch([
            {},
        ])


def test_validate_features_reports_missing_and_type_errors(
) -> None:
    """测试特征完整性和类型校验"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "amount",
            "approved",
            "segment",
            "remark",
            "missing_feature",
        ],
        data_types={
            "amount": DataType.NUMERIC,
            "approved": DataType.BOOLEAN,
            "segment": DataType.CATEGORICAL,
            "remark": DataType.ANY,
            "missing_feature": DataType.NUMERIC,
        },
    )

    missing, type_errors = (
        adapter.validate_features({
            "amount": True,
            "approved": 2,
            "segment": 3,
            "remark": object(),
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


def test_validate_features_accepts_supported_values(
) -> None:
    """测试接受有效特征值"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "amount",
            "approved",
            "segment",
        ],
        data_types={
            "amount": DataType.NUMERIC,
            "approved": DataType.BOOLEAN,
            "segment": DataType.CATEGORICAL,
        },
    )

    missing, type_errors = (
        adapter.validate_features({
            "amount": np.float64(
                10.5
            ),
            "approved": 1,
            "segment": "A",
        })
    )

    assert missing == []
    assert type_errors == []


def test_predict_routes_scalar_and_batch_inputs(
) -> None:
    """测试概率预测统一入口"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
            "feature_b",
        ],
    )

    dictionary_result = require_scalar(
        adapter.predict({
            "feature_b": 2,
            "feature_a": 1,
        })
    )

    vector_result = require_scalar(
        adapter.predict(
            np.array([
                1.0,
                2.0,
            ])
        )
    )

    dictionary_batch_result = require_batch(
        adapter.predict([
            {
                "feature_a": 1,
                "feature_b": 2,
            },
            {
                "feature_a": 3,
                "feature_b": 4,
            },
        ])
    )

    array_batch_result = require_batch(
        adapter.predict(
            np.array([
                [
                    1.0,
                    2.0,
                ],
                [
                    3.0,
                    4.0,
                ],
            ])
        )
    )

    assert dictionary_result == pytest.approx(
        3.0
    )

    assert vector_result == pytest.approx(
        3.0
    )

    assert dictionary_batch_result == pytest.approx([
        3.0,
        7.0,
    ])

    assert array_batch_result == pytest.approx([
        3.0,
        7.0,
    ])

    assert adapter.predict([]) == []

    assert adapter.predict(
        np.array([])
    ) == []


def test_predict_requires_batch_capability(
) -> None:
    """测试批量预测必须声明批量能力"""
    adapter = NoBatchAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
        ],
    )

    with pytest.raises(
            NotImplementedError,
            match="BATCH_PREDICT",
    ):
        adapter.predict([
            {
                "feature_a": 1,
            },
        ])

    with pytest.raises(
            NotImplementedError,
            match="BATCH_PREDICT",
    ):
        adapter.predict(
            np.array([
                [
                    1.0,
                ],
            ])
        )


def test_predict_rejects_invalid_input(
) -> None:
    """测试拒绝非法概率预测输入"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
        ],
    )

    none_input: Any = None
    string_input: Any = "invalid"
    batch_input: Any = [
        {
            "feature_a": 1,
        },
        2,
    ]

    with pytest.raises(
            ValueError,
            match="输入不能为 None",
    ):
        adapter.predict(
            none_input
        )

    with pytest.raises(
            TypeError,
            match="不支持输入类型: str",
    ):
        adapter.predict(
            string_input
        )

    with pytest.raises(
            TypeError,
            match="批量输入必须全部为特征字典",
    ):
        adapter.predict(
            batch_input
        )

    with pytest.raises(
            ValueError,
            match="当前 ndim=3",
    ):
        adapter.predict(
            np.ones(
                (
                    1,
                    1,
                    1,
                )
            )
        )

    with pytest.raises(
            ValueError,
            match="当前 ndim=3",
    ):
        adapter.predict(
            np.empty(
                (
                    0,
                    1,
                    1,
                )
            )
        )


def test_predict_logit_routes_scalar_and_batch_inputs(
) -> None:
    """测试 Logit 预测统一入口"""
    adapter = LogitAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
            "feature_b",
        ],
    )

    scalar_result = require_scalar(
        adapter.predict_logit({
            "feature_a": 1,
            "feature_b": 2,
        })
    )

    batch_result = require_batch(
        adapter.predict_logit([
            {
                "feature_a": 1,
                "feature_b": 2,
            },
            {
                "feature_a": 3,
                "feature_b": 4,
            },
        ])
    )

    assert scalar_result == pytest.approx(
        3.0
    )

    assert batch_result == pytest.approx([
        3.0,
        7.0,
    ])


def test_predict_logit_requires_capability_and_implementation(
) -> None:
    """测试 Logit 能力和接口实现要求"""
    adapter = ProbabilityAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
        ],
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        adapter.predict_logit({
            "feature_a": 1,
        })

    declared_adapter = DeclaredLogitAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
        ],
    )

    with pytest.raises(
            NotImplementedError,
            match="未实现 Logit 预测接口",
    ):
        declared_adapter.predict_logit({
            "feature_a": 1,
        })


def test_predict_logit_rejects_empty_three_dimensional_array(
) -> None:
    """测试空三维数组不能绕过 Logit 输入维度校验"""
    adapter = LogitAdapter(
        model=BinaryModel()
    )

    with pytest.raises(
            ValueError,
            match="当前 ndim=3",
    ):
        adapter.predict_logit(
            np.empty(
                (
                    0,
                    1,
                    1,
                )
            )
        )


def test_get_positive_class_index(
) -> None:
    """测试正类索引解析"""
    positive_one = ProbabilityAdapter(
        model=BinaryModel(),
        positive_class=1,
    )

    positive_zero = ProbabilityAdapter(
        model=BinaryModel(),
        positive_class=0,
    )

    no_classes = ProbabilityAdapter(
        model=NoClassesModel(),
        positive_class="bad",
    )

    assert (
        positive_one.get_positive_class_index()
        == 1
    )

    assert (
        positive_zero.get_positive_class_index()
        == 0
    )

    assert (
        no_classes.get_positive_class_index()
        == 1
    )


def test_get_positive_class_index_rejects_invalid_classes(
) -> None:
    """测试拒绝非法类别配置"""
    multiclass_adapter = ProbabilityAdapter(
        model=MulticlassModel(),
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="仅支持二分类模型",
    ):
        multiclass_adapter.get_positive_class_index()

    missing_class_adapter = ProbabilityAdapter(
        model=BinaryModel(),
        positive_class="bad",
    )

    with pytest.raises(
            ValueError,
            match="模型类别中不存在指定正类",
    ):
        missing_class_adapter.get_positive_class_index()


@pytest.mark.parametrize(
    ("class_count", "message"),
    [
        (
            np.int64(3),
            "当前类别数=3",
        ),
        (
            "2",
            "模型类别数必须为整数",
        ),
    ],
)
def test_validate_binary_model_rejects_invalid_class_count(
        class_count: Any,
        message: str,
) -> None:
    """测试拒绝多分类和非整数类别数元数据"""
    adapter = ProbabilityAdapter(
        model=SimpleNamespace(
            n_classes_=class_count,
        )
    )

    with pytest.raises(
            ValueError,
            match=message,
    ):
        adapter._validate_binary_model()


def test_feature_importance_public_interface(
) -> None:
    """测试特征重要性公开接口"""
    adapter = ImportanceAdapter(
        model=BinaryModel(),
        feature_names=[
            "feature_a",
            "feature_b",
        ],
    )

    assert adapter.get_feature_importance() == {
        "feature_a": 0.25,
        "feature_b": 0.75,
    }

    default_names_adapter = ImportanceAdapter(
        model=BinaryModel()
    )

    assert (
        default_names_adapter.get_feature_importance()
        == {
            "f0": 0.25,
            "f1": 0.75,
        }
    )


def test_feature_importance_requires_implementation(
) -> None:
    """测试特征重要性能力必须实现对应接口"""
    adapter = DeclaredImportanceAdapter(
        model=BinaryModel()
    )

    with pytest.raises(
            NotImplementedError,
            match="未实现特征重要性",
    ):
        adapter.get_feature_importance()

    probability_adapter = ProbabilityAdapter(
        model=BinaryModel()
    )

    with pytest.raises(
            NotImplementedError,
            match="FEATURE_IMPORTANCE",
    ):
        probability_adapter.get_feature_importance()


def test_feature_importance_rejects_invalid_values_and_names(
) -> None:
    """测试特征重要性结果校验"""

    class InvalidValueAdapter(ImportanceAdapter):
        """包含非法重要性数值的测试适配器"""

        def get_feature_importance(
                self,
        ) -> dict[str, float]:
            return self._build_feature_importance([
                0.5,
                np.nan,
            ])

    class InvalidNameCountAdapter(
        ImportanceAdapter
    ):
        """特征名称数量不一致的测试适配器"""

        def get_feature_importance(
                self,
        ) -> dict[str, float]:
            return self._build_feature_importance(
                [
                    0.5,
                    0.5,
                ],
                names=[
                    "feature_a",
                ],
            )

    with pytest.raises(
            ValueError,
            match="特征重要性包含非有限数值",
    ):
        InvalidValueAdapter(
            model=BinaryModel()
        ).get_feature_importance()

    with pytest.raises(
            ValueError,
            match="特征名称数量与特征重要性数量不一致",
    ):
        InvalidNameCountAdapter(
            model=BinaryModel()
        ).get_feature_importance()
