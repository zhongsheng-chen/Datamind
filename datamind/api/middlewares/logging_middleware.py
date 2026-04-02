# datamind/api/middlewares/logging_middleware.py

"""日志中间件

记录所有 HTTP 请求和响应的详细信息，用于审计和问题排查。

功能特性：
  - 请求日志记录：方法、路径、请求头、请求体
  - 响应日志记录：状态码、响应头、处理时间
  - 请求ID追踪：自动生成或提取 X-Request-ID
  - 敏感数据脱敏：自动隐藏密码、token 等敏感信息（支持配置化）
  - 错误日志记录：异常信息和堆栈跟踪
  - 审计日志：记录错误请求和异常事件
  - 链路追踪：完整的 span 追踪

中间件行为：
  - 自动生成请求ID（如果请求头没有 X-Request-ID）
  - 记录所有请求的详细信息（可配置排除路径）
  - 计算请求处理时间（毫秒）
  - 添加响应头 X-Request-ID、X-Trace-ID、X-Span-ID、X-Process-Time-MS
  - 错误请求（状态码 >= 400）额外记录审计日志
  - 异常请求记录完整堆栈信息

排除路径（exclude_paths）：
  - /health: 健康检查端点
  - /metrics: 监控指标端点
  - /static: 静态文件
  - /favicon.ico: 网站图标

敏感字段脱敏：
  自动识别并脱敏以下字段（可通过配置自定义）：
  - password, token, api_key, secret
  - credit_card, card_number, cvv
  - id_number, ssn, phone, email

配置说明：
  - 通过 LoggingMiddlewareConfig 配置中间件行为
  - 通过 SensitiveDataConfig 配置敏感字段和脱敏规则
  - 支持环境变量覆盖默认配置

使用示例：
    # 添加中间件
    app.add_middleware(
        LoggingMiddleware,
        log_request_body=True,
        log_response_body=False,
        mask_sensitive_data=True
    )
"""

import re
import time
import uuid
import json
import asyncio
import traceback
from typing import Optional, List, Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import Response

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.config.settings import LoggingMiddlewareConfig, SensitiveDataConfig
from datamind.config import get_settings

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志中间件

    记录所有HTTP请求和响应的详细信息，支持请求体脱敏和响应时间统计。

    属性:
        exclude_paths: 排除日志记录的路径列表
        log_request_body: 是否记录请求体
        log_response_body: 是否记录响应体
        mask_sensitive_data: 是否脱敏敏感数据
        max_body_size: 最大记录请求体大小（字节）
        log_headers: 是否记录请求头
        sensitive_fields: 敏感字段集合
        sensitive_headers: 敏感请求头集合
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[LoggingMiddlewareConfig] = None,
            sensitive_config: Optional[SensitiveDataConfig] = None,
            exclude_paths: Optional[List[str]] = None,
            log_request_body: Optional[bool] = None,
            log_response_body: Optional[bool] = None,
            mask_sensitive_data: Optional[bool] = None,
            max_body_size: Optional[int] = None,
            log_headers: Optional[bool] = None
    ):
        """
        初始化日志中间件

        参数:
            app: ASGI 应用
            config: 日志中间件配置对象
            sensitive_config: 敏感数据配置对象
            exclude_paths: 排除日志记录的路径列表
            log_request_body: 是否记录请求体
            log_response_body: 是否记录响应体
            mask_sensitive_data: 是否脱敏敏感数据
            max_body_size: 最大记录请求体大小（字节）
            log_headers: 是否记录请求头
        """
        super().__init__(app)

        # 加载配置
        settings = get_settings()
        self.config = config or settings.logging_middleware
        self.sensitive_config = sensitive_config or settings.sensitive_data

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.exclude_paths = exclude_paths or self.config.log_exclude_paths
        self.log_request_body = log_request_body if log_request_body is not None else self.config.log_request_body
        self.log_response_body = log_response_body if log_response_body is not None else self.config.log_response_body
        self.mask_sensitive_data = mask_sensitive_data if mask_sensitive_data is not None else True
        self.max_body_size = max_body_size or self.config.log_max_body_size
        self.log_headers = log_headers if log_headers is not None else self.config.log_headers

        # 从配置加载敏感字段设置
        self.sensitive_fields = set(self.sensitive_config.sensitive_fields)
        self.sensitive_headers = set(self.sensitive_config.sensitive_headers)
        self.mask_char = self.sensitive_config.mask_char
        self.show_partial = self.sensitive_config.show_partial

        # 预编译正则表达式
        self._compile_sensitive_patterns()

        logger.debug("日志中间件初始化完成: log_request_body=%s, log_response_body=%s, mask_sensitive=%s",
                    self.log_request_body, self.log_response_body, self.mask_sensitive_data)

    def _compile_sensitive_patterns(self):
        """预编译敏感字段正则表达式"""
        # JSON 字段脱敏模式
        self.sensitive_patterns = [
            re.compile(rf'"{field}"\s*:\s*"[^"]*"', re.IGNORECASE)
            for field in self.sensitive_fields
        ]

        # 查询参数脱敏模式
        self.query_param_patterns = [
            re.compile(rf'({field})=[^&]+', re.IGNORECASE)
            for field in self.sensitive_fields
        ]

        # 表单数据脱敏模式
        self.form_data_patterns = [
            re.compile(rf'{field}=[^&]+', re.IGNORECASE)
            for field in self.sensitive_fields
        ]

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 检查是否排除日志
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # 生成或获取请求ID
        request_id = await self._get_or_generate_request_id(request)
        context.set_request_id(request_id)
        request.state.request_id = request_id

        # 设置链路追踪信息
        trace_id = await self._setup_trace_id(request)
        parent_span_id = await self._setup_parent_span_id(request)
        span_id = context.generate_span_id()
        context.set_span_id(span_id)

        # 记录请求开始
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")

        # 记录请求日志
        await self._log_request(
            request, request_id, client_ip, user_agent,
            trace_id, span_id, parent_span_id
        )

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = (time.time() - start_time) * 1000

            # 记录响应日志
            await self._log_response(
                request, response, process_time,
                request_id, client_ip, user_agent,
                trace_id, span_id, parent_span_id
            )

            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Span-ID"] = span_id
            if parent_span_id:
                response.headers["X-Parent-Span-ID"] = parent_span_id
            response.headers["X-Process-Time-MS"] = str(round(process_time, 2))

            return response

        except asyncio.CancelledError:
            # 请求被取消，记录但不重新抛出
            process_time = (time.time() - start_time) * 1000
            await self._log_cancelled(
                request, process_time, request_id,
                client_ip, trace_id, span_id, parent_span_id
            )
            raise
        except Exception as e:
            # 记录异常
            process_time = (time.time() - start_time) * 1000
            await self._log_error(
                request, e, process_time, request_id,
                client_ip, trace_id, span_id, parent_span_id
            )
            raise

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除日志"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else "unknown"

    async def _get_or_generate_request_id(self, request: Request) -> str:
        """获取或生成请求ID"""
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            return request_id
        return str(uuid.uuid4())

    async def _setup_trace_id(self, request: Request) -> str:
        """设置 trace_id"""
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = context.generate_trace_id()
        context.set_trace_id(trace_id)
        return trace_id

    async def _setup_parent_span_id(self, request: Request) -> Optional[str]:
        """设置 parent_span_id"""
        parent_span_id = request.headers.get("X-Parent-Span-ID")
        if parent_span_id:
            context.set_parent_span_id(parent_span_id)
        else:
            context.set_parent_span_id("")
        return parent_span_id

    async def _safe_read_body(self, request: Request) -> Optional[str]:
        """安全读取请求体"""
        if not self.log_request_body or request.method not in ["POST", "PUT", "PATCH"]:
            return None

        try:
            body_bytes = await request.body()
            if not body_bytes:
                return None

            # 限制大小
            if len(body_bytes) > self.max_body_size:
                return f"<body too large: {len(body_bytes)} bytes, truncated>"

            # 解码
            try:
                body_str = body_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    body_str = body_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    return f"<binary data, length: {len(body_bytes)} bytes>"

            # 脱敏处理
            if self.mask_sensitive_data:
                body_str = self._mask_sensitive_data(body_str)

            return body_str

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("读取请求体失败: %s", e)
            return f"<error reading body: {type(e).__name__}>"

    async def _capture_response_body(self, response: Response) -> Response:
        """捕获响应体用于日志记录"""
        if not self.log_response_body:
            return response

        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
                # 限制大小
                if len(body) > self.max_body_size:
                    body = body[:self.max_body_size]
                    break

            # 存储响应体到 response 对象
            response._captured_body = body
            response._body_truncated = len(body) > self.max_body_size

            # 重新构建响应体迭代器
            async def generate():
                yield body

            response.body_iterator = generate()
            return response
        except Exception as e:
            logger.debug("捕获响应体失败: %s", e)
            return response

    async def _log_request(self, request: Request, request_id: str,
                           client_ip: str, user_agent: str,
                           trace_id: str, span_id: str, parent_span_id: Optional[str]):
        """记录请求日志"""
        # 获取请求体
        body = await self._safe_read_body(request)

        # 获取用户信息
        user_id = "anonymous"
        username = "anonymous"
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id', 'unknown')
            username = request.state.user.get('username', 'unknown')

        # 构建详情
        details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": self._mask_query_params(str(request.query_params)),
            "user_agent": user_agent,
            "trace_id": trace_id,
            "span_id": span_id,
            "username": username
        }

        if parent_span_id:
            details["parent_span_id"] = parent_span_id

        if self.log_headers:
            details["headers"] = self._get_safe_headers(request.headers)

        if body:
            details["request_body"] = body

        # 记录请求日志
        log_audit(
            action="HTTP_REQUEST",
            user_id=user_id,
            ip_address=client_ip,
            details=details,
            request_id=request_id
        )

    async def _log_response(self, request: Request, response: Response,
                            process_time: float, request_id: str,
                            client_ip: str, user_agent: str,
                            trace_id: str, span_id: str, parent_span_id: Optional[str]):
        """记录响应日志"""
        # 捕获响应体
        await self._capture_response_body(response)

        # 获取响应体
        response_body = None
        body_truncated = False
        if hasattr(response, '_captured_body') and response._captured_body:
            try:
                response_body = response._captured_body.decode('utf-8', errors='ignore')
                if self.mask_sensitive_data:
                    response_body = self._mask_sensitive_data(response_body)
                body_truncated = getattr(response, '_body_truncated', False)
            except Exception as e:
                response_body = f"<error reading body: {type(e).__name__}>"

        # 获取用户信息
        user_id = "anonymous"
        username = "anonymous"
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id', 'unknown')
            username = request.state.user.get('username', 'unknown')

        # 构建详情
        details = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time, 2),
            "user_agent": user_agent,
            "trace_id": trace_id,
            "span_id": span_id,
            "username": username
        }

        if parent_span_id:
            details["parent_span_id"] = parent_span_id

        if response_body:
            details["response_body"] = response_body
            if body_truncated:
                details["response_body_truncated"] = True

        if hasattr(response, '_captured_body'):
            details["response_size"] = len(response._captured_body)

        # 记录响应日志
        log_audit(
            action="HTTP_RESPONSE",
            user_id=user_id,
            ip_address=client_ip,
            details=details,
            request_id=request_id
        )

        # 如果响应状态码表示错误，记录额外审计日志
        if response.status_code >= 400:
            log_audit(
                action="HTTP_ERROR",
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "username": username
                },
                request_id=request_id
            )

    async def _log_error(self, request: Request, error: Exception,
                         process_time: float, request_id: str, client_ip: str,
                         trace_id: str, span_id: str, parent_span_id: Optional[str]):
        """记录错误日志"""
        error_trace = traceback.format_exc()

        user_id = "anonymous"
        username = "anonymous"
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id', 'unknown')
            username = request.state.user.get('username', 'unknown')

        log_audit(
            action="HTTP_EXCEPTION",
            user_id=user_id,
            ip_address=client_ip,
            details={
                "method": request.method,
                "path": request.url.path,
                "error": str(error),
                "error_type": type(error).__name__,
                "traceback": error_trace[:5000],  # 限制堆栈大小
                "process_time_ms": round(process_time, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "username": username
            },
            request_id=request_id
        )

    async def _log_cancelled(self, request: Request, process_time: float,
                             request_id: str, client_ip: str,
                             trace_id: str, span_id: str, parent_span_id: Optional[str]):
        """记录请求取消日志"""
        user_id = "anonymous"
        username = "anonymous"
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id', 'unknown')
            username = request.state.user.get('username', 'unknown')

        log_audit(
            action="HTTP_CANCELLED",
            user_id=user_id,
            ip_address=client_ip,
            details={
                "method": request.method,
                "path": request.url.path,
                "process_time_ms": round(process_time, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "username": username
            },
            request_id=request_id
        )

    def _get_safe_headers(self, headers) -> Dict[str, str]:
        """获取安全的请求头（脱敏）"""
        if not self.log_headers:
            return {}

        safe_headers = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                safe_headers[key] = "***REDACTED***"
            else:
                # 限制头部值长度
                if len(value) > 500:
                    safe_headers[key] = value[:500] + "..."
                else:
                    safe_headers[key] = value
        return safe_headers

    def _mask_query_params(self, query_string: str) -> str:
        """脱敏查询参数"""
        if not query_string or not self.mask_sensitive_data:
            return query_string

        result = query_string
        for pattern in self.query_param_patterns:
            result = pattern.sub(lambda m: f"{m.group(1)}=***", result)
        return result

    def _mask_sensitive_data(self, data: str) -> str:
        """脱敏敏感数据"""
        try:
            # 尝试解析JSON
            obj = json.loads(data)
            masked_obj = self._mask_dict(obj)
            return json.dumps(masked_obj, ensure_ascii=False)
        except json.JSONDecodeError:
            # 非JSON数据，使用正则表达式替换
            result = data
            for pattern in self.sensitive_patterns:
                result = pattern.sub(lambda m: m.group(0).split(':')[0] + ': "***"', result)
            # 也处理表单数据
            for pattern in self.form_data_patterns:
                result = pattern.sub(lambda m: f"{m.group(1)}=***", result)
            return result
        except Exception as e:
            logger.debug("脱敏处理失败: %s", e)
            return "***"

    def _mask_dict(self, obj: Any) -> Any:
        """递归脱敏字典"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # 检查是否为敏感字段
                is_sensitive = any(
                    sensitive in key.lower()
                    for sensitive in self.sensitive_fields
                )

                if is_sensitive and value:
                    # 敏感字段脱敏
                    result[key] = self._mask_value(key, value)
                else:
                    result[key] = self._mask_dict(value)
            return result
        elif isinstance(obj, list):
            return [self._mask_dict(item) for item in obj]
        else:
            return obj

    def _mask_value(self, key: str, value: Any) -> str:
        """根据字段类型和配置进行脱敏"""
        if not isinstance(value, str):
            return self.mask_char * 3

        if not self.show_partial:
            return self.mask_char * min(len(value), 8)

        # 手机号脱敏
        if any(x in key.lower() for x in ['phone', 'mobile', 'telephone']):
            if len(value) == 11 and value.isdigit():
                return value[:3] + '****' + value[-4:]

        # 邮箱脱敏
        if 'email' in key.lower():
            if '@' in value:
                local, domain = value.split('@')
                if len(local) > 3:
                    return local[:3] + '***@' + domain
                else:
                    return '***@' + domain

        # 身份证脱敏
        if any(x in key.lower() for x in ['id_number', 'id_card', 'ssn']):
            if len(value) == 18:
                return value[:6] + '********' + value[-4:]
            elif len(value) == 15:
                return value[:6] + '******' + value[-3:]

        # 信用卡脱敏
        if any(x in key.lower() for x in ['credit_card', 'card_number']):
            if len(value) >= 16:
                return value[:4] + '****' + value[-4:]

        # 默认脱敏：保留前2后2
        if len(value) > 4:
            return value[:2] + self.mask_char * (len(value) - 4) + value[-2:]
        else:
            return self.mask_char * len(value)


def setup_logging_middleware(
        app: ASGIApp,
        config: Optional[LoggingMiddlewareConfig] = None,
        **kwargs
) -> None:
    """
    设置日志中间件的便捷函数

    参数:
        app: ASGI 应用
        config: 日志中间件配置对象
        **kwargs: 其他参数，会传递给 LoggingMiddleware

    示例:
        setup_logging_middleware(
            app,
            log_request_body=True,
            log_response_body=False
        )
    """
    app.add_middleware(LoggingMiddleware, config=config, **kwargs)
    logger.info("日志中间件已添加")