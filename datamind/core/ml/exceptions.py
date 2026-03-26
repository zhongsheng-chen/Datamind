# datamind/core/ml/exceptions.py

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

使用示例：
    >>> raise ModelNotFoundException(model_id="MDL_001")
    >>> raise ModelValidationException("特征缺失: age")
    >>> raise UnsupportedFrameworkException(framework="unknown")
"""

from typing import Optional, Dict, Any


class DatamindError(Exception):
    """基础异常类

    所有业务异常的基类，提供统一的错误信息格式。

    属性:
        message: 错误消息
        code: 错误码，用于客户端识别错误类型
        status_code: HTTP 状态码
        details: 错误详情，可包含额外信息
    """

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
        """
        转换为字典格式，用于 API 响应

        返回:
            包含错误信息的字典
        """
        return {
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details
            }
        }


class ModelException(DatamindError):
    """模型基础异常

    所有模型相关异常的基类。
    """
    def __init__(self, message: str, code: str = "MODEL_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)


class ModelNotFoundException(ModelException):
    """模型未找到异常

    当请求的模型 ID 在数据库或缓存中不存在时抛出。
    """
    def __init__(self, model_id: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_id is not None:
            msg = f"Model not found: {model_id}"
        else:
            msg = "Model not found"
        super().__init__(msg, code="MODEL_NOT_FOUND", status_code=404)


class ModelAlreadyExistsException(ModelException):
    """模型已存在异常

    当注册的模型名称和版本已存在时抛出。
    """
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
    """模型验证失败异常

    当模型元数据验证失败时抛出，如特征缺失、格式错误等。
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_VALIDATION_ERROR", status_code=400, **kwargs)


class ModelFileException(ModelException):
    """模型文件异常

    当模型文件读取、解析或保存失败时抛出。
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_FILE_ERROR", status_code=400, **kwargs)


class ModelLoadException(ModelException):
    """模型加载失败异常

    当从 BentoML 加载模型失败时抛出。
    """
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
    """模型推理失败异常

    当模型预测过程中发生错误时抛出，如特征类型不匹配、数组维度错误等。
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_INFERENCE_ERROR", status_code=500, **kwargs)


class UnsupportedModelTypeException(ModelException):
    """不支持的模型类型异常

    当模型类型不在支持列表中时抛出。
    """
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
    """不支持的模型框架异常

    当模型框架不在支持列表中时抛出。
    """
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
    """数据库基础异常

    所有数据库相关异常的基类。
    """
    def __init__(self, message: str, code: str = "DATABASE_ERROR", **kwargs):
        super().__init__(message, code, status_code=500, **kwargs)


class ValidationException(DatamindError):
    """请求验证失败异常

    当 API 请求参数验证失败时抛出。
    """
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class UnauthorizedException(DatamindError):
    """未授权异常

    当请求缺少有效认证信息时抛出。
    """
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class ForbiddenException(DatamindError):
    """禁止访问异常

    当认证用户没有权限访问资源时抛出。
    """
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ABTestException(DatamindError):
    """A/B测试异常

    当 A/B 测试相关操作失败时抛出。
    """
    def __init__(self, message: str, code: str = "ABTEST_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)