# Datamind/datamind/api/middlewares/cors.py

"""CORS 中间件

提供跨域资源共享（CORS）配置，允许前端应用访问 API。

功能特性：
  - 自定义允许的源（origins）
  - 自定义允许的方法（methods）
  - 自定义允许的请求头（headers）
  - 自定义暴露的响应头（expose_headers）
  - 支持凭证传递（credentials）
  - 预检请求缓存时间（max_age）

默认配置：
  - allow_origins: ["*"]（允许所有源，生产环境建议限制）
  - allow_methods: GET、POST、PUT、DELETE、OPTIONS、PATCH
  - allow_headers: Content-Type、Authorization、X-Request-ID、X-API-Key、X-Application-ID
  - expose_headers: X-Request-ID、X-Process-Time-MS、X-RateLimit-Limit、X-RateLimit-Remaining、X-RateLimit-Reset
  - allow_credentials: True（允许携带凭证）
  - max_age: 600 秒（预检请求缓存时间）

CORS 响应头说明：
  - Access-Control-Allow-Origin: 允许的源
  - Access-Control-Allow-Credentials: 是否允许凭证
  - Access-Control-Allow-Methods: 允许的方法
  - Access-Control-Allow-Headers: 允许的请求头
  - Access-Control-Expose-Headers: 暴露的响应头
  - Access-Control-Max-Age: 预检请求缓存时间
"""

from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp
from typing import List, Optional


class CustomCORSMiddleware(CORSMiddleware):
    """
    自定义CORS中间件

    扩展FastAPI的CORS中间件，添加自定义配置和日志。
    支持配置允许的源、方法、头信息等。
    """

    def __init__(
            self,
            app: ASGIApp,
            allow_origins: List[str] = None,
            allow_credentials: bool = True,
            allow_methods: List[str] = None,
            allow_headers: List[str] = None,
            expose_headers: List[str] = None,
            max_age: int = 600,
            allow_origin_regex: Optional[str] = None,
    ):
        """
        初始化 CORS 中间件

        参数:
            app: ASGI 应用
            allow_origins: 允许的源列表，默认 ["*"]
            allow_credentials: 是否允许携带凭证（Cookie、Authorization等），默认 True
            allow_methods: 允许的 HTTP 方法，默认 ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
            allow_headers: 允许的请求头，默认包含常用头信息
            expose_headers: 暴露给前端的响应头，默认包含自定义响应头
            max_age: 预检请求缓存时间（秒），默认 600
            allow_origin_regex: 允许的源正则表达式
        """
        # 默认配置
        allow_origins = allow_origins or ["*"]
        allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        allow_headers = allow_headers or [
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "X-API-Key",
            "X-Application-ID"
        ]
        expose_headers = expose_headers or [
            "X-Request-ID",
            "X-Process-Time-MS",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]

        super().__init__(
            app=app,
            allow_origins=allow_origins,
            allow_credentials=allow_credentials,
            allow_methods=allow_methods,
            allow_headers=allow_headers,
            expose_headers=expose_headers,
            max_age=max_age,
            allow_origin_regex=allow_origin_regex
        )