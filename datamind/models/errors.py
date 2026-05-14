# datamind/models/errors.py

"""模型错误定义

统一定义模型注册、部署、加载过程中的业务异常类型。

核心功能：
  - ModelError: 模型基础异常
  - ModelNotFoundError: 模型不存在
  - ModelAlreadyExistsError: 模型已存在
  - InvalidModelStateError: 非法模型状态
  - InvalidExperimentStateError: 非法实验状态
  - DeploymentError: 模型部署异常
  - InvalidDeploymentStateError: 非法部署状态
  - BackendError: 模型后端错误
  - ArtifactError: 模型产物处理错误

使用示例：
  from datamind.models.errors import ModelNotFoundError

  raise ModelNotFoundError("模型不存在")
"""


class ModelError(Exception):
    """模型基础异常"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ModelNotFoundError(ModelError):
    """模型不存在"""
    pass


class ModelAlreadyExistsError(ModelError):
    """模型已存在"""
    pass


class InvalidModelStateError(ModelError):
    """非法模型状态"""
    pass


class InvalidExperimentStateError(ModelError):
    """非法实验状态"""
    pass


class DeploymentError(ModelError):
    """模型部署异常"""
    pass


class InvalidDeploymentStateError(ModelError):
    """非法部署状态"""
    pass


class BackendError(ModelError):
    """模型后端错误"""
    pass


class ArtifactError(ModelError):
    """模型产物处理错误"""
    pass