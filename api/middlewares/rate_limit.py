# datamind/api/middlewares/rate_limit.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from typing import Dict, Tuple, Optional
from collections import defaultdict
import asyncio
import redis.asyncio as redis
from datetime import datetime, timedelta

from core.logging import log_manager, get_request_id
from config.settings import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件

    支持基于IP、用户ID、API Key的限流
    支持Redis分布式限流
    """

    def __init__(
            self,
            app: ASGIApp,
            redis_client: Optional[redis.Redis] = None,
            default_limit: int = 100,
            default_period: int = 60,
            exclude_paths: Optional[list] = None,
            use_redis: bool = True
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.default_limit = default_limit or settings.RATE_LIMIT_REQUESTS
        self.default_period = default_period or settings.RATE_LIMIT_PERIOD
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/static",
            "/favicon.ico",
            "/ui"
        ]
        self.use_redis = use_redis and redis_client is not None

        # 内存存储（用于单机限流）
        self.memory_storage: Dict[str, list] = defaultdict(list)

        # 限流规则
        self.rules = {
            "default": {"limit": self.default_limit, "period": self.default_period},
            "admin": {"limit": 1000, "period": 60},
            "premium": {"limit": 500, "period": 60},
            "anonymous": {"limit": 50, "period": 60}
        }

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 检查是否排除限流
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # 获取限流key
        key = await self._get_rate_limit_key(request)

        # 获取用户等级
        tier = await self._get_user_tier(request)

        # 获取限流规则
        rule = self.rules.get(tier, self.rules["default"])

        # 检查是否超过限制
        if await self._is_rate_limited(key, rule):
            # 记录限流事件
            request_id = get_request_id()
            log_manager.log_audit(
                action="RATE_LIMIT_EXCEEDED",
                user_id=request.state.user.get('id', 'anonymous') if hasattr(request.state, 'user') else 'anonymous',
                ip_address=request.client.host if request.client else None,
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "tier": tier,
                    "limit": rule['limit'],
                    "period": rule['period']
                },
                request_id=request_id
            )

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "请求过于频繁",
                    "limit": rule['limit'],
                    "period": rule['period'],
                    "message": f"每{rule['period']}秒最多允许{rule['limit']}次请求"
                }
            )

        # 记录请求
        await self._record_request(key, rule)

        # 处理请求
        response = await call_next(request)

        # 添加限流头信息
        remaining = await self._get_remaining_requests(key, rule)
        response.headers["X-RateLimit-Limit"] = str(rule['limit'])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + rule['period']))

        return response

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除限流"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    async def _get_rate_limit_key(self, request: Request) -> str:
        """获取限流key"""
        # 优先级: 用户ID > API Key > IP
        if hasattr(request.state, 'user') and request.state.user.get('id'):
            return f"user:{request.state.user['id']}"

        api_key = request.headers.get(settings.API_KEY_HEADER)
        if api_key:
            return f"apikey:{api_key}"

        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def _get_user_tier(self, request: Request) -> str:
        """获取用户等级"""
        if hasattr(request.state, 'user'):
            roles = request.state.user.get('roles', [])
            if 'admin' in roles:
                return "admin"
            if 'premium' in roles:
                return "premium"

        api_key = request.headers.get(settings.API_KEY_HEADER)
        if api_key:
            # TODO: 根据API Key获取用户等级
            pass

        return "anonymous"

    async def _is_rate_limited(self, key: str, rule: Dict) -> bool:
        """检查是否超过限流"""
        if self.use_redis:
            return await self._check_redis_rate_limit(key, rule)
        else:
            return self._check_memory_rate_limit(key, rule)

    async def _check_redis_rate_limit(self, key: str, rule: Dict) -> bool:
        """使用Redis检查限流"""
        redis_key = f"rate_limit:{key}"
        now = time.time()
        window_start = now - rule['period']

        async with self.redis_client.pipeline() as pipe:
            # 移除窗口外的请求
            await pipe.zremrangebyscore(redis_key, 0, window_start)
            # 获取当前窗口内的请求数
            await pipe.zcard(redis_key)
            # 添加当前请求
            await pipe.zadd(redis_key, {str(now): now})
            # 设置过期时间
            await pipe.expire(redis_key, rule['period'])

            results = await pipe.execute()
            count = results[1]

        return count >= rule['limit']

    def _check_memory_rate_limit(self, key: str, rule: Dict) -> bool:
        """使用内存检查限流"""
        now = time.time()
        window_start = now - rule['period']

        # 清理过期记录
        self.memory_storage[key] = [
            t for t in self.memory_storage[key]
            if t > window_start
        ]

        # 检查是否超过限制
        if len(self.memory_storage[key]) >= rule['limit']:
            return True

        # 记录当前请求
        self.memory_storage[key].append(now)
        return False

    async def _record_request(self, key: str, rule: Dict):
        """记录请求"""
        # 已经在检查限流时记录了，这里可以添加额外的统计逻辑
        pass

    async def _get_remaining_requests(self, key: str, rule: Dict) -> int:
        """获取剩余请求数"""
        if self.use_redis:
            redis_key = f"rate_limit:{key}"
            now = time.time()
            window_start = now - rule['period']

            count = await self.redis_client.zcount(redis_key, window_start, now)
            return max(0, rule['limit'] - count)
        else:
            now = time.time()
            window_start = now - rule['period']
            count = len([t for t in self.memory_storage[key] if t > window_start])
            return max(0, rule['limit'] - count)


# IP限流中间件（简化版）
class IPRateLimitMiddleware(RateLimitMiddleware):
    """基于IP的限流中间件"""

    async def _get_rate_limit_key(self, request: Request) -> str:
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"


# 用户限流中间件
class UserRateLimitMiddleware(RateLimitMiddleware):
    """基于用户的限流中间件"""

    async def _get_rate_limit_key(self, request: Request) -> str:
        if hasattr(request.state, 'user') and request.state.user.get('id'):
            return f"user:{request.state.user['id']}"
        return await super()._get_rate_limit_key(request)