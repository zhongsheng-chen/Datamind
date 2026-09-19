"""模型错误定义

统一定义模型注册、部署、加载、运行和实验过程中的异常类型。

核心功能：
  - ModelError: 模型基础异常
  - ModelNotFoundError: 模型不存在
  - ModelAlreadyExistsError: 模型已存在
  - VersionNotFoundError: 版本不存在
  - InvalidModelStateError: 非法模型状态
  - ExperimentError: 实验基础异常
  - InvalidExperimentStateError: 非法实验状态
  - InvalidExperimentConfigError: 非法实验配置
  - DeploymentError: 模型部署异常
  - DeploymentNotFoundError: 部署不存在
  - InvalidDeploymentStateError: 非法部署状态
  - RuntimeRouteError: 运行时路由异常
  - BackendError: 模型后端错误
  - ArtifactError: 模型产物处理错误

使用示例：
  from datamind.models.errors import (
      ModelNotFoundError,
      VersionNotFoundError,
      RuntimeRouteError,
      InvalidExperimentConfigError,
  )

  raise ModelNotFoundError("模型不存在")
  raise VersionNotFoundError("版本不存在")
  raise RuntimeRouteError("没有可用部署")
  raise InvalidExperimentConfigError("实验配置不合法")
"""


class ModelError(Exception):
    """模型基础异常"""

    def __init__(self, message: str):
        """初始化模型异常

        参数：
            message: 异常消息
        """
        super().__init__(message)
        self.message = message


class ModelNotFoundError(ModelError):
    """模型不存在"""
    pass


class ModelAlreadyExistsError(ModelError):
    """模型已存在"""
    pass


class VersionNotFoundError(ModelError):
    """版本不存在"""
    pass


class InvalidModelStateError(ModelError):
    """非法模型状态"""
    pass


class ExperimentError(Exception):
    """实验基础异常"""

    def __init__(self, message: str):
        """初始化实验异常

        参数：
            message: 异常消息
        """
        super().__init__(message)
        self.message = message


class InvalidExperimentStateError(ExperimentError):
    """非法实验状态"""
    pass


class InvalidExperimentConfigError(ExperimentError):
    """非法实验配置"""
    pass


class DeploymentError(ModelError):
    """模型部署异常"""
    pass


class DeploymentNotFoundError(DeploymentError):
    """部署不存在"""
    pass


class InvalidDeploymentStateError(DeploymentError):
    """非法部署状态"""
    pass


class RuntimeRouteError(ModelError):
    """运行时路由异常"""
    pass


class BackendError(ModelError):
    """模型后端错误"""
    pass


class ArtifactError(ModelError):
    """模型产物处理错误"""
    pass
