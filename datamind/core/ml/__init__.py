# datamind/core/ml/__init__.py
"""机器学习模块

提供模型注册、加载、推理、评分卡管理等核心功能。

模块组成：
  - common: 通用基础（异常、框架、缓存、适配器）
  - model: 模型管理（加载、注册、推理）
  - scorecard: 评分卡业务（配置、WOE、特征分）
  - companion: 陪跑业务（预测）
  - explain: 模型解释（SHAP）

使用示例：
  >>> from datamind.core.ml import get_inference_engine
  >>>
  >>> engine = get_inference_engine()
  >>> result = engine.predict("MDL_001", {"age": 35, "income": 50000})
"""

from datamind.core.ml.model.inference import InferenceEngine, get_inference_engine
from .model.loader import ModelLoader, get_model_loader
from .model.registry import ModelRegistry, get_model_registry
from .scorecard.manager import get_scorecard_manager
from .scorecard.transformer import WOETransformer
from .scorecard.scorer import ScorecardScorer
from .scorecard.predictor import ScorecardPredictor
from .companion.predictor import CompanionPredictor

__all__ = [
    # 推理
    'InferenceEngine',
    'get_inference_engine',
    # 模型管理
    'ModelLoader',
    'get_model_loader',
    'ModelRegistry',
    'get_model_registry',
    # 评分卡
    'get_scorecard_manager',
    'WOETransformer',
    'ScorecardScorer',
    'ScorecardPredictor',
    # 陪跑
    'CompanionPredictor',
]