# Datamind/datamind/api/middlewares/performance.py

"""性能监控中间件

提供系统性能监控和慢请求检测功能，帮助识别性能瓶颈。

功能特性：
  - CPU 使用率监控：记录请求前后的 CPU 使用率
  - 内存使用监控：记录请求前后的内存占用（MB）
  - 请求处理时间统计：精确到毫秒
  - 模型性能监控：记录模型推理请求的详细指标
  - 慢请求检测：记录超过阈值的慢请求

中间件类型：
  PerformanceMiddleware: 性能监控中间件
     - 记录每个请求的 CPU、内存、耗时
     - 对模型推理请求记录更详细的性能指标
     - 记录性能日志（log_performance）

  SlowRequestMiddleware: 慢请求监控中间件
     - 检测处理时间超过阈值的请求
     - 记录审计日志（log_audit）
     - 可配置慢请求阈值（默认 1000ms）

性能指标：
  - process_time: 请求处理时间（毫秒）
  - cpu_usage: 当前 CPU 使用率（%）
  - memory_usage: 当前内存使用（MB）
  - cpu_delta: CPU 使用率变化
  - memory_delta: 内存使用变化

模型推理性能：
  - 自动识别 /scoring/predict 和 /fraud/predict 路径
  - 获取模型ID和版本
  - 记录模型推理的详细性能指标
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import psutil

from datamind.core.logging import log_manager, debug_print
from datamind.core.logging import context
from datamind.core.ml.model_loader import model_loader


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    性能监控中间件

    记录系统性能指标和模型性能，包括 CPU、内存、请求耗时等。
    """

    def __init__(self, app: ASGIApp, enable_detailed: bool = True):
        """
        初始化性能监控中间件

        参数:
            app: ASGI 应用
            enable_detailed: 是否启用详细监控（包括 CPU/内存详细指标）
        """
        super().__init__(app)
        self.enable_detailed = enable_detailed
        self.process = psutil.Process()

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        request_id = context.get_request_id()
        start_time = time.time()

        # 记录开始时的系统状态
        start_cpu = self.process.cpu_percent() if self.enable_detailed else 0
        start_memory = self.process.memory_info().rss / 1024 / 1024 if self.enable_detailed else 0  # MB

        # 处理请求
        response = await call_next(request)

        # 计算性能指标
        process_time = (time.time() - start_time) * 1000

        # 记录结束时的系统状态
        end_cpu = self.process.cpu_percent() if self.enable_detailed else 0
        end_memory = self.process.memory_info().rss / 1024 / 1024 if self.enable_detailed else 0

        # 记录性能日志
        await self._log_performance(
            request=request,
            response=response,
            process_time=process_time,
            cpu_usage=end_cpu,
            memory_usage=end_memory,
            cpu_delta=end_cpu - start_cpu,
            memory_delta=end_memory - start_memory,
            request_id=request_id
        )

        return response

    async def _log_performance(self, **kwargs):
        """记录性能日志"""
        request = kwargs['request']
        process_time = kwargs['process_time']

        # 构建性能日志参数
        log_params = {
            "operation": f"{request.method} {request.url.path}",
            "duration_ms": process_time,
            "status_code": kwargs['response'].status_code,
            "request_id": kwargs['request_id']
        }

        # 添加详细指标（如果启用）
        if self.enable_detailed:
            log_params.update({
                "cpu_usage": kwargs['cpu_usage'],
                "memory_usage": kwargs['memory_usage'],
                "cpu_delta": kwargs['cpu_delta'],
                "memory_delta": kwargs['memory_delta']
            })

        # 记录性能日志
        log_manager.log_performance(**log_params)

        # 如果是模型推理请求，记录更详细的指标
        if "/scoring/predict" in request.url.path or "/fraud/predict" in request.url.path:
            await self._log_model_performance(**kwargs)

    async def _log_model_performance(self, **kwargs):
        """记录模型性能"""
        request = kwargs['request']

        # 获取模型ID（从请求体或查询参数中获取）
        model_id = request.query_params.get('model_id')

        # 如果没有 model_id，尝试从请求体中获取
        if not model_id and hasattr(request, '_body'):
            try:
                import json
                body = await request.body()
                if body:
                    data = json.loads(body)
                    model_id = data.get('model_id')
            except Exception:
                pass

        if model_id and model_loader.is_loaded(model_id):
            model_info = model_loader._loaded_models.get(model_id, {})

            log_manager.log_performance(
                operation=f"model_inference:{model_id}",
                duration_ms=kwargs['process_time'],
                model_id=model_id,
                model_version=model_info.get('metadata', {}).model_version,
                request_id=kwargs['request_id']
            )


# 慢请求监控中间件
class SlowRequestMiddleware(BaseHTTPMiddleware):
    """
    慢请求监控中间件

    记录处理时间超过阈值的请求，帮助识别性能瓶颈。
    """

    def __init__(self, app: ASGIApp, slow_threshold: int = 1000):
        """
        初始化慢请求监控中间件

        参数:
            app: ASGI 应用
            slow_threshold: 慢请求阈值（毫秒），默认 1000ms
        """
        super().__init__(app)
        self.slow_threshold = slow_threshold  # 毫秒

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000

        if process_time > self.slow_threshold:
            request_id = context.get_request_id()

            user_id = "anonymous"
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.get('id', 'unknown')

            client_ip = request.client.host if request.client else None

            log_manager.log_audit(
                action="SLOW_REQUEST",
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time, 2),
                    "threshold_ms": self.slow_threshold
                },
                request_id=request_id
            )

        return response