# Datamind/datamind/api/middlewares/performance.py

"""性能监控中间件

提供系统性能监控和慢请求检测功能，帮助识别性能瓶颈。

功能特性：
  - CPU 使用率监控：记录请求前后的 CPU 使用率
  - 内存使用监控：记录请求前后的内存占用（MB）
  - 请求处理时间统计：精确到毫秒
  - 模型性能监控：记录模型推理请求的详细指标
  - 慢请求检测：记录超过阈值的慢请求
  - 并发请求监控：记录当前并发请求数

中间件类型：
  PerformanceMiddleware: 性能监控中间件
     - 记录每个请求的 CPU、内存、耗时
     - 对模型推理请求记录更详细的性能指标
     - 记录性能日志
     - 支持采样率控制

  SlowRequestMiddleware: 慢请求监控中间件
     - 检测处理时间超过阈值的请求
     - 记录审计日志
     - 可配置慢请求阈值（默认 1000ms）

性能指标：
  - process_time: 请求处理时间（毫秒）
  - cpu_usage: 当前 CPU 使用率（%）
  - memory_usage: 当前内存使用（MB）
  - cpu_delta: CPU 使用率变化
  - memory_delta: 内存使用变化
  - concurrent_requests: 并发请求数
  - db_queries: 数据库查询次数
  - db_query_time: 数据库查询总耗时

模型推理性能：
  - 自动识别 /scoring/predict 和 /fraud/predict 路径
  - 获取模型ID和版本
  - 记录模型推理的详细性能指标
"""

import time
import json
import psutil
import asyncio
import random
import re
from typing import Optional, Dict, Any, List, Set
from collections import defaultdict
from dataclasses import dataclass, field
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import AuditAction
from datamind.core.ml.model_loader import model_loader
from datamind.config import get_settings
from datamind.config import PerformanceConfig


@dataclass
class PerformanceStats:
    """性能统计数据结构"""
    total_requests: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    errors: int = 0
    by_endpoint: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    性能监控中间件

    记录系统性能指标和模型性能，包括 CPU、内存、请求耗时等。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[PerformanceConfig] = None,
            enable_detailed: Optional[bool] = None,
            enable_concurrent_tracking: Optional[bool] = None,
            enable_db_tracking: Optional[bool] = None,
            sample_rate: Optional[float] = None,
            exclude_paths: Optional[List[str]] = None
    ):
        """
        初始化性能监控中间件

        参数:
            app: ASGI 应用
            config: 性能监控配置对象
            enable_detailed: 是否启用详细监控（包括 CPU/内存详细指标）
            enable_concurrent_tracking: 是否启用并发请求追踪
            enable_db_tracking: 是否启用数据库查询追踪
            sample_rate: 采样率 (0.0-1.0)，用于高负载场景
            exclude_paths: 排除监控的路径列表
        """
        super().__init__(app)

        # 加载配置
        settings = get_settings()
        self.config = config or settings.performance

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.enable_detailed = enable_detailed if enable_detailed is not None else self.config.performance_detailed
        self.enable_concurrent_tracking = enable_concurrent_tracking if enable_concurrent_tracking is not None else self.config.performance_concurrent_tracking
        self.enable_db_tracking = enable_db_tracking if enable_db_tracking is not None else self.config.performance_db_tracking
        self.sample_rate = sample_rate if sample_rate is not None else self.config.performance_sample_rate
        self.slow_threshold = self.config.slow_request_threshold
        self.slow_query_threshold = self.config.slow_query_threshold

        # 确保采样率在有效范围内
        self.sample_rate = max(0.0, min(1.0, self.sample_rate))

        # 排除路径
        self.exclude_paths = exclude_paths or settings.logging_middleware.log_exclude_paths

        # 进程监控
        self.process = psutil.Process()

        # 并发请求追踪
        self.concurrent_requests = 0
        self._concurrent_lock = asyncio.Lock()

        # 性能统计
        self.stats = PerformanceStats()
        self._stats_lock = asyncio.Lock()

        # 启动后台监控任务
        self._background_tasks: Set[asyncio.Task] = set()

        # 缓存模型信息
        self._model_info_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()

        # 查询计数器（用于当前请求）
        self._query_counters: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "time": 0.0})
        self._counter_lock = asyncio.Lock()

        # 内存缓存清理任务
        if self.enable_detailed:
            self._start_cleanup_task()

    def _should_monitor(self, path: str) -> bool:
        """检查是否应该监控该路径"""
        # 检查采样率
        if self.sample_rate < 1.0:
            if random.random() > self.sample_rate:
                return False

        # 检查排除路径
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return False

        return True

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 检查是否应该监控
        if not self._should_monitor(request.url.path):
            return await call_next(request)

        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        trace_id = context.get_trace_id()
        start_time = time.time()

        # 重置当前请求的查询计数器
        current_request_id = request_id or str(id(request))
        async with self._counter_lock:
            self._query_counters[current_request_id] = {"count": 0, "time": 0.0}

        # 更新并发请求数
        if self.enable_concurrent_tracking:
            async with self._concurrent_lock:
                self.concurrent_requests += 1
                current_concurrent = self.concurrent_requests

        # 记录开始时的系统状态
        start_cpu = self._get_cpu_usage() if self.enable_detailed else 0
        start_memory = self._get_memory_usage() if self.enable_detailed else 0

        # 处理请求
        response = None
        is_error = False
        try:
            response = await call_next(request)
        except Exception:
            is_error = True
            raise
        finally:
            # 计算性能指标
            process_time = (time.time() - start_time) * 1000

            # 获取数据库查询统计
            db_queries = 0
            db_time = 0.0
            if self.enable_db_tracking:
                async with self._counter_lock:
                    query_stats = self._query_counters.pop(current_request_id, {"count": 0, "time": 0.0})
                    db_queries = query_stats["count"]
                    db_time = query_stats["time"]

            # 更新并发请求数
            if self.enable_concurrent_tracking:
                async with self._concurrent_lock:
                    self.concurrent_requests -= 1

            # 更新统计信息
            await self._update_stats(
                endpoint=request.url.path,
                process_time=process_time,
                is_error=is_error
            )

            # 记录结束时的系统状态
            end_cpu = self._get_cpu_usage() if self.enable_detailed else 0
            end_memory = self._get_memory_usage() if self.enable_detailed else 0

            # 获取用户信息
            user_id = "anonymous"
            username = "anonymous"
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.get('id', 'unknown')
                username = request.state.user.get('username', 'unknown')

            client_ip = self._get_client_ip(request)

            # 构建性能日志参数
            performance_params = {
                "operation": f"{request.method} {request.url.path}",
                "duration_ms": round(process_time, 2),
                "status_code": response.status_code if response else 500,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "is_error": is_error,
                "username": username
            }

            # 添加并发请求数
            if self.enable_concurrent_tracking:
                performance_params["concurrent_requests"] = current_concurrent

            # 添加数据库查询统计
            if self.enable_db_tracking:
                performance_params["db_queries"] = db_queries
                performance_params["db_time_ms"] = round(db_time, 2)

            # 添加详细指标（如果启用）
            if self.enable_detailed:
                performance_params.update({
                    "cpu_usage": round(end_cpu, 2),
                    "memory_usage": round(end_memory, 2),
                    "cpu_delta": round(end_cpu - start_cpu, 2),
                    "memory_delta": round(end_memory - start_memory, 2)
                })

            # 记录性能日志
            log_audit(
                action=AuditAction.PERFORMANCE_METRIC.value,
                user_id=user_id,
                ip_address=client_ip,
                details=performance_params,
                request_id=request_id
            )

            # 如果是模型推理请求，记录更详细的指标
            if self._is_model_request(request.url.path):
                await self._log_model_performance(
                    request=request,
                    process_time=process_time,
                    user_id=user_id,
                    client_ip=client_ip,
                    request_id=request_id,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    is_error=is_error,
                    db_queries=db_queries,
                    db_time=db_time
                )

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    def _get_cpu_usage(self) -> float:
        """获取CPU使用率（百分比）"""
        try:
            return self.process.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    def _get_memory_usage(self) -> float:
        """获取内存使用（MB）"""
        try:
            return self.process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def _is_model_request(self, path: str) -> bool:
        """检查是否为模型推理请求"""
        model_paths = ["/scoring/predict", "/fraud/predict", "/model/predict"]
        return any(model_path in path for model_path in model_paths)

    async def _update_stats(self, endpoint: str, process_time: float, is_error: bool):
        """更新性能统计"""
        async with self._stats_lock:
            self.stats.total_requests += 1
            self.stats.total_time += process_time
            self.stats.min_time = min(self.stats.min_time, process_time)
            self.stats.max_time = max(self.stats.max_time, process_time)

            if is_error:
                self.stats.errors += 1

            # 按端点统计
            if endpoint not in self.stats.by_endpoint:
                self.stats.by_endpoint[endpoint] = {
                    "count": 0,
                    "total_time": 0.0,
                    "errors": 0
                }

            endpoint_stats = self.stats.by_endpoint[endpoint]
            endpoint_stats["count"] += 1
            endpoint_stats["total_time"] += process_time
            if is_error:
                endpoint_stats["errors"] += 1

    def record_query(self, query_text: str, duration_ms: float):
        """记录数据库查询（由 SQLAlchemy 事件调用）"""
        if not self.enable_db_tracking:
            return

        # 获取当前请求ID
        request_id = context.get_request_id()
        if not request_id:
            return

        # 更新查询计数
        asyncio.create_task(self._record_query_async(request_id, query_text, duration_ms))

    async def _record_query_async(self, request_id: str, query_text: str, duration_ms: float):
        """异步记录查询"""
        async with self._counter_lock:
            if request_id in self._query_counters:
                self._query_counters[request_id]["count"] += 1
                self._query_counters[request_id]["time"] += duration_ms

    async def _log_model_performance(self, **kwargs):
        """记录模型性能"""
        request = kwargs['request']
        process_time = kwargs['process_time']
        user_id = kwargs['user_id']
        client_ip = kwargs['client_ip']
        request_id = kwargs['request_id']
        trace_id = kwargs['trace_id']
        span_id = kwargs['span_id']
        parent_span_id = kwargs['parent_span_id']
        is_error = kwargs.get('is_error', False)
        db_queries = kwargs.get('db_queries', 0)
        db_time = kwargs.get('db_time', 0)

        # 获取模型ID（从请求体或查询参数中获取）
        model_id = await self._extract_model_id(request)
        model_version = await self._extract_model_version(request)

        # 记录模型性能
        if model_id:
            # 获取模型详细信息（带缓存）
            model_info = await self._get_model_info(model_id)

            if not model_version:
                model_version = model_info.get('version')

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "model_id": model_id,
                    "model_version": model_version,
                    "model_type": model_info.get('type'),
                    "process_time_ms": round(process_time, 2),
                    "path": request.url.path,
                    "method": request.method,
                    "is_error": is_error,
                    "db_queries": db_queries,
                    "db_time_ms": round(db_time, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
        else:
            # 模型推理请求但没有模型ID，记录警告
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "path": request.url.path,
                    "process_time_ms": round(process_time, 2),
                    "warning": "无法获取模型ID",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

    async def _extract_model_id(self, request: Request) -> Optional[str]:
        """从请求中提取模型ID"""
        # 从查询参数获取
        model_id = request.query_params.get('model_id')
        if model_id:
            return model_id

        # 从路径中获取
        path_parts = request.url.path.split('/')
        for i, part in enumerate(path_parts):
            if part in ['scoring', 'fraud', 'model'] and i + 1 < len(path_parts):
                if path_parts[i + 1] != 'predict':
                    return path_parts[i + 1]

        # 从请求体获取
        try:
            body = await request.body()
            if body:
                data = json.loads(body)
                return data.get('model_id')
        except json.JSONDecodeError as e:
            debug_print(
                "PerformanceMiddleware",
                f"解析请求体 JSON 失败: {e}, 路径: {request.url.path}"
            )
        except UnicodeDecodeError as e:
            debug_print(
                "PerformanceMiddleware",
                f"请求体编码错误: {e}, 路径: {request.url.path}"
            )
        except Exception as e:
            debug_print(
                "PerformanceMiddleware",
                f"提取模型ID时发生未知错误: {e}, 路径: {request.url.path}"
            )

        return None

    async def _extract_model_version(self, request: Request) -> Optional[str]:
        """从请求中提取模型版本"""
        # 从查询参数获取
        model_version = request.query_params.get('model_version')
        if model_version:
            return model_version

        # 从请求体获取
        try:
            body = await request.body()
            if body:
                data = json.loads(body)
                return data.get('model_version')
        except json.JSONDecodeError as e:
            debug_print(
                "PerformanceMiddleware",
                f"解析请求体 JSON 失败: {e}, 路径: {request.url.path}"
            )
        except UnicodeDecodeError as e:
            debug_print(
                "PerformanceMiddleware",
                f"请求体编码错误: {e}, 路径: {request.url.path}"
            )
        except Exception as e:
            debug_print(
                "PerformanceMiddleware",
                f"提取模型版本时发生未知错误: {e}, 路径: {request.url.path}"
            )

        return None

    async def _get_model_info(self, model_id: str) -> Dict[str, Any]:
        """获取模型信息（带缓存）"""
        # 检查缓存
        async with self._cache_lock:
            if model_id in self._model_info_cache:
                cached = self._model_info_cache[model_id]
                # 缓存5分钟
                if time.time() - cached['timestamp'] < 300:
                    return cached['info']

        # 从 model_loader 获取
        info = {
            'type': None,
            'version': None,
            'loaded': False
        }

        try:
            if model_loader.is_loaded(model_id):
                model_info = model_loader._loaded_models.get(model_id, {})
                info['loaded'] = True
                info['type'] = model_info.get('metadata', {}).get('model_type')
                info['version'] = model_info.get('metadata', {}).get('model_version')
        except Exception as e:
            debug_print("PerformanceMiddleware", f"获取模型信息失败: {e}")

        # 更新缓存
        async with self._cache_lock:
            self._model_info_cache[model_id] = {
                'info': info,
                'timestamp': time.time()
            }

        return info

    async def get_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        async with self._stats_lock:
            avg_time = self.stats.total_time / self.stats.total_requests if self.stats.total_requests > 0 else 0
            error_rate = self.stats.errors / self.stats.total_requests if self.stats.total_requests > 0 else 0

            return {
                "total_requests": self.stats.total_requests,
                "total_time_ms": round(self.stats.total_time, 2),
                "avg_time_ms": round(avg_time, 2),
                "min_time_ms": round(self.stats.min_time, 2) if self.stats.min_time != float('inf') else 0,
                "max_time_ms": round(self.stats.max_time, 2),
                "errors": self.stats.errors,
                "error_rate": round(error_rate, 4),
                "concurrent_requests": self.concurrent_requests if self.enable_concurrent_tracking else None,
                "by_endpoint": {
                    endpoint: {
                        "count": stats["count"],
                        "avg_time_ms": round(stats["total_time"] / stats["count"], 2),
                        "error_rate": round(stats["errors"] / stats["count"], 4)
                    }
                    for endpoint, stats in self.stats.by_endpoint.items()
                }
            }

    def _start_cleanup_task(self):
        """启动缓存清理任务"""

        async def cleanup():
            while True:
                try:
                    await asyncio.sleep(3600)  # 每小时清理一次
                    async with self._cache_lock:
                        now = time.time()
                        expired = [
                            k for k, v in self._model_info_cache.items()
                            if now - v['timestamp'] > 300
                        ]
                        for k in expired:
                            del self._model_info_cache[k]
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    debug_print("PerformanceMiddleware", f"清理任务异常: {e}")

        task = asyncio.create_task(cleanup())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)


class SlowRequestMiddleware(BaseHTTPMiddleware):
    """
    慢请求监控中间件

    记录处理时间超过阈值的请求，帮助识别性能瓶颈。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[PerformanceConfig] = None,
            slow_threshold: Optional[int] = None,
            log_body: bool = False,
            sanitize_body: bool = True,
            exclude_paths: Optional[List[str]] = None
    ):
        """
        初始化慢请求监控中间件

        参数:
            app: ASGI 应用
            config: 性能监控配置对象
            slow_threshold: 慢请求阈值（毫秒），默认 1000ms
            log_body: 是否记录请求体（可能包含敏感信息）
            sanitize_body: 是否对请求体进行脱敏处理
            exclude_paths: 排除监控的路径列表
        """
        super().__init__(app)

        # 加载配置
        settings = get_settings()
        self.config = config or settings.performance

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.slow_threshold = slow_threshold if slow_threshold is not None else self.config.slow_request_threshold
        self.log_body = log_body
        self.sanitize_body = sanitize_body
        self.exclude_paths = exclude_paths or settings.logging_middleware.log_exclude_paths

        # 敏感字段列表（用于脱敏）
        self.sensitive_fields = settings.sensitive_data.sensitive_fields

    def _should_monitor(self, path: str) -> bool:
        """检查是否应该监控该路径"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return False
        return True

    def _sanitize_body(self, body_str: str) -> str:
        """脱敏处理请求体，移除敏感信息"""
        try:
            # 尝试解析为 JSON
            data = json.loads(body_str)

            def sanitize_dict(obj):
                """递归脱敏字典"""
                if isinstance(obj, dict):
                    result = {}
                    for k, v in obj.items():
                        # 检查是否为敏感字段
                        is_sensitive = any(field in k.lower() for field in self.sensitive_fields)
                        if is_sensitive and v:
                            if isinstance(v, str):
                                result[k] = f"***REDACTED (length: {len(v)})***"
                            else:
                                result[k] = "***REDACTED***"
                        else:
                            result[k] = sanitize_dict(v)
                    return result
                elif isinstance(obj, list):
                    return [sanitize_dict(item) for item in obj]
                return obj

            sanitized = sanitize_dict(data)
            return json.dumps(sanitized, ensure_ascii=False)

        except (json.JSONDecodeError, TypeError):
            # 不是有效的 JSON，使用正则表达式替换
            try:
                result = body_str
                for field in self.sensitive_fields:
                    # 匹配 JSON 格式的键值对
                    pattern = rf'(["\']?{field}["\']?\s*:\s*["\']?)([^"\'}}]+)(["\']?)'
                    replacement = rf'\1***REDACTED***\3'
                    result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

                    # 匹配 URL 编码格式
                    pattern_url = rf'({field}=)([^&]+)'
                    replacement_url = rf'\1***REDACTED***'
                    result = re.sub(pattern_url, replacement_url, result, flags=re.IGNORECASE)

                return result
            except Exception as e:
                debug_print("SlowRequestMiddleware", f"脱敏处理失败: {e}")
                return "<body content (sanitization failed)>"

    async def _safe_read_body(self, request: Request) -> Optional[str]:
        """安全读取请求体"""
        try:
            body = await request.body()
            if not body:
                return None

            # 限制大小
            if len(body) >= 1024:  # 超过1KB不记录
                return f"<body too large: {len(body)} bytes>"

            # 尝试解码
            try:
                body_str = body.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    body_str = body.decode('latin-1')
                except UnicodeDecodeError:
                    return f"<binary data, hex: {body[:100].hex()}>"

            # 脱敏处理
            if self.sanitize_body:
                body_str = self._sanitize_body(body_str)

            return body_str

        except asyncio.CancelledError:
            raise
        except Exception as e:
            debug_print("SlowRequestMiddleware", f"读取请求体失败: {e}")
            return f"<error reading body: {type(e).__name__}>"

    async def dispatch(self, request: Request, call_next):
        # 检查是否应该监控
        if not self._should_monitor(request.url.path):
            return await call_next(request)

        start_time = time.time()
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        trace_id = context.get_trace_id()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000

        if process_time > self.slow_threshold:
            user_id = "anonymous"
            username = "anonymous"
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.get('id', 'unknown')
                username = request.state.user.get('username', 'unknown')

            client_ip = request.client.host if request.client else None

            # 构建详细信息
            details = {
                "method": request.method,
                "path": request.url.path,
                "process_time_ms": round(process_time, 2),
                "threshold_ms": self.slow_threshold,
                "status_code": response.status_code,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "user_agent": request.headers.get("user-agent"),
                "username": username
            }

            # 添加请求体（如果启用）
            if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
                body_content = await self._safe_read_body(request)
                if body_content:
                    details["body"] = body_content

            # 记录慢请求审计日志
            log_audit(
                action=AuditAction.SLOW_REQUEST.value,
                user_id=user_id,
                ip_address=client_ip,
                details=details,
                request_id=request_id
            )

            debug_print(
                "SlowRequestMiddleware",
                f"慢请求: {request.method} {request.url.path} "
                f"用户={username}, 耗时={round(process_time, 2)}ms, 阈值={self.slow_threshold}ms"
            )

        return response


def setup_performance_middleware(
        app: ASGIApp,
        config: Optional[PerformanceConfig] = None,
        **kwargs
) -> None:
    """
    设置性能监控中间件的便捷函数

    参数:
        app: ASGI 应用
        config: 性能监控配置对象
        **kwargs: 其他参数，会传递给 PerformanceMiddleware
    """
    app.add_middleware(PerformanceMiddleware, config=config, **kwargs)
    app.add_middleware(SlowRequestMiddleware, config=config, **kwargs)