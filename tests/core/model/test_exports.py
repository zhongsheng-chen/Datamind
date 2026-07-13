# tests/core/model/test_exports.py

"""模型包公共导出测试

验证模型包公开 API 的完整性和可访问性。

核心功能：
  - test_model_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.core.model as model


EXPECTED_EXPORTS = {
    "BaseModelAdapter",
    "ModelAdapterFactory",
    "SklearnAdapter",
    "XGBoostAdapter",
    "LightGBMAdapter",
    "CatBoostAdapter",
}


def test_model_exports_expected_public_api() -> None:
    """测试模型包公开完整且准确的 API"""
    assert set(model.__all__) == EXPECTED_EXPORTS
    assert len(model.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in model.__all__:
        assert hasattr(model, name), name
