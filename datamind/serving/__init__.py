# datamind/serving/__init__.py

"""BentoML Serving 模块

提供基于 BentoML 的模型服务，支持：
  - 评分卡模型服务
  - 反欺诈模型服务
  - 模型热加载
  - 模型注册/注销
  - A/B测试支持
"""

from datamind.serving.scoring_service import ScoringService
from datamind.serving.fraud_service import FraudService
from datamind.serving.base import BaseBentoService

__all__ = [
    'ScoringService',
    'FraudService',
    'BaseBentoService',
]