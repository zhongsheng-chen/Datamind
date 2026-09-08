"""运行时模型服务异常

定义运行时模型服务对外接口使用的异常类型。

核心功能：
  - ServiceDeploymentNotFoundError:
      服务部署不存在
  - ServiceEnvironmentMismatchError:
      部署环境与当前服务环境不一致
  - ServiceAuthenticationError:
      请求身份认证失败
  - ServiceAuthorizationError:
      请求权限不足
  - ServiceAuthenticationUnavailableError:
      认证服务不可用

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


class ServiceAuthenticationError(
    BentoMLException
):
    """请求身份认证失败"""

    error_code = HTTPStatus.UNAUTHORIZED


class ServiceAuthorizationError(
    BentoMLException
):
    """请求权限不足"""

    error_code = HTTPStatus.FORBIDDEN


class ServiceAuthenticationUnavailableError(
    BentoMLException
):
    """认证服务不可用"""

    error_code = HTTPStatus.SERVICE_UNAVAILABLE
