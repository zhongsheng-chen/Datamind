# datamind/core/scoring/__init__.py

"""评分卡模块

提供完整的评分卡模型能力，包括：
  - 模型适配器：统一不同框架的模型接口
  - 能力定义：模型能力声明和检查
  - 特征转换：WOE 转换和分箱管理
  - 分数计算：概率到信用分数的转换
  - 预测引擎：统一的预测和评分入口
  - 特征解释：特征贡献分析和重要性

模块组成：
  - adapters: 模型适配器（sklearn、xgboost、lightgbm、catboost、torch、tensorflow、onnx）
  - capability: 模型能力定义和推断
  - binning: 分箱对象定义
  - transform: WOE 特征转换器
  - score: 分数计算器
  - predictor: 预测器
  - engine: 评分引擎
  - explain: 特征解释器
"""

from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.predictor import Predictor
from datamind.core.scoring.explain import Explainer
from datamind.core.scoring.score import (
    Score,
    to_score,
    to_score_batch,
    from_logit,
    from_logit_batch,
    to_probability,
    to_probability_batch
)
from datamind.core.scoring.transform import WOETransformer, MissingStrategy
from datamind.core.scoring.binning import Bin

from datamind.core.scoring.capability import (
    ScorecardCapability,
    infer_capabilities,
    has_capability,
    has_all_capabilities,
    has_any_capability,
    combine_capabilities,
    get_capability_weight,
    get_capability_weight_sum,
    validate_required_capabilities,
    get_capability_list,
    get_capability_descriptions,
)

from datamind.core.scoring.adapters import (
    BaseModelAdapter,
    get_adapter,
    is_supported,
    get_supported_frameworks,
)

__all__ = [
    'ScoringEngine',
    'Predictor',
    'Explainer',
    'Score',
    'to_score',
    'to_score_batch',
    'from_logit',
    'from_logit_batch',
    'to_probability',
    'to_probability_batch',
    'WOETransformer',
    'MissingStrategy',
    'Bin',
    'ScorecardCapability',
    'infer_capabilities',
    'has_capability',
    'has_all_capabilities',
    'has_any_capability',
    'combine_capabilities',
    'get_capability_weight',
    'get_capability_weight_sum',
    'validate_required_capabilities',
    'get_capability_list',
    'get_capability_descriptions',
    'BaseModelAdapter',
    'get_adapter',
    'is_supported',
    'get_supported_frameworks',
]