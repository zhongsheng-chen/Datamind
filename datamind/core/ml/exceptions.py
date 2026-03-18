# core/ml/exceptions.py

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
        msg = message or f"Model not found: {model_id}" if model_id else "Model not found"
        super().__init__(msg, code="MODEL_NOT_FOUND", status_code=404)


class ModelAlreadyExistsException(ModelException):
    """模型已存在"""
    def __init__(self, model_name: str = None, version: str = None):
        msg = f"Model {model_name} version {version} already exists"
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
    def __init__(self, model_id: str = None, reason: str = None):
        msg = f"Failed to load model {model_id}: {reason}" if model_id else f"Failed to load model: {reason}"
        super().__init__(msg, code="MODEL_LOAD_ERROR", status_code=500)


class ModelInferenceException(ModelException):
    """模型推理失败"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MODEL_INFERENCE_ERROR", status_code=500, **kwargs)


class UnsupportedModelTypeException(ModelException):
    """不支持的模型类型"""
    def __init__(self, model_type: str):
        super().__init__(
            f"Unsupported model type: {model_type}",
            code="UNSUPPORTED_MODEL_TYPE",
            status_code=400
        )


class UnsupportedFrameworkException(ModelException):
    """不支持的模型框架"""
    def __init__(self, framework: str):
        super().__init__(
            f"Unsupported framework: {framework}",
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