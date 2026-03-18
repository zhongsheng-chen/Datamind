# datamind/api/middlewares/cors.py
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp
from typing import List, Optional


class CustomCORSMiddleware(CORSMiddleware):
    """
    自定义CORS中间件

    扩展FastAPI的CORS中间件，添加自定义配置和日志
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