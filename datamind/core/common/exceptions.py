# datamind/core/common/errors.py

"""通用异常定义

提供系统通用的异常类。

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
  - StorageException: 存储基础异常
    - StorageNotFoundException: 文件不存在
    - StoragePermissionException: 权限错误
    - StorageQuotaException: 配额超限
    - StorageValidationException: 参数验证错误
  - ValidationException: 请求验证失败
  - UnauthorizedException: 未授权
  - ForbiddenException: 禁止访问
  - ABTestException: A/B测试异常

使用示例：
    raise ModelNotFoundException(model_id="MDL_001")
    raise StorageNotFoundException(path="/data/file.txt")
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
        """转换为字典格式，用于 API 响应"""
        return {
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details
            }
        }


# ============== 模型异常 ==============

class ModelException(DatamindError):
    """模型基础异常"""
    def __init__(self, message: str, code: str = "MODEL_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)


class ModelNotFoundException(ModelException):
    """模型未找到异常"""
    def __init__(self, model_id: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_id is not None:
            msg = f"模型未找到: {model_id}"
        else:
            msg = "模型未找到"
        super().__init__(msg, code="MODEL_NOT_FOUND", status_code=404)


class ModelAlreadyExistsException(ModelException):
    """模型已存在异常"""
    def __init__(self, model_name: str = None, version: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_name and version:
            msg = f"模型 {model_name} 版本 {version} 已存在"
        elif model_name:
            msg = f"模型 {model_name} 已存在"
        else:
            msg = "模型已存在"
        super().__init__(msg, code="MODEL_ALREADY_EXISTS", status_code=409)


class ModelValidationException(ModelException):
    """模型验证失败异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_VALIDATION_ERROR", status_code=400, **kwargs)


class ModelFileException(ModelException):
    """模型文件异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_FILE_ERROR", status_code=400, **kwargs)


class ModelLoadException(ModelException):
    """模型加载失败异常"""
    def __init__(self, model_id: str = None, reason: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_id and reason:
            msg = f"模型加载失败: {model_id}，原因: {reason}"
        elif model_id:
            msg = f"模型加载失败: {model_id}"
        elif reason:
            msg = f"模型加载失败: {reason}"
        else:
            msg = "模型加载失败"
        super().__init__(msg, code="MODEL_LOAD_ERROR", status_code=500)


class ModelInferenceException(ModelException):
    """模型推理失败异常"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_INFERENCE_ERROR", status_code=500, **kwargs)


class UnsupportedModelTypeException(ModelException):
    """不支持的模型类型异常"""
    def __init__(self, model_type: str = None, message: str = None):
        if message is not None:
            msg = message
        elif model_type:
            msg = f"不支持的模型类型: {model_type}"
        else:
            msg = "不支持的模型类型"
        super().__init__(msg, code="UNSUPPORTED_MODEL_TYPE", status_code=400)


class UnsupportedFrameworkException(ModelException):
    """不支持的模型框架异常"""
    def __init__(self, framework: str = None, message: str = None):
        if message is not None:
            msg = message
        elif framework:
            msg = f"不支持的模型框架: {framework}"
        else:
            msg = "不支持的模型框架"
        super().__init__(msg, code="UNSUPPORTED_FRAMEWORK", status_code=400)


# ============== 存储异常 ==============

class StorageException(DatamindError):
    """存储基础异常

    所有存储相关异常的基类。
    """
    def __init__(self, message: str, code: str = "STORAGE_ERROR", status_code: int = 500, **kwargs):
        super().__init__(message, code, status_code, **kwargs)


class StorageNotFoundException(StorageException):
    """文件不存在异常"""
    def __init__(self, path: str = None, message: str = None):
        if message is not None:
            msg = message
        elif path:
            msg = f"文件不存在: {path}"
        else:
            msg = "文件不存在"
        super().__init__(msg, code="STORAGE_NOT_FOUND", status_code=404)


class StoragePermissionException(StorageException):
    """权限错误异常"""
    def __init__(self, path: str = None, message: str = None):
        if message is not None:
            msg = message
        elif path:
            msg = f"无权限访问: {path}"
        else:
            msg = "存储权限错误"
        super().__init__(msg, code="STORAGE_PERMISSION_ERROR", status_code=403)


class StorageQuotaException(StorageException):
    """配额超限异常"""
    def __init__(self, current: int = None, limit: int = None, message: str = None):
        if message is not None:
            msg = message
        elif current is not None and limit is not None:
            msg = f"存储配额已满: {current}/{limit} 字节"
        elif current is not None:
            msg = f"存储配额已满: 当前使用 {current} 字节"
        else:
            msg = "存储配额已满"
        super().__init__(msg, code="STORAGE_QUOTA_EXCEEDED", status_code=429)


class StorageValidationException(StorageException):
    """参数验证错误异常"""
    def __init__(self, message: str):
        super().__init__(message, code="STORAGE_VALIDATION_ERROR", status_code=400)


# ============== 数据库异常 ==============

class DatabaseException(DatamindError):
    """数据库基础异常

    所有数据库相关异常的基类。
    """
    def __init__(self, message: str, code: str = "DATABASE_ERROR", **kwargs):
        super().__init__(message, code, status_code=500, **kwargs)


# ============== 通用异常 ==============

class ValidationException(DatamindError):
    """请求验证失败异常"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class UnauthorizedException(DatamindError):
    """未授权异常"""
    def __init__(self, message: str = "未授权访问"):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class ForbiddenException(DatamindError):
    """禁止访问异常"""
    def __init__(self, message: str = "禁止访问"):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ABTestException(DatamindError):
    """A/B测试异常"""
    def __init__(self, message: str, code: str = "ABTEST_ERROR", **kwargs):
        super().__init__(message, code, **kwargs)