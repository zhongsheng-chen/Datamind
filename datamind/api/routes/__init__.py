# datamind/api/routes/__init__.py

"""API 路由模块

支持多版本 API 路由管理
"""

from datamind.api.routes.v1 import router as v1_router

__all__ = ["v1_router"]