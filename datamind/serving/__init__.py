# datamind/serving/__init__.py
"""
模型服务模块

基于BentoML的模型服务部署
支持评分卡和反欺诈模型的独立部署
"""

from datamind.serving.scoring_service import ScoringService
from datamind.serving.fraud_service import FraudService
from datamind.serving.base import BaseModelService

__all__ = [
    'ScoringService',
    'FraudService',
    'BaseModelService',
]