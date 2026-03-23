# datamind/api/routes/v2/__init__.py

"""API v2 版本路由

v2 版本改进：
  - 响应结构更加扁平化
  - 新增元数据字段
  - 更好的错误信息
  - 性能优化
"""

from fastapi import APIRouter
from datamind.api.routes.v2 import scoring_api
from datamind.api.routes.v2 import fraud_api

router = APIRouter(prefix="/v2")

router.include_router(scoring_api.router, prefix="/scoring", tags=["scoring"])
router.include_router(fraud_api.router, prefix="/fraud", tags=["fraud"])