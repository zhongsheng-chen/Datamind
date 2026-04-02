# datamind/api/middlewares/version.py

"""API 版本管理中间件

提供 API 版本控制功能，包括版本路由、版本弃用警告、版本重定向和版本兼容性检查。

功能特性：
  - 版本路由：自动识别请求路径中的 API 版本
  - 版本弃用警告：对已弃用的版本返回警告头信息
  - 版本重定向：支持将旧版本请求重定向到新版本
  - 版本兼容性检查：验证请求的版本是否受支持

中间件类型：
  APIVersionMiddleware: API 版本管理中间件
     - 提取请求路径中的版本号
     - 检查版本是否支持
     - 检查版本是否已弃用
     - 处理版本重定向
     - 添加版本相关的响应头

  APIVersionCompatibilityMiddleware: API 版本兼容性中间件
     - 处理旧版本请求的兼容性转换
     - 支持请求和响应的格式转换

响应头说明：
  - X-API-Deprecated: 标识 API 版本已弃用
  - X-API-Deprecated-Version: 已弃用的版本号
  - X-API-Deprecated-Message: 弃用提示信息
  - X-API-Latest-Version: 最新可用版本

版本重定向配置：
  - 通过 settings.api.version_redirects 配置
  - 支持将旧版本请求自动重定向到新版本（301 永久重定向）

使用示例：
    # 添加版本管理中间件
    app.add_middleware(APIVersionMiddleware)

    # 添加版本兼容性中间件
    app.add_middleware(APIVersionCompatibilityMiddleware)

配置示例（settings.py）：
    api = ApiConfig(
        supported_versions=["v1", "v2"],
        deprecated_versions=["v1"],
        api_version="v2",
        version_redirects={"v0": "v1"}
    )
"""

import re
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import RedirectResponse

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.config import get_settings

logger = get_logger(__name__)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    API 版本管理中间件

    处理 API 版本路由、版本检查和版本重定向。

    属性:
        supported_versions: 支持的 API 版本列表
        deprecated_versions: 已弃用的 API 版本列表
        current_version: 当前 API 版本
        version_redirects: 版本重定向映射
    """

    def __init__(self, app: ASGIApp):
        """
        初始化 API 版本管理中间件

        参数:
            app: ASGI 应用
        """
        super().__init__(app)
        self.settings = get_settings()
        self.supported_versions = self.settings.api.supported_versions
        self.deprecated_versions = self.settings.api.deprecated_versions
        self.current_version = self.settings.api.api_version
        self.version_redirects = self.settings.api.version_redirects

        # 版本正则表达式
        self.version_pattern = re.compile(r'^/api/(v\d+)/')
        self.api_path_pattern = re.compile(r'^/api/(?:v\d+)?/(.*)$')

        logger.info("API版本管理中间件初始化完成: 支持版本=%s, 已弃用版本=%s, 当前版本=%s, 重定向规则=%s",
                   self.supported_versions, self.deprecated_versions,
                   self.current_version, list(self.version_redirects.keys()))

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

                logger.info("API版本重定向: %s -> %s, 路径=%s", version, target_version, request.url.path)

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

                logger.warning("不支持的API版本: %s, 路径=%s, 客户端IP=%s",
                              version, request.url.path, client_ip)

                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "unsupported_api_version",
                        "version": version,
                        "supported_versions": self.supported_versions,
                        "current_version": self.current_version,
                        "message": f"API版本 {version} 不受支持，支持的版本: {self.supported_versions}"
                    }
                )

            # 检查版本是否已弃用
            if version in self.deprecated_versions:
                response = await call_next(request)
                response.headers["X-API-Deprecated"] = "true"
                response.headers["X-API-Deprecated-Version"] = version
                response.headers["X-API-Deprecated-Message"] = (
                    f"API版本 {version} 已弃用，请升级到 {self.current_version}"
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

                logger.info("已弃用的API版本请求: %s, 路径=%s", version, request.url.path)
                return response

            # 正常请求
            return await call_next(request)

        # 无版本号路径（如 /health），直接放行
        return await call_next(request)


class APIVersionCompatibilityMiddleware(BaseHTTPMiddleware):
    """
    API 版本兼容性中间件

    处理旧版本请求的兼容性转换，支持请求和响应的格式映射。

    属性:
        compatibility_map: 版本兼容性配置映射
    """

    def __init__(self, app: ASGIApp):
        """
        初始化 API 版本兼容性中间件

        参数:
            app: ASGI 应用
        """
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

        logger.info("API版本兼容性中间件初始化完成: 兼容版本=%s", list(self.compatibility_map.keys()))

    async def dispatch(self, request: Request, call_next):
        """处理请求，进行版本兼容性转换"""
        request_id = context.get_request_id()

        # 提取版本号
        match = re.match(r'^/api/(v\d+)/', request.url.path)
        if match:
            version = match.group(1)

            # 如果需要兼容性处理
            if version in self.compatibility_map:
                logger.debug("API版本兼容性处理: 版本=%s, 路径=%s", version, request.url.path)
                # 可以在这里进行请求转换

        return await call_next(request)

    def _map_v1_to_v2_response(self, v1_response: dict) -> dict:
        """
        将 v1 响应转换为 v2 格式

        参数:
            v1_response: v1 格式的响应字典

        返回:
            v2 格式的响应字典
        """
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
        """
        将 v2 请求转换为 v1 格式

        参数:
            v2_request: v2 格式的请求字典

        返回:
            v1 格式的请求字典
        """
        return {
            "application_id": v2_request.get("application_id", ""),
            "features": v2_request.get("features", {}),
            "model_id": v2_request.get("model_id"),
            "ab_test_id": v2_request.get("experiment", {}).get("test_id")
        }