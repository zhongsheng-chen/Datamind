# datamind/api/middlewares/version.py

"""API 版本管理中间件

提供 API 版本控制功能，包括：
  - 版本路由
  - 版本弃用警告
  - 版本重定向
  - 版本兼容性检查
"""

import re
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import RedirectResponse

from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import AuditAction
from datamind.config import get_settings


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API 版本管理中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()
        self.supported_versions = self.settings.api.supported_versions
        self.deprecated_versions = self.settings.api.deprecated_versions
        self.current_version = self.settings.api.api_version
        self.version_redirects = self.settings.api.version_redirects

        # 版本正则表达式
        self.version_pattern = re.compile(r'^/api/(v\d+)/')
        self.api_path_pattern = re.compile(r'^/api/(?:v\d+)?/(.*)$')

    async def dispatch(self, request: Request, call_next):
        """处理请求，检查 API 版本"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        client_ip = request.client.host if request.client else None

        # 提取版本号
        match = self.version_pattern.match(request.url.path)

        if match:
            version = match.group(1)

            # 检查是否需要重定向
            if version in self.version_redirects:
                target_version = self.version_redirects[version]
                new_path = f"/api/{target_version}{request.url.path.replace(f'/api/{version}', '')}"

                log_audit(
                    action=AuditAction.CONFIG_UPDATE.value,
                    user_id="system",
                    ip_address=client_ip,
                    details={
                        "path": request.url.path,
                        "method": request.method,
                        "from_version": version,
                        "to_version": target_version,
                        "reason": "version_redirect",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                return RedirectResponse(
                    url=new_path,
                    status_code=301
                )

            # 检查版本是否支持
            if version not in self.supported_versions:
                log_audit(
                    action=AuditAction.INVALID_TIMESTAMP.value,
                    user_id="anonymous",
                    ip_address=client_ip,
                    details={
                        "path": request.url.path,
                        "method": request.method,
                        "version": version,
                        "supported_versions": self.supported_versions,
                        "reason": "unsupported_version",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "unsupported_api_version",
                        "version": version,
                        "supported_versions": self.supported_versions,
                        "current_version": self.current_version,
                        "message": f"API version {version} is not supported. "
                                   f"Supported versions: {self.supported_versions}"
                    }
                )

            # 检查版本是否已弃用
            if version in self.deprecated_versions:
                response = await call_next(request)
                response.headers["X-API-Deprecated"] = "true"
                response.headers["X-API-Deprecated-Version"] = version
                response.headers["X-API-Deprecated-Message"] = (
                    f"API version {version} is deprecated. "
                    f"Please upgrade to {self.current_version}"
                )
                response.headers["X-API-Latest-Version"] = self.current_version

                log_audit(
                    action=AuditAction.CONFIG_UPDATE.value,
                    user_id="anonymous",
                    ip_address=client_ip,
                    details={
                        "path": request.url.path,
                        "method": request.method,
                        "version": version,
                        "deprecated_versions": self.deprecated_versions,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                return response

            # 正常请求
            return await call_next(request)

        # 无版本号路径（如 /health），直接放行
        return await call_next(request)


class APIVersionCompatibilityMiddleware(BaseHTTPMiddleware):
    """API 版本兼容性中间件

    处理旧版本请求的兼容性转换
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()
        self.compatibility_map = {
            # v1 兼容配置
            "v1": {
                "scoring": {
                    "response_mapping": self._map_v1_to_v2_response,
                    "request_mapping": self._map_v2_to_v1_request
                }
            }
        }

    async def dispatch(self, request: Request, call_next):
        """处理请求，进行版本兼容性转换"""
        request_id = context.get_request_id()

        # 提取版本号
        match = re.match(r'^/api/(v\d+)/', request.url.path)
        if match:
            version = match.group(1)

            # 如果需要兼容性处理
            if version in self.compatibility_map:
                # 可以在这里进行请求转换
                pass

        return await call_next(request)

    def _map_v1_to_v2_response(self, v1_response: dict) -> dict:
        """将 v1 响应转换为 v2 格式"""
        return {
            "score": v1_response.get("total_score", 0),
            "probability": v1_response.get("default_probability", 0),
            "feature_contributions": v1_response.get("feature_scores", {}),
            "model": {
                "id": v1_response.get("model_id", ""),
                "version": v1_response.get("model_version", "")
            },
            "request": {
                "id": v1_response.get("request_id", ""),
                "application_id": v1_response.get("application_id", "")
            },
            "performance": {
                "processing_time_ms": v1_response.get("processing_time_ms", 0)
            }
        }

    def _map_v2_to_v1_request(self, v2_request: dict) -> dict:
        """将 v2 请求转换为 v1 格式"""
        return {
            "application_id": v2_request.get("application_id", ""),
            "features": v2_request.get("features", {}),
            "model_id": v2_request.get("model_id"),
            "ab_test_id": v2_request.get("experiment", {}).get("test_id")
        }