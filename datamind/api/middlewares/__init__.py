# datamind/api/middlewares/__init__.py

"""API 中间件模块

提供统一的中间件导出入口，包括认证、日志、限流、CORS 等功能。

中间件列表：
  - AuthenticationMiddleware: 认证中间件（JWT、API Key、Basic Auth）
  - LoggingMiddleware: 日志中间件（请求/响应日志、敏感数据脱敏）
  - RateLimitMiddleware: 限流中间件（IP/用户/API Key 限流）
  - CustomCORSMiddleware: CORS 中间件（跨域资源共享配置）

中间件加载顺序（建议）：
  - LoggingMiddleware - 最先记录请求信息
  - AuthenticationMiddleware - 验证用户身份
  - RateLimitMiddleware - 限流检查
  - CustomCORSMiddleware - CORS 处理
  - 其他业务中间件
"""

from datamind.api.middlewares.auth import AuthenticationMiddleware
from datamind.api.middlewares.logging_middleware import LoggingMiddleware
from datamind.api.middlewares.rate_limit import RateLimitMiddleware
from datamind.api.middlewares.cors import CustomCORSMiddleware

__all__ = [
    'AuthenticationMiddleware',
    'LoggingMiddleware',
    'RateLimitMiddleware',
    'CustomCORSMiddleware',
]