# datamind/api/routes/__init__.py
"""
API路由模块
"""

from datamind.api.routes import model_api, scoring_api
from datamind.api.routes import management_api, fraud_api

__all__ = [
    'model_api',
    'scoring_api',
    'fraud_api',
    'management_api',
]