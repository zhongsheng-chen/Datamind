# datamind/api/__init__.py
"""
API模块

提供RESTful API接口，包括：
- 模型管理API
- 评分卡API
- 反欺诈API
- 管理API
"""

from fastapi import APIRouter

from api.routes import model_api, scoring_api, fraud_api, management_api

# 创建主路由
api_router = APIRouter()

# 注册所有路由
api_router.include_router(model_api.router, prefix="/models", tags=["models"])
api_router.include_router(scoring_api.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(fraud_api.router, prefix="/fraud", tags=["fraud"])
api_router.include_router(management_api.router, prefix="/management", tags=["management"])

__all__ = [
    'api_router',
    'model_api',
    'scoring_api',
    'fraud_api',
    'management_api',
]