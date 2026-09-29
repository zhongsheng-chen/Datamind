"""运行时服务请求结构.

定义运行控制、模型预测和业务结果回流接口的输入结构。

核心功能：
  - ControlRequest: 运行控制请求
  - DeploymentRequest: 部署查询请求
  - PredictRequest: 单条预测请求
  - PredictionInstance: 批量预测中的单条预测实例
  - BatchPredictRequest: 批量预测请求
  - BatchReferenceRequest: 批次引用请求
  - OutcomeFeedbackRequest: 业务结果回流请求

使用示例：
  from datamind.runtime.server.schemas import PredictRequest

  request = PredictRequest(
      model_name="scorecard",
      features={"age": 35},
      subject_key="customer_10001",
      subject_type="customer",
  )
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeRequest(BaseModel):
    """运行时接口请求基类."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ControlRequest(RuntimeRequest):
    """运行控制请求."""

    deployment_id: str = Field(
        min_length=1,
    )


class DeploymentRequest(RuntimeRequest):
    """部署查询请求."""

    deployment_id: str = Field(
        min_length=1,
    )


class PredictRequest(RuntimeRequest):
    """单条预测请求."""

    model_name: str = Field(
        min_length=1,
        max_length=100,
    )
    features: dict[str, Any] = Field(
        min_length=1,
    )
    deployment_id: str | None = None
    subject_key: str | None = None
    subject_type: str | None = None


class PredictionInstance(RuntimeRequest):
    """批量预测中的单条预测实例."""

    features: dict[str, Any] = Field(
        min_length=1,
    )
    subject_key: str | None = None
    subject_type: str | None = None


class BatchPredictRequest(RuntimeRequest):
    """批量预测请求."""

    model_name: str = Field(
        min_length=1,
        max_length=100,
    )
    instances: list[PredictionInstance] = Field(
        min_length=1,
    )
    deployment_id: str | None = None


class BatchReferenceRequest(RuntimeRequest):
    """批次引用请求."""

    batch_id: str = Field(
        min_length=1,
        max_length=64,
    )


class OutcomeFeedbackRequest(RuntimeRequest):
    """业务结果回流请求."""

    outcome_id: str = Field(
        min_length=1,
        max_length=64,
    )
    subject_key: str = Field(
        min_length=1,
        max_length=128,
    )
    decision_id: str | None = None
    request_id: str | None = None
    subject_type: str | None = None
    approved: bool | None = None
    converted: bool | None = None
    defaulted: bool | None = None
    overdue_days: int | None = Field(
        default=None,
        ge=0,
    )
    amount: float | None = Field(
        default=None,
        ge=0,
    )
    label: str | None = None
    context: dict[str, Any] | None = None
    outcome_time: datetime | None = None
