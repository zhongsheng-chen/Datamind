# Datamind/datamind/api/__init__.py

"""API模块

提供 Datamind 系统的 RESTful API 接口，对外暴露模型管理、评分预测、反欺诈检测等功能。

模块组成：
  - routes: 路由模块，包含各业务领域的 API 端点
    - model_api: 模型管理 API（注册、激活、停用、查询）
    - scoring_api: 评分卡 API（评分预测）
    - fraud_api: 反欺诈 API（欺诈检测）
    - management_api: 管理 API（系统配置、监控、审计）
  - dependencies: 依赖项模块（认证、授权、请求上下文）
  - middlewares: 中间件模块（日志、CORS、限流、安全）

API 路由前缀：
  - /api/v1/models - 模型管理
  - /api/v1/scoring - 评分卡服务
  - /api/v1/fraud - 反欺诈服务
  - /api/v1/management - 系统管理

安全特性：
  - API 密钥认证（X-API-Key）
  - JWT 令牌认证（可选）
  - 速率限制（防滥用）
  - 请求日志（审计追踪）

示例请求：
  # 注册模型
  POST /api/v1/models/register
  {
    "model_name": "credit_score_model",
    "model_version": "1.0.0",
    ...
  }

  # 评分预测
  POST /api/v1/scoring/predict
  {
    "model_id": "MDL_xxx",
    "features": {...}
  }
"""

from fastapi import APIRouter

from datamind.api.routes import model_api, scoring_api
from datamind.api.routes import management_api, fraud_api

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