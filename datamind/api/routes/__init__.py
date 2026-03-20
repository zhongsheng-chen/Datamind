# Datamind/datamind/api/routes/__init__.py

"""API 路由模块

聚合所有业务领域的 API 路由模块，提供统一的导出入口。

路由模块组成：
  - model_api: 模型管理 API（注册、激活、停用、查询、加载等）
  - scoring_api: 评分卡 API（信用评分预测）
  - fraud_api: 反欺诈 API（欺诈检测预测）
  - management_api: 管理 API（系统配置、监控、审计）
"""

from datamind.api.routes import model_api, scoring_api
from datamind.api.routes import management_api, fraud_api

__all__ = [
    'model_api',
    'scoring_api',
    'fraud_api',
    'management_api',
]