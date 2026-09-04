# tests/constants/test_exports.py

"""常量包公共导出测试

验证常量包公开 API 的完整性和可访问性。

核心功能：
  - test_constants_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.constants as constants


EXPECTED_EXPORTS = {
    "DataType",
    "SUPPORTED_DATA_TYPES",
    "StorageType",
    "SUPPORTED_STORAGE_TYPES",
    "Framework",
    "SUPPORTED_FRAMEWORKS",
    "ModelType",
    "SUPPORTED_MODEL_TYPES",
    "SUPPORTED_MODEL_TYPES_BY_FRAMEWORK",
    "SUPPORTED_MODEL_NAME_PATTERN",
    "TaskType",
    "SUPPORTED_TASK_TYPES",
    "SUPPORTED_MODEL_VERSION_PATTERN",
    "Environment",
    "SUPPORTED_ENVIRONMENTS",
    "ADMINISTRATOR_DISPLAY_NAME",
    "ADMINISTRATOR_ROLE_NAME",
    "ADMINISTRATOR_PERMISSIONS",
    "BUILTIN_ROLE_NAMES",
    "SUPPORTED_PERMISSIONS",
    "LogLevel",
    "SUPPORTED_LOG_LEVELS",
    "LogFormat",
    "SUPPORTED_LOG_FORMATS",
    "RotationType",
    "SUPPORTED_ROTATION_TYPES",
    "RotationWhen",
    "SUPPORTED_ROTATION_WHEN",
    "KB",
    "MB",
    "GB",
}


def test_constants_exports_expected_public_api() -> None:
    """测试常量包公开完整且准确的 API"""
    assert set(constants.__all__) == EXPECTED_EXPORTS
    assert len(constants.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in constants.__all__:
        assert hasattr(constants, name), name
