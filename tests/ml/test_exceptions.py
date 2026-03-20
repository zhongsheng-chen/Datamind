# tests/ml/test_exceptions.py
"""测试机器学习异常类"""

import pytest
from datamind.core.ml.exceptions import (
    DatamindError,
    ModelException,
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException,
    ModelLoadException,
    ModelInferenceException,
    UnsupportedModelTypeException,
    UnsupportedFrameworkException,
    DatabaseException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    ABTestException
)


class TestExceptions:
    """测试异常类"""

    def test_datamind_error(self):
        """测试基础异常类"""
        error = DatamindError("测试错误", code="TEST_ERROR", status_code=400, details={"key": "value"})
        assert error.message == "测试错误"
        assert error.code == "TEST_ERROR"
        assert error.status_code == 400
        assert error.details == {"key": "value"}

        error_dict = error.to_dict()
        assert error_dict == {
            'error': {
                'code': 'TEST_ERROR',
                'message': '测试错误',
                'details': {'key': 'value'}
            }
        }

    def test_model_not_found_exception(self):
        """测试模型未找到异常"""
        # 带模型ID
        error = ModelNotFoundException(model_id="MDL_123")
        assert str(error) == "Model not found: MDL_123"
        assert error.code == "MODEL_NOT_FOUND"
        assert error.status_code == 404

        # 不带模型ID
        error = ModelNotFoundException()
        assert str(error) == "Model not found"

        # 自定义消息
        error = ModelNotFoundException(message="自定义错误消息")
        assert str(error) == "自定义错误消息"

    def test_model_already_exists_exception(self):
        """测试模型已存在异常"""
        error = ModelAlreadyExistsException(model_name="test_model", version="1.0.0")
        assert str(error) == "Model test_model version 1.0.0 already exists"
        assert error.code == "MODEL_ALREADY_EXISTS"
        assert error.status_code == 409

    def test_model_validation_exception(self):
        """测试模型验证异常"""
        error = ModelValidationException("验证失败", details={"field": "name"})
        assert str(error) == "验证失败"
        assert error.code == "MODEL_VALIDATION_ERROR"
        assert error.status_code == 400
        assert error.details == {"field": "name"}

    def test_model_file_exception(self):
        """测试模型文件异常"""
        error = ModelFileException("文件损坏")
        assert str(error) == "文件损坏"
        assert error.code == "MODEL_FILE_ERROR"
        assert error.status_code == 400

    def test_model_load_exception(self):
        """测试模型加载异常"""
        # 带模型ID和原因
        error = ModelLoadException(model_id="MDL_123", reason="文件不存在")
        assert str(error) == "Failed to load model MDL_123: 文件不存在"
        assert error.code == "MODEL_LOAD_ERROR"
        assert error.status_code == 500

        # 只带原因
        error = ModelLoadException(reason="内存不足")
        assert str(error) == "Failed to load model: 内存不足"

    def test_model_inference_exception(self):
        """测试模型推理异常"""
        error = ModelInferenceException("推理失败")
        assert str(error) == "推理失败"
        assert error.code == "MODEL_INFERENCE_ERROR"
        assert error.status_code == 500

    def test_unsupported_model_type_exception(self):
        """测试不支持的模型类型异常"""
        error = UnsupportedModelTypeException("invalid_type")
        assert str(error) == "Unsupported model type: invalid_type"
        assert error.code == "UNSUPPORTED_MODEL_TYPE"
        assert error.status_code == 400

    def test_unsupported_framework_exception(self):
        """测试不支持的框架异常"""
        error = UnsupportedFrameworkException("invalid_framework")
        assert str(error) == "Unsupported framework: invalid_framework"
        assert error.code == "UNSUPPORTED_FRAMEWORK"
        assert error.status_code == 400

    def test_database_exception(self):
        """测试数据库异常"""
        error = DatabaseException("连接失败")
        assert str(error) == "连接失败"
        assert error.code == "DATABASE_ERROR"
        assert error.status_code == 500

    def test_validation_exception(self):
        """测试请求验证异常"""
        error = ValidationException("参数错误", details={"field": "age"})
        assert str(error) == "参数错误"
        assert error.code == "VALIDATION_ERROR"
        assert error.status_code == 400
        assert error.details == {"field": "age"}

    def test_unauthorized_exception(self):
        """测试未授权异常"""
        error = UnauthorizedException()
        assert str(error) == "Unauthorized"
        assert error.code == "UNAUTHORIZED"
        assert error.status_code == 401

    def test_forbidden_exception(self):
        """测试禁止访问异常"""
        error = ForbiddenException("无权访问")
        assert str(error) == "无权访问"
        assert error.code == "FORBIDDEN"
        assert error.status_code == 403

    def test_abtest_exception(self):
        """测试 A/B 测试异常"""
        error = ABTestException("测试不存在")
        assert str(error) == "测试不存在"
        assert error.code == "ABTEST_ERROR"
        assert error.status_code == 500

    def test_exception_inheritance(self):
        """测试异常继承关系"""
        assert issubclass(ModelNotFoundException, ModelException)
        assert issubclass(ModelException, DatamindError)
        assert issubclass(DatabaseException, DatamindError)
        assert issubclass(ValidationException, DatamindError)