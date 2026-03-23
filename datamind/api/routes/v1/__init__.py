# datamind/api/routes/v1/__init__.py

"""API v1 版本路由

版本特性：
  - 评分卡预测返回 total_score + feature_scores
  - 反欺诈预测返回 fraud_probability + risk_score
  - 模型管理 API
  - A/B 测试支持
"""

from fastapi import APIRouter
from datamind.api.routes.v1 import scoring_api
from datamind.api.routes.v1 import fraud_api
from datamind.api.routes.v1 import model_api
from datamind.api.routes.v1 import management_api

router = APIRouter(prefix="/v1")

router.include_router(scoring_api.router, prefix="/scoring", tags=["scoring"])
router.include_router(fraud_api.router, prefix="/fraud", tags=["fraud"])
router.include_router(model_api.router, prefix="/models", tags=["models"])
router.include_router(management_api.router, prefix="/management", tags=["management"])