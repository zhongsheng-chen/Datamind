"""数据库核心包公共导出测试.

验证数据库核心包公开 API 的完整性和可访问性。

核心功能：
  - test_db_core_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.db.core as db_core


EXPECTED_EXPORTS = {
    "Base",
    "IdMixin",
    "TimestampMixin",
    "UnitOfWork",
    "create_engine",
    "get_engine",
    "dispose_engine",
    "get_session_factory",
    "reset_session_factory",
    "get_db_url",
}


def test_db_core_exports_expected_public_api() -> None:
    """测试数据库核心包公开完整且准确的 API."""
    assert set(db_core.__all__) == EXPECTED_EXPORTS
    assert len(db_core.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问."""
    for name in db_core.__all__:
        assert hasattr(db_core, name), name
