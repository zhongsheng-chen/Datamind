# datamind/api/middlewares/__init__.py

"""API 中间件模块

提供统一的中间件导出入口，包括认证、日志、限流、CORS、安全等功能。

中间件列表：
  - AuthenticationMiddleware: 认证中间件（JWT、API Key、Basic Auth）
  - LoggingMiddleware: 日志中间件（请求/响应日志、敏感数据脱敏）
  - RateLimitMiddleware: 限流中间件（IP/用户/API Key 限流）
  - IPRateLimitMiddleware: IP限流中间件
  - UserRateLimitMiddleware: 用户限流中间件
  - CustomCORSMiddleware: CORS 中间件（跨域资源共享配置）
  - DevelopmentCORSMiddleware: 开发环境CORS中间件
  - ProductionCORSMiddleware: 生产环境CORS中间件
  - SecurityHeadersMiddleware: 安全响应头中间件
  - IPAccessMiddleware: IP访问控制中间件（白名单/黑名单）
  - RequestSizeLimitMiddleware: 请求大小限制中间件
  - RequestValidationMiddleware: 请求验证中间件（时间戳/签名）
  - SecurityMiddleware: 组合安全中间件
  - PerformanceMiddleware: 性能监控中间件
  - SlowRequestMiddleware: 慢请求监控中间件
  - PostgreSQLPerformanceMiddleware: PostgreSQL性能监控中间件

中间件加载顺序（建议）：
  - LoggingMiddleware - 最先记录请求信息
  - AuthenticationMiddleware - 验证用户身份
  - RateLimitMiddleware - 限流检查
  - CustomCORSMiddleware - CORS 处理
  - SecurityMiddleware - 安全防护
  - PerformanceMiddleware - 性能监控
  - 其他业务中间件
"""

from datamind.api.middlewares.auth import (
    AuthenticationMiddleware,
    create_jwt_token,
    verify_jwt_token,
    decode_jwt_token,
    refresh_jwt_token
)

from datamind.api.middlewares.logging_middleware import (
    LoggingMiddleware,
    setup_logging_middleware
)

from datamind.api.middlewares.rate_limit import (
    RateLimitMiddleware,
    IPRateLimitMiddleware,
    UserRateLimitMiddleware,
    setup_rate_limit_middleware
)

from datamind.api.middlewares.cors import (
    CustomCORSMiddleware,
    DevelopmentCORSMiddleware,
    ProductionCORSMiddleware,
    setup_cors,
    get_cors_config,
    is_cors_preflight_request,
    add_cors_headers,
    validate_cors_config
)

from datamind.api.middlewares.security import (
    SecurityHeadersMiddleware,
    IPAccessMiddleware,
    IPWhitelistMiddleware,
    RequestSizeLimitMiddleware,
    RequestValidationMiddleware,
    SecurityMiddleware,
    setup_security_middleware
)

from datamind.api.middlewares.performance import (
    PerformanceMiddleware,
    SlowRequestMiddleware,
    setup_performance_middleware
)

from datamind.api.middlewares.database_performance import (
    PostgreSQLPerformanceMiddleware,
    setup_database_performance_middleware
)

from datamind.api.middlewares.version import APIVersionMiddleware, APIVersionCompatibilityMiddleware

__all__ = [
    'AuthenticationMiddleware',
    'create_jwt_token',
    'verify_jwt_token',
    'decode_jwt_token',
    'refresh_jwt_token',
    'LoggingMiddleware',
    'setup_logging_middleware',
    'RateLimitMiddleware',
    'IPRateLimitMiddleware',
    'UserRateLimitMiddleware',
    'setup_rate_limit_middleware',
    'CustomCORSMiddleware',
    'DevelopmentCORSMiddleware',
    'ProductionCORSMiddleware',
    'setup_cors',
    'get_cors_config',
    'is_cors_preflight_request',
    'add_cors_headers',
    'validate_cors_config',
    'SecurityHeadersMiddleware',
    'IPAccessMiddleware',
    'IPWhitelistMiddleware',
    'RequestSizeLimitMiddleware',
    'RequestValidationMiddleware',
    'SecurityMiddleware',
    'setup_security_middleware',
    'PerformanceMiddleware',
    'SlowRequestMiddleware',
    'setup_performance_middleware',
    'PostgreSQLPerformanceMiddleware',
    'setup_database_performance_middleware',
    'APIVersionMiddleware',
    'APIVersionCompatibilityMiddleware'
]