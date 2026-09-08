"""运行时请求结构测试

验证运行控制和预测请求的字段约束。

核心功能：
  - test_control_request_rejects_operator:
    验证控制请求不接受客户端操作人
  - test_predict_request_rejects_internal_model_id:
    验证公开预测请求不再接受内部模型 ID
"""


import pytest
from pydantic import ValidationError

from datamind.runtime.server.schemas import (
    ControlRequest,
    PredictRequest,
)


def test_control_request_rejects_operator() -> None:
    """测试控制请求不接受客户端操作人"""
    with pytest.raises(
            ValidationError,
            match="operator",
    ):
        ControlRequest.model_validate({
            "deployment_id": "dep_test",
            "operator": "spoofed-user",
        })


def test_predict_request_rejects_internal_model_id() -> None:
    """测试公开预测请求不再接受内部模型 ID"""
    with pytest.raises(ValidationError):
        PredictRequest.model_validate({
            "model_id": "mdl_test",
            "features": {"age": 35},
        })
