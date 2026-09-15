"""推理响应构造测试

验证公开字段筛选、响应结构和原始数据保留行为。
"""

import json
from typing import Any

import pytest

from datamind.runtime.responses import build_prediction_response


def test_build_prediction_response_selects_public_fields() -> None:
    """测试公开响应只包含业务结果与当前请求 ID，内部结果保持完整"""
    prediction = {
        "score": 120,
        "probability": 0.2,
        "decision": "reject",
        "threshold": 600,
        "score_intercept": 0,
        "features": {
            "model_id": {"points": 120, "value": "input", "woe": 0.1, "bin": "input"},
        },
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "deployment_id": "dep_test",
        "framework": "sklearn",
        "service_type": "scoring",
        "task_type": "scoring",
        "decision_id": "dcs_test",
        "route": {"routing_id": "rtn_test", "experiment_id": "exp_test"},
        "environment": "testing",
        "worker_id": "worker_test",
        "request_id": "not_the_current_request",
        "internal_extension": {"debug": True},
    }
    original = json.dumps(prediction)

    response = build_prediction_response(prediction, request_id="req_test")

    assert list(response) == [
        "success", "task_type", "score", "probability", "decision", "threshold",
        "score_intercept", "features", "request_id",
    ]
    assert response["success"] is True
    assert response["request_id"] == "req_test"
    assert response["task_type"] == "scoring"
    for key in ("score", "probability", "decision", "threshold", "score_intercept", "features"):
        assert response[key] == prediction[key]
    assert response["features"] is prediction["features"]
    assert json.dumps(prediction) == original


@pytest.mark.parametrize(("prediction", "expected"), [
    (
        {
            "task_type": "classification",
            "prediction": 0,
            "label": "benign",
            "probability": 0.2,
            "threshold": 0.5,
            "model_id": "mdl",
        },
        {
            "success": True,
            "task_type": "classification",
            "probability": 0.2,
            "prediction": 0,
            "label": "benign",
            "threshold": 0.5,
            "request_id": "req",
        },
    ),
    (
        {"success": False, "error": "failed", "error_type": "ValueError", "worker_id": "worker"},
        {"success": False, "error": "failed", "error_type": "ValueError", "request_id": "req"},
    ),
])
def test_build_prediction_response_handles_classification_and_errors(
        prediction: dict[str, Any],
        expected: dict[str, Any],
) -> None:
    """测试分类响应和错误响应均不返回内部标识"""
    response = build_prediction_response(prediction, request_id="req")

    assert response == expected
    assert list(response) == list(expected)


@pytest.mark.parametrize("prediction", [
    {},
    {"score": 0, "probability": 0, "score_intercept": 0, "features": {}},
    {"score": None, "features": None},
])
def test_build_prediction_response_preserves_present_values(
        prediction: dict[str, Any],
) -> None:
    """测试保留零值和空值，不补充未提供的业务字段"""
    response = build_prediction_response(prediction, request_id="req")

    assert response == {"success": True, **prediction, "request_id": "req"}
