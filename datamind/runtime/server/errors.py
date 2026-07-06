# datamind/runtime/server/errors.py

"""Datamind 运行时模型服务异常

定义运行时模型服务对外接口使用的异常类型。

核心功能：
  - ServiceDeploymentNotFoundError:
      服务部署不存在
  - ServiceEnvironmentMismatchError:
      部署环境与当前服务环境不一致

说明：
  本模块中的异常用于运行时模型服务接口层，
  负责将服务请求错误映射为明确的 HTTP 响应状态。

  这些异常仅用于服务接口层，
  不属于 Datamind 核心业务异常。

使用示例：
  from datamind.runtime.server.errors import (
      ServiceDeploymentNotFoundError,
      ServiceEnvironmentMismatchError,
  )

  if deployment is None:
      raise ServiceDeploymentNotFoundError(
          f"部署不存在: {deployment_id}"
      )

  if deployment.environment != service_environment:
      raise ServiceEnvironmentMismatchError(
          "部署环境与当前服务环境不一致: "
          f"deployment_id={deployment_id}, "
          f"deployment_environment={deployment.environment}, "
          f"service_environment={service_environment}"
      )
"""

from http import HTTPStatus

from bentoml.exceptions import (
    BentoMLException,
    NotFound,
)


class ServiceDeploymentNotFoundError(
    NotFound
):
    """服务部署不存在"""


class ServiceEnvironmentMismatchError(
    BentoMLException
):
    """部署环境与当前服务环境不一致"""

    error_code = HTTPStatus.CONFLICT
