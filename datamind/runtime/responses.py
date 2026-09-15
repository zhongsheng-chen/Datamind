"""推理响应

统一构造分类、评分及预测失败时的接口响应。

核心功能：
  - build_prediction_response: 构造预测响应

使用示例：
  from datamind.runtime.responses import build_prediction_response

  response = build_prediction_response(
      {"score": 650, "success": True},
      request_id="req_0123456789abcdef",
  )
"""

from typing import Any


_PUBLIC_RESULT_FIELDS = (
    "error",
    "error_type",
    "task_type",
    "score",
    "probability",
    "prediction",
    "label",
    "decision",
    "threshold",
    "score_intercept",
    "features",
)


def build_prediction_response(
        prediction: dict[str, Any],
        *,
        request_id: str,
) -> dict[str, Any]:
    """构造预测响应

    筛选响应字段并附加请求 ID，不修改原始结果。

    参数：
        prediction: 预测结果或错误信息
        request_id: 请求 ID

    返回：
        包含业务结果或错误信息的响应字典
    """
    task_type = prediction.get(
        "task_type",
        prediction.get("service_type"),
    )

    return {
        "success": prediction.get("success", True),
        **(
            {"task_type": task_type}
            if task_type is not None
            else {}
        ),
        **{
            key: prediction[key]
            for key in _PUBLIC_RESULT_FIELDS
            if key != "task_type" and key in prediction
        },
        "request_id": request_id,
    }
