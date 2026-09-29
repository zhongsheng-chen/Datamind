"""分类模型运行服务测试.

验证分类阈值、单条预测、批量预测和异常结果处理。

核心功能：
  - test_service_rejects_invalid_threshold:
    验证服务拒绝无效分类阈值
  - test_predict_classifies_probability:
    验证单条概率转换为分类结果
  - test_predict_rejects_batch_result:
    验证单条预测拒绝批量结果
  - test_predict_batch_returns_classifications:
    验证批量预测返回分类结果
  - test_predict_batch_rejects_scalar_result:
    验证批量预测拒绝标量结果
  - test_predict_rejects_invalid_feature_type:
    验证单条和批量分类在模型执行前拒绝非法特征类型
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

import datamind.runtime.serving.classification_service as service_module
from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.classification_service import (
    ClassificationService,
)


def create_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        prediction: Any = 0.8,
        threshold: float = 0.5,
        feature_names: list[str] | None = None,
        data_types: dict[str, DataType] | None = None,
) -> tuple[ClassificationService, MagicMock]:
    """创建使用推理替身的分类服务."""
    inference = MagicMock()
    inference.get_capabilities.return_value = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )
    inference.predict.return_value = prediction
    monkeypatch.setitem(
        vars(service_module),
        "Inference",
        lambda **_kwargs: inference,
    )
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
    )

    return (
        ClassificationService(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
            threshold=threshold,
        ),
        inference,
    )


@pytest.mark.parametrize(
    "threshold",
    [-0.1, 1.1],
)
def test_service_rejects_invalid_threshold(
        threshold: float,
) -> None:
    """测试分类服务拒绝范围外阈值."""
    with pytest.raises(
            ValueError,
            match="threshold 必须在 0 到 1 之间",
    ):
        ClassificationService(
            runtime_model=RuntimeModel(
                deployment_id="dep_test",
                model_id="mdl_test",
                version_id="ver_test",
                framework="sklearn",
                model=object(),
            ),
            threshold=threshold,
        )


def test_service_uses_model_second_class_as_positive_class(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试分类服务从模型类别顺序识别字符串正类."""
    class StringLabelModel:
        """带字符串类别的分类模型测试替身."""

        classes_ = (
            "accepted",
            "flagged",
        )

    inference = MagicMock()
    inference.get_capabilities.return_value = (
        ModelCapability.PREDICT_PROBA
    )
    inference_factory = MagicMock(
        return_value=inference
    )
    monkeypatch.setitem(
        vars(service_module),
        "Inference",
        inference_factory,
    )
    model = StringLabelModel()

    service = ClassificationService(
        runtime_model=RuntimeModel(
            deployment_id="dep_test",
            model_id="mdl_test",
            version_id="ver_test",
            framework="sklearn",
            model=model,
        ),
    )
    inference.predict.return_value = 0.8
    result = service.predict({
        "transaction_amount": 100.0,
    })

    assert (
        inference_factory.call_args.kwargs[
            "positive_class"
        ]
        == "flagged"
    )
    assert service.class_labels == (
        "accepted",
        "flagged",
    )
    assert result["prediction"] == 1
    assert result["label"] == "flagged"


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.49, 0),
        (0.50, 1),
        (0.90, 1),
    ],
)
def test_predict_classifies_probability(
        monkeypatch: pytest.MonkeyPatch,
        probability: float,
        expected: int,
) -> None:
    """测试单条概率按照阈值转换为分类标签."""
    service, inference = create_service(
        monkeypatch,
        prediction=probability,
    )

    result = service.predict({
        "age": 35,
    })

    inference.get_capabilities.assert_called()
    inference.predict.assert_called_once_with({
        "age": 35,
    })
    assert result["prediction"] == expected
    assert result["label"] == expected
    assert result["probability"] == probability
    assert result["threshold"] == 0.5
    assert result["service_type"] == "classification"
    assert result["task_type"] == "classification"
    assert service.runtime_model.access_count == 1


def test_predict_rejects_empty_features(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条分类拒绝空特征."""
    service, _ = create_service(monkeypatch)

    with pytest.raises(
            ValueError,
            match="features 不能为空",
    ):
        service.predict({})


@pytest.mark.parametrize(
    ("batch", "message"),
    [
        (False, "特征类型无效: age 期望 numeric，实际 str"),
        (True, "第 0 条记录的特征类型无效: age 期望 numeric，实际 str"),
    ],
)
def test_predict_rejects_invalid_feature_type(
        monkeypatch: pytest.MonkeyPatch,
        batch: bool,
        message: str,
) -> None:
    """测试单条和批量分类在模型执行前拒绝非法特征类型."""
    service, inference = create_service(
        monkeypatch,
        feature_names=["age"],
        data_types={"age": DataType.NUMERIC},
    )
    features = {"age": "not-a-number"}

    with pytest.raises(TypeError, match=message):
        if batch:
            service.predict_batch([features])
        else:
            service.predict(features)

    inference.predict.assert_not_called()


def test_predict_rejects_batch_result(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条分类拒绝批量概率结果."""
    service, _ = create_service(
        monkeypatch,
        prediction=[0.8],
    )

    with pytest.raises(
            TypeError,
            match="单条分类预测返回了批量结果",
    ):
        service.predict({"age": 35})


def test_predict_batch_returns_classifications(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量分类返回逐条预测结果."""
    service, inference = create_service(
        monkeypatch,
        prediction=[0.2, 0.8],
    )
    features = [
        {"age": 25},
        {"age": 45},
    ]

    result = service.predict_batch(features)

    inference.get_capabilities.assert_called()
    assert result["count"] == 2
    assert result["predictions"] == [
        {
            "prediction": 0,
            "label": 0,
            "probability": 0.2,
            "threshold": 0.5,
        },
        {
            "prediction": 1,
            "label": 1,
            "probability": 0.8,
            "threshold": 0.5,
        },
    ]
    assert service.runtime_model.access_count == 1


def test_predict_batch_returns_empty_result(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试空批次返回空预测列表."""
    service, inference = create_service(monkeypatch)

    result = service.predict_batch([])

    assert result["count"] == 0
    assert result["predictions"] == []
    inference.predict.assert_not_called()
    assert service.runtime_model.access_count == 0


def test_predict_batch_rejects_scalar_result(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量分类拒绝标量概率结果."""
    service, _ = create_service(
        monkeypatch,
        prediction=0.8,
    )

    with pytest.raises(
            TypeError,
            match="批量分类预测未返回列表结果",
    ):
        service.predict_batch([
            {"age": 35},
        ])
