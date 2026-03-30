# datamind/api/middlewares/rate_limit.py

"""限流中间件

提供 API 限流功能，防止滥用和保护系统资源。

功能特性：
  - 多维度限流：支持基于 IP、用户ID、API Key 的限流
  - 分布式限流：支持 Redis 存储，适用于多实例部署
  - 单机限流：内存存储，适用于单实例部署
  - 多等级限流：根据用户等级（admin/developer/analyst/api_user）应用不同规则
  - 限流头信息：返回 X-RateLimit-* 头信息供客户端参考
  - 审计日志：记录限流触发事件
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

限流规则：
  - default: 默认限流（100次/60秒）
  - admin: 管理员限流（1000次/60秒）
  - developer: 开发者限流（500次/60秒）
  - analyst: 分析师限流（200次/60秒）
  - api_user: API用户限流（100次/60秒）
  - anonymous: 匿名用户限流（50次/60秒）

限流维度优先级：
  - 用户ID（已认证用户）
  - API Key
  - 客户端 IP
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

import redis.asyncio as redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import UserStatus, UserRole
from datamind.core.domain.enums import AuditAction
from datamind.config import get_settings
from datamind.config.settings import RateLimitConfig

# 原子性限流检查
RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local period = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- 移除窗口外的请求
redis.call('ZREMRANGEBYSCORE', key, 0, now - period)

-- 获取当前窗口内的请求数
local count = redis.call('ZCARD', key)

-- 检查是否超过限制
if count < limit then
    -- 添加当前请求
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, period)
    -- 计算剩余请求数，确保不为负数
    local remaining = limit - count - 1
    if remaining < 0 then
        remaining = 0
    end
    return {0, remaining}
end

-- 返回超限状态和剩余请求数（0）
return {1, 0}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件
    """

    def __init__(
            self,
            app: ASGIApp,
            redis_client: Optional[redis.Redis] = None,
            config: Optional[RateLimitConfig] = None,
            default_limit: Optional[int] = None,
            default_period: Optional[int] = None,
            exclude_paths: Optional[List[str]] = None,
            use_redis: bool = True,
            enabled: Optional[bool] = None,
    ):
        """
        初始化限流中间件

        参数:
            app: ASGI 应用
            redis_client: Redis 客户端（用于分布式限流）
            config: 速率限制配置对象
            default_limit: 默认限流次数
            default_period: 默认限流周期（秒）
            exclude_paths: 排除限流的路径列表
            use_redis: 是否使用 Redis（False 则使用内存存储）
            enabled: 是否启用限流（可覆盖配置）
        """
        super().__init__(app)
        settings = get_settings()

        # 加载配置
        self.config = config or settings.rate_limit

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.default_limit = default_limit if default_limit is not None else self.config.rate_limit_default_limit
        self.default_period = default_period if default_period is not None else self.config.rate_limit_default_period
        self.redis_client = redis_client

        if exclude_paths is not None:
            self.exclude_paths = exclude_paths
        else:
            self.exclude_paths = settings.logging_middleware.log_exclude_paths

        self.use_redis = use_redis and redis_client is not None

        # 优先使用传入的 enabled 参数
        if enabled is not None:
            self.rate_limit_enabled = enabled
        else:
            self.rate_limit_enabled = self.config.rate_limit_enabled

        # 有效角色列表（从枚举获取）
        self._valid_roles = [role.value for role in UserRole]

        # 限流规则中的角色（字符串值）
        self._rate_limit_roles = ['admin', 'developer', 'analyst', 'api_user', 'anonymous', 'default']

        # 内存存储（用于单机限流）
        self.memory_storage: Dict[str, List[float]] = defaultdict(list)
        self._memory_lock = asyncio.Lock()

        # API Key 缓存
        self._api_key_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()

        # 从配置读取限流规则
        self.rules = self._load_rate_limit_rules()

        # 确保所有角色都在限流规则中
        self._ensure_roles_in_rules()

        # 注册 Lua 脚本
        self._rate_limit_script = None
        if self.use_redis and self.rate_limit_enabled:
            self._rate_limit_script = self.redis_client.register_script(RATE_LIMIT_LUA_SCRIPT)

        # 启动清理任务（仅内存模式）
        if not self.use_redis and self.rate_limit_enabled:
            asyncio.create_task(self._periodic_cleanup())

        # 调试打印
        debug_print("RateLimitMiddleware",
                    f"INIT: default_limit={self.default_limit}, default_period={self.default_period}")
        debug_print("RateLimitMiddleware",
                    f"INIT: rules['default']={self.rules.get('default', {})}")

    def _ensure_roles_in_rules(self) -> None:
        """确保所有角色都在限流规则中"""
        for role in self._rate_limit_roles:
            if role not in self.rules:
                self.rules[role] = {
                    "limit": self.default_limit,
                    "period": self.default_period
                }

    def _load_rate_limit_rules(self) -> Dict[str, Dict[str, int]]:
        """从配置加载限流规则"""
        return {
            "default": {
                "limit": self.default_limit,
                "period": self.default_period
            },
            "admin": {
                "limit": self.config.rate_limit_admin_limit,
                "period": self.config.rate_limit_admin_period
            },
            "developer": {
                "limit": self.config.rate_limit_developer_limit,
                "period": self.config.rate_limit_developer_period
            },
            "analyst": {
                "limit": self.config.rate_limit_analyst_limit,
                "period": self.config.rate_limit_analyst_period
            },
            "api_user": {
                "limit": self.config.rate_limit_api_user_limit,
                "period": self.config.rate_limit_api_user_period
            },
            "anonymous": {
                "limit": self.default_limit,
                "period": self.default_period
            }
        }

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 如果未启用限流，直接放行
        if not self.rate_limit_enabled:
            return await call_next(request)
        debug_print("RateLimitMiddleware", f"限流检查开始: {request.method} {request.url.path}")

        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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
        is_limited, remaining = await self._check_rate_limit(key, rule)

        if is_limited:
            # 获取用户信息
            user_id = "anonymous"
            username = "anonymous"
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.get('id', 'anonymous')
                username = request.state.user.get('username', 'anonymous')

            client_ip = self._get_client_ip(request)

            # 记录限流事件
            log_audit(
                action=AuditAction.RATE_LIMIT_EXCEEDED.value,
                user_id=user_id,
                ip_address=client_ip,
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "username": username,
                    "tier": tier,
                    "limit": rule['limit'],
                    "period": rule['period'],
                    "key_type": key.split(':')[0] if ':' in key else 'unknown',
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print(
                "RateLimitMiddleware",
                f"限流触发: {request.method} {request.url.path}, "
                f"用户={username}, 等级={tier}, 限制={rule['limit']}/{rule['period']}秒"
            )

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "请求过于频繁",
                    "limit": rule['limit'],
                    "period": rule['period'],
                    "remaining": 0,
                    "message": f"每{rule['period']}秒最多允许{rule['limit']}次请求"
                }
            )

        # 处理请求
        response = await call_next(request)

        # 添加限流头信息
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
        """获取限流key

        优先级: 用户ID > API Key > IP
        """
        # 用户ID
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id')
            if user_id:
                return f"user:{user_id}"

        # API Key
        settings = get_settings()
        api_key = request.headers.get(settings.auth.api_key_header)
        if api_key:
            # 只取前16位作为key，避免key过长
            return f"apikey:{api_key[:16]}"

        # IP 地址（考虑代理情况）
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # 取第一个IP（客户端真实IP）
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else "unknown"

    async def _get_user_tier(self, request: Request) -> str:
        """获取用户等级

        根据用户角色返回对应的限流等级：
            - admin: 管理员
            - developer: 开发者
            - analyst: 分析师
            - api_user: API用户
            - anonymous: 匿名用户
        """
        # 优先从 request.state 获取已缓存的等级
        if hasattr(request.state, 'user_tier'):
            return request.state.user_tier

        # 已认证用户
        if hasattr(request.state, 'user') and request.state.user:
            role = request.state.user.get('strategy')
            # 验证角色是否有效
            if role and role in self._valid_roles:
                # 检查角色是否在限流规则中
                if role in self.rules:
                    request.state.user_tier = role
                    return role

            # 如果有 roles 列表，取第一个有效角色
            roles = request.state.user.get('roles', [])
            for role in roles:
                if role in self._valid_roles and role in self.rules:
                    request.state.user_tier = role
                    return role

            request.state.user_tier = "anonymous"
            return "anonymous"

        # API Key 用户（未通过认证中间件，但可能通过 API Key 调用）
        tier = await self._get_tier_from_api_key(request)
        if tier:
            request.state.user_tier = tier
            return tier

        request.state.user_tier = "anonymous"
        return "anonymous"

    async def _get_tier_from_api_key(self, request: Request) -> Optional[str]:
        """从 API Key 获取用户等级（带缓存）"""
        settings = get_settings()
        api_key = request.headers.get(settings.auth.api_key_header)
        if not api_key:
            return None

        # 检查缓存
        cache_key = f"apikey:{api_key[:16]}"
        async with self._cache_lock:
            if cache_key in self._api_key_cache:
                cached_data = self._api_key_cache[cache_key]
                # 缓存5分钟
                if time.time() - cached_data['timestamp'] < 300:
                    tier = cached_data.get('tier')
                    # 验证缓存的等级是否有效
                    if tier in self._valid_roles or tier == 'anonymous':
                        return tier

        try:
            # 异步查询数据库
            from datamind.core.db.database import get_db
            from datamind.core.db.models import ApiKey, User

            # 使用线程池执行同步数据库查询
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sync_query_api_key,
                api_key
            )

            if result:
                tier = result.get('tier', 'api_user')
                # 验证等级是否有效
                if tier in self._valid_roles:
                    # 更新缓存
                    async with self._cache_lock:
                        self._api_key_cache[cache_key] = {
                            'tier': tier,
                            'timestamp': time.time()
                        }
                    return tier

        except Exception as e:
            debug_print("RateLimitMiddleware", f"获取API Key用户等级失败: {e}")

        return "api_user"

    def _sync_query_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """同步查询API Key信息"""
        try:
            from datamind.core.db.database import get_db
            from datamind.core.db.models import ApiKey, User

            with next(get_db()) as session:
                # 查询 API Key
                api_key_record = session.query(ApiKey).filter_by(
                    key=api_key,
                    is_active=True
                ).first()

                if api_key_record and api_key_record.is_valid():
                    # 获取关联用户
                    user = session.query(User).filter_by(
                        user_id=api_key_record.user_id,
                        status=UserStatus.ACTIVE
                    ).first()

                    if user:
                        # 优先使用 API Key 的角色
                        if api_key_record.roles:
                            role = api_key_record.roles[0]
                            # 验证角色是否有效
                            if role in self._valid_roles and role in self.rules:
                                return {'tier': role}

                        # 否则使用用户的角色
                        user_role = user.role.value
                        if user_role in self._valid_roles and user_role in self.rules:
                            return {'tier': user_role}

            return None
        except Exception as e:
            debug_print("RateLimitMiddleware", f"同步查询API Key失败: {e}")
            return None

    async def _check_rate_limit(self, key: str, rule: Dict[str, int]) -> Tuple[bool, int]:
        """检查是否超过限流

        返回: (是否被限流, 剩余请求数)
        """
        if self.use_redis:
            return await self._check_redis_rate_limit(key, rule)
        else:
            return await self._check_memory_rate_limit(key, rule)

    async def _check_redis_rate_limit(self, key: str, rule: Dict[str, int]) -> Tuple[bool, int]:
        """使用Redis检查限流（原子操作）"""
        redis_key = f"rate_limit:{key}"
        now = time.time()

        try:
            # 使用 Lua 脚本保证原子性
            result = await self._rate_limit_script(
                keys=[redis_key],
                args=[rule['limit'], rule['period'], now]
            )

            is_limited = result[0] == 1
            remaining = result[1]

            return is_limited, remaining

        except Exception as e:
            debug_print("RateLimitMiddleware", f"Redis限流检查失败: {e}")
            # Redis 故障时降级到内存限流
            return await self._check_memory_rate_limit(key, rule)

    async def _check_memory_rate_limit(self, key: str, rule: Dict[str, int]) -> Tuple[bool, int]:
        """使用内存检查限流（线程安全）"""
        async with self._memory_lock:
            now = time.time()
            window_start = now - rule['period']

            # 清理过期记录
            before_count = len(self.memory_storage[key])
            self.memory_storage[key] = [
                t for t in self.memory_storage[key]
                if t > window_start
            ]
            after_count = len(self.memory_storage[key])

            current_count = len(self.memory_storage[key])

            # 调试输出
            debug_print(
                "RateLimitMiddleware",
                f"限流检查: key={key}, limit={rule['limit']}, period={rule['period']}, "
                f"current={current_count}, before_cleanup={before_count}, after_cleanup={after_count}"
            )

            # 检查是否超过限制
            if current_count >= rule['limit']:
                debug_print("RateLimitMiddleware", f"限流触发: current={current_count} >= limit={rule['limit']}")
                return True, 0

            # 记录当前请求
            self.memory_storage[key].append(now)
            remaining = rule['limit'] - current_count - 1
            if remaining < 0:
                remaining = 0

            debug_print("RateLimitMiddleware",
                        f"请求记录: key={key}, new_count={current_count + 1}, remaining={remaining}")

            return False, remaining

    async def _periodic_cleanup(self):
        """定期清理内存存储（防止内存泄漏）"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时清理一次
                async with self._memory_lock:
                    now = time.time()
                    expired_keys = []

                    for key, timestamps in self.memory_storage.items():
                        # 清理超过1小时的记录
                        valid_timestamps = [t for t in timestamps if t > now - 3600]
                        if valid_timestamps:
                            self.memory_storage[key] = valid_timestamps
                        else:
                            expired_keys.append(key)

                    # 删除空key
                    for key in expired_keys:
                        del self.memory_storage[key]

                    # 清理API Key缓存
                    async with self._cache_lock:
                        expired_cache_keys = [
                            k for k, v in self._api_key_cache.items()
                            if time.time() - v['timestamp'] > 300
                        ]
                        for key in expired_cache_keys:
                            del self._api_key_cache[key]

            except asyncio.CancelledError:
                break
            except Exception as e:
                debug_print("RateLimitMiddleware", f"清理任务异常: {e}")

    async def get_current_usage(self, request: Request) -> Dict[str, Any]:
        """获取当前请求使用情况（用于监控）"""
        key = await self._get_rate_limit_key(request)
        tier = await self._get_user_tier(request)
        rule = self.rules.get(tier, self.rules["default"])
        now = time.time()
        window_start = now - rule['period']

        if self.use_redis:
            redis_key = f"rate_limit:{key}"
            count = await self.redis_client.zcount(redis_key, window_start, now)
            remaining = max(0, rule['limit'] - count)
        else:
            async with self._memory_lock:
                count = len([t for t in self.memory_storage[key] if t > window_start])
                remaining = max(0, rule['limit'] - count)

        return {
            "key": key,
            "tier": tier,
            "limit": rule['limit'],
            "period": rule['period'],
            "current": count,
            "remaining": remaining,
            "reset_in": rule['period'] - (now - window_start) if count > 0 else rule['period']
        }


def setup_rate_limit_middleware(
        app: ASGIApp,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[RateLimitConfig] = None,
        enabled: Optional[bool] = None,
        **kwargs
) -> None:
    """
    设置限流中间件的便捷函数

    参数:
        app: ASGI 应用
        redis_client: Redis 客户端
        config: 速率限制配置对象
        enabled: 是否启用限流
        **kwargs: 其他参数，会传递给 RateLimitMiddleware
    """
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        config=config,
        enabled=enabled,
        **kwargs
    )


# IP限流中间件
class IPRateLimitMiddleware(RateLimitMiddleware):
    """基于IP的限流中间件

    只根据客户端 IP 进行限流，适用于无需用户认证的场景。
    """

    async def _get_rate_limit_key(self, request: Request) -> str:
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"


# 用户限流中间件
class UserRateLimitMiddleware(RateLimitMiddleware):
    """基于用户的限流中间件

    优先使用用户ID进行限流，无用户时降级到 IP 限流。
    """

    async def _get_rate_limit_key(self, request: Request) -> str:
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('id')
            if user_id:
                return f"user:{user_id}"
        return await super()._get_rate_limit_key(request)