"""运行时服务请求结构.

定义运行控制、模型预测接口的输入结构。

核心功能：
  - ControlRequest: 运行控制请求
  - DeploymentRequest: 部署查询请求
  - PredictRequest: 单条预测请求
  - PredictionInstance: 批量预测中的单条预测实例
  - BatchPredictRequest: 批量预测请求
  - BatchReferenceRequest: 批次引用请求

使用示例：
  from datamind.runtime.server.schemas import PredictRequest

  request = PredictRequest(
      model_name="scorecard",
      features={"age": 35},
      subject_key="customer_10001",
      subject_type="customer",
  )
"""

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
        description="要重新加载的部署 ID",
    )


class DeploymentRequest(RuntimeRequest):
    """部署查询请求."""

    deployment_id: str = Field(
        min_length=1,
        description="要查询运行状态的部署 ID",
    )


class PredictRequest(RuntimeRequest):
    """单条预测请求."""

    model_name: str = Field(
        min_length=1,
        max_length=100,
        description="已注册的模型名称",
    )
    features: dict[str, Any] = Field(
        min_length=1,
        description="本次预测的输入特征",
    )
    deployment_id: str | None = Field(
        default=None,
        description="显式指定的部署 ID；省略时由路由选择部署",
    )
    subject_key: str | None = Field(
        default=None,
        description="用于实验分组和路由匹配的稳定业务主体标识",
    )
    subject_type: str | None = Field(
        default=None,
        description="用于路由条件匹配的业务主体类型，例如 customer",
    )


class PredictionInstance(RuntimeRequest):
    """批量预测中的单条预测实例."""

    features: dict[str, Any] = Field(
        min_length=1,
        description="该实例的输入特征",
    )
    subject_key: str | None = Field(
        default=None,
        description="该实例用于实验分组和路由匹配的稳定业务主体标识",
    )
    subject_type: str | None = Field(
        default=None,
        description="该实例用于路由条件匹配的业务主体类型，例如 customer",
    )


class BatchPredictRequest(RuntimeRequest):
    """批量预测请求."""

    model_name: str = Field(
        min_length=1,
        max_length=100,
        description="已注册的模型名称",
    )
    instances: list[PredictionInstance] = Field(
        min_length=1,
        description="需要预测的实例列表",
    )
    deployment_id: str | None = Field(
        default=None,
        description="批次内所有实例共用的部署 ID；省略时逐条路由",
    )


class BatchReferenceRequest(RuntimeRequest):
    """批次引用请求."""

    batch_id: str = Field(
        min_length=1,
        max_length=64,
        description="批量预测提交返回的批次 ID",
    )
