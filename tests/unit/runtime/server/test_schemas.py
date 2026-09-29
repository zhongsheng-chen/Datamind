"""运行时请求结构测试.

验证运行控制和预测请求的字段约束。

核心功能：
  - test_control_request_rejects_operator:
    验证控制请求不接受客户端操作人
  - test_predict_request_rejects_internal_model_id:
    验证公开预测请求不再接受内部模型 ID
  - test_batch_predict_request_accepts_instances:
    验证批量预测请求使用实例列表
  - test_batch_predict_request_rejects_legacy_features_list:
    验证批量预测请求拒绝旧版特征列表
"""


import pytest
from pydantic import ValidationError

from datamind.runtime.server.schemas import (
    BatchPredictRequest,
    ControlRequest,
    PredictRequest,
)


def test_control_request_rejects_operator() -> None:
    """测试控制请求不接受客户端操作人."""
    with pytest.raises(
            ValidationError,
            match="operator",
    ):
        ControlRequest.model_validate({
            "deployment_id": "dep_test",
            "operator": "spoofed-user",
        })


def test_predict_request_rejects_internal_model_id() -> None:
    """测试公开预测请求不再接受内部模型 ID."""
    with pytest.raises(ValidationError):
        PredictRequest.model_validate({
            "model_id": "mdl_test",
            "features": {"age": 35},
        })


def test_batch_predict_request_accepts_instances() -> None:
    """测试批量预测请求使用实例列表."""
    request = BatchPredictRequest.model_validate({
        "model_name": "scorecard",
        "instances": [{
            "subject_key": "customer_1",
            "subject_type": "customer",
            "features": {"age": 35},
        }],
    })

    assert request.model_name == "scorecard"
    assert request.instances[0].subject_key == "customer_1"
    assert request.instances[0].features == {"age": 35}


def test_batch_predict_request_rejects_legacy_features_list() -> None:
    """测试批量预测请求拒绝旧版特征列表."""
    with pytest.raises(ValidationError):
        BatchPredictRequest.model_validate({
            "deployment_id": "dep_test",
            "features_list": [{"age": 35}],
        })
