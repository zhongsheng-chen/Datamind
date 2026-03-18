# Datamind/datamind/api/middlewares/logging_middleware.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import uuid
from typing import Optional
import json

from datamind.core import log_manager, set_request_id
from datamind.core.logging.context import set_request_id as set_context_request_id


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志中间件

    记录所有HTTP请求和响应的详细信息
    """

    def __init__(
            self,
            app: ASGIApp,
            exclude_paths: Optional[list] = None,
            log_request_body: bool = True,
            log_response_body: bool = False,
            mask_sensitive_data: bool = True
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/static",
            "/favicon.ico"
        ]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.mask_sensitive_data = mask_sensitive_data

        # 敏感字段列表
        self.sensitive_fields = [
            'password', 'token', 'api_key', 'secret',
            'credit_card', 'id_number', 'phone', 'email'
        ]

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 生成或获取请求ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        set_context_request_id(request_id)

        # 检查是否排除日志
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # 记录请求开始
        start_time = time.time()

        # 获取请求信息
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # 记录请求日志
        await self._log_request(request, request_id, client_ip, user_agent)

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = (time.time() - start_time) * 1000

            # 记录响应日志
            await self._log_response(
                request, response, process_time,
                request_id, client_ip, user_agent
            )

            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-MS"] = str(round(process_time, 2))

            return response

        except Exception as e:
            # 记录异常
            process_time = (time.time() - start_time) * 1000
            await self._log_error(request, e, process_time, request_id, client_ip)
            raise

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除日志"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    async def _log_request(self, request: Request, request_id: str,
                           client_ip: str, user_agent: str):
        """记录请求日志"""
        # 获取请求体
        body = None
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = body_bytes.decode()
                    if self.mask_sensitive_data:
                        body = self._mask_sensitive_data(body)
            except:
                body = "<无法读取请求体>"

        # 记录访问日志
        log_manager.log_access(
            method=request.method,
            path=request.url.path,
            status=0,  # 暂时未知
            duration_ms=0,
            ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            request_body=body,
            query_params=str(request.query_params),
            headers=self._get_safe_headers(request.headers)
        )

    async def _log_response(self, request: Request, response,
                            process_time: float, request_id: str,
                            client_ip: str, user_agent: str):
        """记录响应日志"""
        # 获取响应体
        body = None
        if self.log_response_body:
            try:
                # 注意：这里需要特殊处理，因为response.body可能不可用
                body = "<响应体未捕获>"
            except:
                pass

        # 记录访问日志
        log_manager.log_access(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(process_time, 2),
            ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            response_body=body,
            response_size=len(response.body) if hasattr(response, 'body') else 0
        )

        # 如果响应状态码表示错误，记录审计日志
        if response.status_code >= 400:
            log_manager.log_audit(
                action="HTTP_ERROR",
                user_id=request.state.user.get('id', 'unknown') if hasattr(request.state, 'user') else 'anonymous',
                ip_address=client_ip,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time, 2)
                },
                request_id=request_id
            )

    async def _log_error(self, request: Request, error: Exception,
                         process_time: float, request_id: str, client_ip: str):
        """记录错误日志"""
        import traceback

        error_trace = traceback.format_exc()

        log_manager.log_audit(
            action="HTTP_EXCEPTION",
            user_id=request.state.user.get('id', 'unknown') if hasattr(request.state, 'user') else 'anonymous',
            ip_address=client_ip,
            details={
                "method": request.method,
                "path": request.url.path,
                "error": str(error),
                "error_type": type(error).__name__,
                "traceback": error_trace,
                "process_time_ms": round(process_time, 2)
            },
            request_id=request_id
        )

    def _get_safe_headers(self, headers) -> dict:
        """获取安全的请求头（脱敏）"""
        safe_headers = {}
        sensitive_headers = ['authorization', 'cookie', 'x-api-key']

        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                safe_headers[key] = "***"
            else:
                safe_headers[key] = value

        return safe_headers

    def _mask_sensitive_data(self, data: str) -> str:
        """脱敏敏感数据"""
        try:
            # 尝试解析JSON
            obj = json.loads(data)

            # 递归脱敏
            masked_obj = self._mask_dict(obj)

            return json.dumps(masked_obj)

        except:
            # 非JSON数据，简单替换
            for field in self.sensitive_fields:
                if field in data.lower():
                    # 简单替换，实际应该用正则
                    data = data.replace(field, "***")
            return data

    def _mask_dict(self, obj):
        """递归脱敏字典"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                    result[key] = "***"
                else:
                    result[key] = self._mask_dict(value)
            return result
        elif isinstance(obj, list):
            return [self._mask_dict(item) for item in obj]
        else:
            return obj