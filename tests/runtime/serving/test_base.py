"""运行时服务基类测试

验证统一结果、模型能力、访问状态以及特征元数据解析行为。

核心功能：
  - test_service_exposes_runtime_information:
    验证服务公开运行时模型信息
  - test_service_handles_capability_operations:
    验证服务处理模型能力操作
  - test_service_touch_updates_runtime_access_state:
    验证服务更新运行时模型访问状态
  - test_service_accepts_explicit_feature_schema:
    验证服务接受显式特征 Schema
  - test_service_ignores_schema_in_runtime_metadata:
    验证服务不再读取运行时元数据中的 Schema
  - test_service_infers_feature_names_from_model_attribute:
    验证从模型属性推断特征名称
  - test_service_infers_feature_names_from_booster:
    验证从 Booster 推断特征名称
  - test_service_returns_none_when_feature_names_cannot_be_inferred:
    验证无法推断特征名称时返回 None
  - test_service_rejects_missing_runtime_model:
    验证服务拒绝缺失运行时模型
"""

from types import SimpleNamespace
from typing import Any

import pytest

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


CAPABILITIES = (
    ModelCapability.PREDICT_PROBA
    | ModelCapability.BATCH_PREDICT
)


class RuntimeServiceStub(BaseRuntimeService):
    """可实例化的运行时服务替身"""

    SERVICE_TYPE = "test"

    def get_capabilities(self) -> ModelCapability:
        """获取测试服务能力集"""
        return CAPABILITIES

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        return self.build_result(features)

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.build_result({
            "predictions": features_list,
        })


def create_runtime_model(
        *,
        model: Any = None,
        metadata: dict[str, Any] | None = None,
        framework: str = "sklearn",
) -> RuntimeModel:
    """创建运行时模型"""
    return RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework=framework,
        model=model if model is not None else object(),
        metadata=metadata or {},
    )


def test_service_exposes_runtime_information() -> None:
    """测试服务公开运行时模型信息"""
    runtime_model = create_runtime_model()
    service = RuntimeServiceStub(
        runtime_model=runtime_model
    )

    result = service.build_result({
        "probability": 0.8,
    })

    assert service.deployment_id == "dep_test"
    assert service.model_id == "mdl_test"
    assert service.version_id == "ver_test"
    assert service.framework == "sklearn"
    assert service.metadata == {}
    assert result == {
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "service_type": "test",
        "probability": 0.8,
    }


def test_service_handles_capability_operations() -> None:
    """测试服务处理模型能力操作"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model()
    )

    assert service.get_capabilities() == CAPABILITIES
    assert service.get_capability_names() == [
        "PREDICT_PROBA",
        "BATCH_PREDICT",
    ]
    assert service.has_capability(
        ModelCapability.PREDICT_PROBA
    ) is True

    with pytest.raises(
            NotImplementedError,
            match="RuntimeServiceStub 不支持能力: PREDICT_LOG_ODDS",
    ):
        service.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )


def test_service_touch_updates_runtime_access_state() -> None:
    """测试服务记录运行时模型访问状态"""
    runtime_model = create_runtime_model()
    service = RuntimeServiceStub(
        runtime_model=runtime_model
    )

    service.touch()

    assert runtime_model.access_count == 1
    assert runtime_model.last_used_at is not None


def test_service_accepts_explicit_feature_schema() -> None:
    """测试服务接受显式传入的特征名称和类型"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(),
        feature_names=[
            "age",
            "income",
            "employment_type",
        ],
        data_types={
            "age": DataType.NUMERIC,
            "income": DataType.NUMERIC,
            "employment_type": DataType.CATEGORICAL,
        },
    )

    assert service.feature_names == [
        "age",
        "income",
        "employment_type",
    ]
    assert service.data_types == {
        "age": DataType.NUMERIC,
        "income": DataType.NUMERIC,
        "employment_type": DataType.CATEGORICAL,
    }


def test_service_ignores_schema_in_runtime_metadata() -> None:
    """测试服务不再从运行时元数据读取特征 Schema"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(metadata={
            "feature_names": ["age"],
            "data_types": {"age": "numeric"},
        })
    )

    assert service.feature_names is None
    assert service.data_types == {}


@pytest.mark.parametrize(
    ("framework", "attribute_name"),
    [
        ("sklearn", "feature_names_in_"),
        ("xgboost", "feature_names_in_"),
        ("lightgbm", "feature_name_"),
        ("catboost", "feature_names_"),
    ],
)
def test_service_infers_feature_names_from_model_attribute(
        framework: str,
        attribute_name: str,
) -> None:
    """测试服务从模型属性推断特征名称"""
    model = SimpleNamespace(**{
        attribute_name: ["age", "annual_income"],
    })
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(
            model=model,
            framework=framework,
        )
    )

    assert service.feature_names == [
        "age",
        "annual_income",
    ]


def test_service_infers_feature_names_from_booster() -> None:
    """测试服务从 XGBoost Booster 推断特征名称"""
    class ModelStub:
        """提供 Booster 的模型替身"""

        @staticmethod
        def get_booster() -> SimpleNamespace:
            return SimpleNamespace(
                feature_names=["age", "annual_income"]
            )

    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(
            model=ModelStub(),
            framework="xgboost",
        )
    )

    assert service.feature_names == [
        "age",
        "annual_income",
    ]


@pytest.mark.parametrize(
    ("framework", "model"),
    [
        ("sklearn", object()),
        ("lightgbm", SimpleNamespace()),
        ("xgboost", SimpleNamespace(get_booster=lambda: SimpleNamespace(
            feature_names=None
        ))),
    ],
)
def test_service_returns_none_when_feature_names_cannot_be_inferred(
        framework: str,
        model: Any,
) -> None:
    """测试无法推断模型特征名称时返回空值"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(
            model=model,
            framework=framework,
        )
    )

    assert service.feature_names is None


def test_service_rejects_missing_runtime_model() -> None:
    """测试服务拒绝空运行时模型"""
    runtime_model: Any = None

    with pytest.raises(
            ValueError,
            match="runtime_model 不能为空",
    ):
        RuntimeServiceStub(
            runtime_model=runtime_model,
        )
