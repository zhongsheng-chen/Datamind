# Datamind/datamind/api/middlewares/performance.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import psutil

from datamind.core import log_manager, get_request_id
from datamind.core.ml.model_loader import model_loader


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    性能监控中间件

    记录系统性能指标和模型性能
    """

    def __init__(self, app: ASGIApp, enable_detailed: bool = True):
        super().__init__(app)
        self.enable_detailed = enable_detailed
        self.process = psutil.Process()

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        request_id = get_request_id()
        start_time = time.time()

        # 记录开始时的系统状态
        start_cpu = self.process.cpu_percent()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        # 处理请求
        response = await call_next(request)

        # 计算性能指标
        process_time = (time.time() - start_time) * 1000

        # 记录结束时的系统状态
        end_cpu = self.process.cpu_percent()
        end_memory = self.process.memory_info().rss / 1024 / 1024

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

        # 使用log_manager记录性能日志
        log_manager.log_performance(
            operation=f"{request.method} {request.url.path}",
            duration_ms=kwargs['process_time'],
            cpu_usage=kwargs['cpu_usage'],
            memory_usage=kwargs['memory_usage'],
            cpu_delta=kwargs['cpu_delta'],
            memory_delta=kwargs['memory_delta'],
            status_code=kwargs['response'].status_code,
            request_id=kwargs['request_id']
        )

        # 如果是模型推理请求，记录更详细的指标
        if "/scoring/predict" in request.url.path or "/fraud/predict" in request.url.path:
            await self._log_model_performance(**kwargs)

    async def _log_model_performance(self, **kwargs):
        """记录模型性能"""
        request = kwargs['request']

        # 获取模型ID
        model_id = request.query_params.get('model_id')
        if not model_id and hasattr(request.state, 'user'):
            # TODO: 从AB测试获取模型ID
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

    记录处理时间超过阈值的请求
    """

    def __init__(self, app: ASGIApp, slow_threshold: int = 1000):
        super().__init__(app)
        self.slow_threshold = slow_threshold  # 毫秒

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000

        if process_time > self.slow_threshold:
            request_id = get_request_id()

            log_manager.log_audit(
                action="SLOW_REQUEST",
                user_id=request.state.user.get('id', 'anonymous') if hasattr(request.state, 'user') else 'anonymous',
                ip_address=request.client.host if request.client else None,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time, 2),
                    "threshold_ms": self.slow_threshold
                },
                request_id=request_id
            )

        return response