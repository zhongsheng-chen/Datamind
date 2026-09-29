"""配置包公共导出测试.

验证配置包公开 API 的完整性和可访问性。

核心功能：
  - test_config_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.config as config


EXPECTED_EXPORTS = {
    "Settings",
    "get_audit_config",
    "get_auth_config",
    "get_classification_config",
    "get_console_config",
    "get_database_config",
    "get_initialization_config",
    "get_logging_config",
    "get_runtime_config",
    "get_scoring_config",
    "get_service_config",
    "get_settings",
    "get_storage_config",
    "get_task_queue_config",
    "get_task_worker_config",
}


def test_config_exports_expected_public_api() -> None:
    """测试配置包公开完整且准确的 API."""
    assert set(config.__all__) == EXPECTED_EXPORTS
    assert len(config.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问."""
    for name in config.__all__:
        assert hasattr(config, name), name
