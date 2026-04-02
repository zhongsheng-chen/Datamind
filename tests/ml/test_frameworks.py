# tests/ml/test_frameworks.py

"""测试框架配置模块"""

import pytest
import warnings
from datamind.core.common.frameworks import (
    get_bentoml_backend,
    get_framework_signatures,
    is_framework_supported,
    get_supported_frameworks,
    FRAMEWORK_TO_BENTOML,
    FRAMEWORK_SIGNATURES
)


class TestFrameworkConfig:
    """测试框架配置"""

    def test_get_bentoml_backend_success(self):
        """测试获取 BentoML 后端 - 成功"""
        backend = get_bentoml_backend('sklearn')
        assert backend is not None
        # BentoML 内部模块名称可能不同，只检查是否包含 'sklearn'
        assert 'sklearn' in backend.__name__.lower()

        backend = get_bentoml_backend('xgboost')
        assert backend is not None
        assert 'xgboost' in backend.__name__.lower()

        backend = get_bentoml_backend('lightgbm')
        assert backend is not None
        assert 'lightgbm' in backend.__name__.lower()

        backend = get_bentoml_backend('catboost')
        assert backend is not None
        assert 'catboost' in backend.__name__.lower()

        backend = get_bentoml_backend('torch')
        assert backend is not None
        assert 'torch' in backend.__name__.lower() or 'pytorch' in backend.__name__.lower()

        backend = get_bentoml_backend('tensorflow')
        assert backend is not None
        assert 'tensorflow' in backend.__name__.lower()

        backend = get_bentoml_backend('onnx')
        assert backend is not None
        assert 'onnx' in backend.__name__.lower()

    def test_get_bentoml_backend_case_insensitive(self):
        """测试获取 BentoML 后端 - 大小写不敏感"""
        backend1 = get_bentoml_backend('SKLEARN')
        backend2 = get_bentoml_backend('sklearn')
        assert backend1 is backend2

        backend1 = get_bentoml_backend('XGBoost')
        backend2 = get_bentoml_backend('xgboost')
        assert backend1 is backend2

    def test_get_bentoml_backend_not_supported(self):
        """测试获取 BentoML 后端 - 不支持的框架"""
        with pytest.raises(ValueError) as exc_info:
            get_bentoml_backend('unknown_framework')
        assert "不支持的框架" in str(exc_info.value)

    def test_get_framework_signatures(self):
        """测试获取框架签名配置"""
        signatures = get_framework_signatures('sklearn')
        assert 'predict' in signatures
        assert 'predict_proba' in signatures
        assert signatures['predict']['batchable'] is True

        signatures = get_framework_signatures('xgboost')
        assert 'predict' in signatures
        assert signatures['predict']['batchable'] is True

        # 不支持的框架返回默认签名
        signatures = get_framework_signatures('unknown')
        assert signatures == {"predict": {"batchable": True}}

    def test_is_framework_supported(self):
        """测试检查框架是否支持"""
        assert is_framework_supported('sklearn') is True
        assert is_framework_supported('xgboost') is True
        assert is_framework_supported('lightgbm') is True
        assert is_framework_supported('catboost') is True
        assert is_framework_supported('torch') is True
        assert is_framework_supported('tensorflow') is True
        assert is_framework_supported('onnx') is True
        assert is_framework_supported('unknown') is False
        assert is_framework_supported('') is False

    def test_get_supported_frameworks(self):
        """测试获取支持的框架列表"""
        frameworks = get_supported_frameworks()
        assert isinstance(frameworks, list)
        # 包括 sklearn, xgboost, lightgbm, catboost, torch, pytorch, tensorflow, onnx
        assert len(frameworks) == 8
        assert 'sklearn' in frameworks
        assert 'xgboost' in frameworks
        assert 'lightgbm' in frameworks
        assert 'catboost' in frameworks
        assert 'torch' in frameworks
        assert 'pytorch' in frameworks
        assert 'tensorflow' in frameworks
        assert 'onnx' in frameworks

    def test_framework_mapping_consistency(self):
        """测试框架映射一致性"""
        # FRAMEWORK_TO_BENTOML 包含 pytorch，FRAMEWORK_SIGNATURES 也包含 pytorch
        # 所以两者长度应该相等
        assert len(FRAMEWORK_TO_BENTOML) == len(FRAMEWORK_SIGNATURES)

        # 检查每个框架都有签名配置
        for framework in FRAMEWORK_TO_BENTOML.keys():
            assert framework in FRAMEWORK_SIGNATURES

        # 检查每个签名配置都有对应的框架
        for framework in FRAMEWORK_SIGNATURES.keys():
            assert framework in FRAMEWORK_TO_BENTOML

    def test_bentoml_backend_exists(self):
        """测试 BentoML 后端存在"""
        for framework, backend in FRAMEWORK_TO_BENTOML.items():
            assert backend is not None
            # 检查后端是否有 save_model 方法（这是 BentoML 框架的标准接口）
            # 使用 warnings.catch_warnings 忽略弃用警告
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                assert hasattr(backend, 'save_model')
                assert hasattr(backend, 'load_model')


# 测试 BentoML 后端加载
class TestBentoMLBackendIntegration:
    """测试 BentoML 后端集成"""

    def test_sklearn_backend(self):
        """测试 sklearn 后端"""
        import bentoml.sklearn
        backend = get_bentoml_backend('sklearn')
        assert backend is bentoml.sklearn

    def test_xgboost_backend(self):
        """测试 xgboost 后端"""
        import bentoml.xgboost
        backend = get_bentoml_backend('xgboost')
        assert backend is bentoml.xgboost

    def test_lightgbm_backend(self):
        """测试 lightgbm 后端"""
        import bentoml.lightgbm
        backend = get_bentoml_backend('lightgbm')
        assert backend is bentoml.lightgbm

    def test_catboost_backend(self):
        """测试 catboost 后端"""
        import bentoml.catboost
        backend = get_bentoml_backend('catboost')
        assert backend is bentoml.catboost

    def test_torch_backend(self):
        """测试 torch 后端"""
        import bentoml.pytorch
        backend = get_bentoml_backend('torch')
        assert backend is bentoml.pytorch