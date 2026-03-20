# Datamind/datamind/core/ml/exceptions.py

"""机器学习异常定义

提供机器学习模块专用的异常类，继承自 DatamindError。

异常层次结构：
- DatamindError: 基础异常类
  - ModelException: 模型基础异常
    - ModelNotFoundException: 模型未找到
    - ModelAlreadyExistsException: 模型已存在
    - ModelValidationException: 模型验证失败
    - ModelFileException: 模型文件异常
    - ModelLoadException: 模型加载失败
    - ModelInferenceException: 模型推理失败
    - UnsupportedModelTypeException: 不支持的模型类型
    - UnsupportedFrameworkException: 不支持的模型框架
  - DatabaseException: 数据库异常
  - ValidationException: 请求验证失败
  - UnauthorizedException: 未授权
  - ForbiddenException: 禁止访问
  - ABTestException: A/B测试异常

所有异常都支持：
 - 自定义错误消息
 - 错误码（code）
 - HTTP状态码（status_code）
 - 详细信息（details）
 - 转换为字典格式（to_dict）
"""

from typing import Optional, Dict, Any


class DatamindError(Exception):
    """基础异常类"""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details
            }
        }


class ModelException(DatamindError):
    """模型基础异常"""
    def __init__(self, message: str, code: str = "MODEL_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)


class ModelNotFoundException(ModelException):
    """模型未找到"""
    def __init__(self, model_id: str = None, message: str = None):
        if message is not None:
            # 如果提供了自定义消息，直接使用
            msg = message
        elif model_id is not None:
            msg = f"Model not found: {model_id}"
        else:
            msg = "Model not found"
        super().__init__(msg, code="MODEL_NOT_FOUND", status_code=404)


class ModelAlreadyExistsException(ModelException):
    """模型已存在"""
    def __init__(self, model_name: str = None, version: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_name and version:
            msg = f"Model {model_name} version {version} already exists"
        elif model_name:
            msg = f"Model {model_name} already exists"
        else:
            msg = "Model already exists"
        super().__init__(msg, code="MODEL_ALREADY_EXISTS", status_code=409)


class ModelValidationException(ModelException):
    """模型验证失败"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_VALIDATION_ERROR", status_code=400, **kwargs)


class ModelFileException(ModelException):
    """模型文件异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_FILE_ERROR", status_code=400, **kwargs)


class ModelLoadException(ModelException):
    """模型加载失败"""
    def __init__(self, model_id: str = None, reason: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_id and reason:
            msg = f"Failed to load model {model_id}: {reason}"
        elif model_id:
            msg = f"Failed to load model {model_id}"
        elif reason:
            msg = f"Failed to load model: {reason}"
        else:
            msg = "Failed to load model"
        super().__init__(msg, code="MODEL_LOAD_ERROR", status_code=500)


class ModelInferenceException(ModelException):
    """模型推理失败"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_INFERENCE_ERROR", status_code=500, **kwargs)


class UnsupportedModelTypeException(ModelException):
    """不支持的模型类型"""
    def __init__(self, model_type: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_type:
            msg = f"Unsupported model type: {model_type}"
        else:
            msg = "Unsupported model type"
        super().__init__(
            msg,
            code="UNSUPPORTED_MODEL_TYPE",
            status_code=400
        )


class UnsupportedFrameworkException(ModelException):
    """不支持的模型框架"""
    def __init__(self, framework: str = None, message: str = None):
        if message is not None:
            msg = message
        elif framework:
            msg = f"Unsupported framework: {framework}"
        else:
            msg = "Unsupported framework"
        super().__init__(
            msg,
            code="UNSUPPORTED_FRAMEWORK",
            status_code=400
        )


class DatabaseException(DatamindError):
    """数据库基础异常"""
    def __init__(self, message: str, code: str = "DATABASE_ERROR", **kwargs):
        super().__init__(message, code, status_code=500, **kwargs)


class ValidationException(DatamindError):
    """请求验证失败"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class UnauthorizedException(DatamindError):
    """未授权"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class ForbiddenException(DatamindError):
    """禁止访问"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ABTestException(DatamindError):
    """A/B测试异常"""
    def __init__(self, message: str, code: str = "ABTEST_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)