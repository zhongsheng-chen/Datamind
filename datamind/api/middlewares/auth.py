# datamind/api/middlewares/auth.py

"""认证中间件

提供 JWT token 和 API Key 的认证功能，保护 API 端点安全。

功能特性：
  - 多种认证方式：JWT Bearer Token、API Key、Basic Auth
  - 路径排除：支持排除公开路径和健康检查路径
  - JWT 工具函数：创建和验证 JWT token
  - 审计日志：记录所有认证成功和失败事件
  - 链路追踪：完整的 span 追踪

认证方式优先级：
  - Bearer Token (JWT) - 最优先，适用于用户登录后的请求
  - API Key - 适用于服务间调用
  - Basic Auth - 适用于简单场景

中间件行为：
  - 排除路径（exclude_paths）：不需要认证的路径（如 /health、/docs）
  - 公开路径（public_paths）：公开 API 路径（如 /auth/login）
  - 认证成功：将用户信息存入 request.state.user
  - 认证失败：返回 401 状态码

JWT Token 结构：
  {
    "sub": "user_id",           # 用户ID
    "username": "username",     # 用户名
    "roles": ["admin"],         # 角色列表
    "permissions": ["read"],    # 权限列表
    "iat": 1234567890,          # 签发时间
    "exp": 1234567890           # 过期时间
  }

API Key 验证：
  - 从请求头 X-API-Key 获取
  - 支持从数据库验证
  - 支持 IP 白名单、过期时间检查
"""

import jwt
import time
import base64
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import UserStatus, UserRole
from datamind.config import get_settings

logger = get_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    认证中间件

    处理 JWT token 验证和 API 密钥认证。
    认证成功后，用户信息存储在 request.state.user 中。
    """

    def __init__(
            self,
            app: ASGIApp,
            exclude_paths: Optional[List[str]] = None,
            public_paths: Optional[List[str]] = None
    ):
        """
        初始化认证中间件

        参数:
            app: ASGI 应用
            exclude_paths: 完全排除认证的路径（如健康检查）
            public_paths: 公开 API 路径（如登录接口）
        """
        super().__init__(app)
        self.settings = get_settings()

        # 使用配置或默认值
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/ui",
            "/static",
            "/favicon.ico"
        ]

        self.public_paths = public_paths or [
            f"{self.settings.api.prefix}/auth/login",
            f"{self.settings.api.prefix}/auth/register",
            f"{self.settings.api.prefix}/auth/refresh",
            f"{self.settings.api.prefix}/auth/forgot-password",
            f"{self.settings.api.prefix}/auth/reset-password"
        ]

        self.security = HTTPBearer(auto_error=False)

        # 缓存有效角色列表
        self._valid_roles = [r.value for r in UserRole]

        logger.info("认证中间件初始化完成，排除路径数=%d，公开路径数=%d",
                   len(self.exclude_paths), len(self.public_paths))

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # OPTIONS 请求不需要认证
        if request.method == "OPTIONS":
            return await call_next(request)

        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        # 检查是否为排除路径
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        # 获取认证信息
        auth_result = await self._authenticate(request)

        if not auth_result['authenticated']:
            # 记录认证失败
            duration = (time.time() - start_time) * 1000
            log_audit(
                action="AUTH_FAILED",
                user_id="anonymous",
                ip_address=self._get_client_ip(request),
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "reason": auth_result['reason'],
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "user_agent": request.headers.get("user-agent")
                },
                request_id=request_id
            )
            logger.warning("认证失败: 路径=%s, 原因=%s, 客户端IP=%s",
                          request.url.path, auth_result['reason'], self._get_client_ip(request))

            raise HTTPException(
                status_code=401,
                detail=auth_result['reason']
            )

        # 将用户信息添加到request.state
        user_info = auth_result['user']
        request.state.user = user_info
        request.state.token = auth_result.get('token')
        request.state.auth_type = auth_result.get('auth_type')
        request.state.user_id = user_info.get('id')
        request.state.username = user_info.get('username')
        request.state.role = user_info.get('strategy')
        request.state.roles = user_info.get('roles', [])
        request.state.permissions = user_info.get('permissions', [])

        # 记录认证成功
        duration = (time.time() - start_time) * 1000
        log_audit(
            action="AUTH_SUCCESS",
            user_id=user_info.get('id', 'unknown'),
            ip_address=self._get_client_ip(request),
            details={
                "path": request.url.path,
                "method": request.method,
                "auth_type": auth_result['auth_type'],
                "username": user_info.get('username'),
                "strategy": user_info.get('strategy'),
                "duration_ms": round(duration, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        logger.info("认证成功: 用户=%s, 认证方式=%s, 路径=%s",
                   user_info.get('username'), auth_result.get('auth_type'), request.url.path)

        response = await call_next(request)
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    def _is_excluded_path(self, path: str) -> bool:
        """检查是否为排除路径"""
        # 检查完全匹配
        if path in self.exclude_paths:
            return True

        # 检查前缀匹配
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True

        # 检查公开路径
        for public_path in self.public_paths:
            if path.startswith(public_path):
                return True

        return False

    async def _authenticate(self, request: Request) -> Dict[str, Any]:
        """
        认证请求

        支持多种认证方式:
          - Bearer Token (JWT)
          - API Key
          - Basic Auth

        返回:
            字典包含 authenticated, reason, user, auth_type
        """
        # 获取认证头
        auth_header = request.headers.get("Authorization")
        api_key = request.headers.get(self.settings.auth.api_key_header)

        result = {
            'authenticated': False,
            'reason': None,
            'user': None,
            'auth_type': None,
            'token': None
        }

        # 尝试Bearer Token认证（JWT）
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            auth_result = await self._verify_jwt_token(token, request)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'jwt'
                result['token'] = token
                return result

        # 尝试API Key认证
        if api_key and self.settings.auth.api_key_enabled:
            auth_result = await self._verify_api_key(api_key, request)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'api_key'
                result['token'] = api_key
                return result

        # 尝试Basic Auth
        if auth_header and auth_header.startswith("Basic "):
            auth_result = await self._verify_basic_auth(auth_header, request)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'basic'
                return result

        # 所有认证方式都失败
        result['reason'] = "未提供有效的认证信息"
        return result

    async def _verify_jwt_token(self, token: str, request: Request) -> Dict[str, Any]:
        """验证JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.settings.auth.jwt_secret_key,
                algorithms=[self.settings.auth.jwt_algorithm]
            )

            # 检查token是否过期
            exp = payload.get('exp')
            if exp and isinstance(exp, (int, float)):
                if datetime.fromtimestamp(exp) < datetime.now():
                    return {
                        'authenticated': False,
                        'reason': "Token已过期"
                    }

            # 获取角色信息
            roles = payload.get('roles', [])
            # 过滤出有效的角色
            valid_roles = [r for r in roles if r in self._valid_roles]
            role = valid_roles[0] if valid_roles else UserRole.API_USER.value

            # 获取权限信息
            permissions = payload.get('permissions', [])

            logger.debug("JWT认证成功: 用户=%s", payload.get('username'))

            return {
                'authenticated': True,
                'user': {
                    'id': payload.get('sub'),
                    'username': payload.get('username'),
                    'strategy': role,
                    'roles': valid_roles,
                    'permissions': permissions,
                    'email': payload.get('email'),
                    'full_name': payload.get('full_name')
                }
            }

        except jwt.ExpiredSignatureError:
            logger.warning("JWT认证失败: Token已过期")
            return {
                'authenticated': False,
                'reason': "Token已过期"
            }
        except jwt.InvalidTokenError as e:
            logger.warning("JWT认证失败: 无效Token, 错误=%s", e)
            return {
                'authenticated': False,
                'reason': f"无效的Token: {str(e)}"
            }

    async def _verify_api_key(self, api_key: str, request: Request) -> Dict[str, Any]:
        """验证API Key"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        client_ip = self._get_client_ip(request)

        try:
            from datamind.core.db.database import get_db
            from datamind.core.db.models import ApiKey, User

            # 使用异步数据库驱动或在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sync_verify_api_key,
                api_key, client_ip, request_id, trace_id, span_id, parent_span_id
            )
            return result

        except ImportError as e:
            logger.warning("API Key验证模块导入失败: %s", e)
            # 降级到简化验证
            return await self._verify_api_key_fallback(api_key, request)
        except Exception as e:
            logger.error("API Key验证失败: %s", e)
            return {
                'authenticated': False,
                'reason': "API Key验证失败"
            }

    def _sync_verify_api_key(
            self,
            api_key: str,
            client_ip: Optional[str],
            request_id: str,
            trace_id: str,
            span_id: str,
            parent_span_id: str
    ) -> Dict[str, Any]:
        """同步验证API Key（在线程池中执行）"""
        from datamind.core.db.database import get_db
        from datamind.core.db.models import ApiKey, User
        from datamind.core.domain.enums import AuditAction

        with next(get_db()) as session:
            # 查找API密钥
            api_key_record = session.query(ApiKey).filter_by(
                key=api_key,
                is_active=True
            ).first()

            if not api_key_record:
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id="unknown",
                    ip_address=client_ip,
                    details={
                        "api_key_prefix": api_key[:8] + "...",
                        "reason": "API密钥不存在或已禁用",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("API Key认证失败: API密钥不存在或已禁用, 前缀=%s", api_key[:8])
                return {
                    'authenticated': False,
                    'reason': "无效的API Key"
                }

            # 检查API密钥是否有效
            if not api_key_record.is_valid():
                reason = "API密钥已过期" if api_key_record.expires_at else "API密钥已禁用"
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id=api_key_record.user_id,
                    ip_address=client_ip,
                    details={
                        "api_key_id": api_key_record.api_key_id,
                        "reason": reason,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("API Key认证失败: %s, 密钥ID=%s", reason, api_key_record.api_key_id)
                return {
                    'authenticated': False,
                    'reason': reason
                }

            # 获取关联的用户
            user = session.query(User).filter_by(
                user_id=api_key_record.user_id,
                status=UserStatus.ACTIVE
            ).first()

            if not user or not user.is_active:
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id=api_key_record.user_id,
                    ip_address=client_ip,
                    details={
                        "api_key_id": api_key_record.api_key_id,
                        "reason": "关联用户不可用",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("API Key认证失败: 关联用户不可用, 用户ID=%s", api_key_record.user_id)
                return {
                    'authenticated': False,
                    'reason': "API Key无效"
                }

            # 检查IP白名单
            if api_key_record.allowed_ips and client_ip:
                if client_ip not in api_key_record.allowed_ips:
                    log_audit(
                        action=AuditAction.IP_BLOCKED.value,
                        user_id=user.user_id,
                        ip_address=client_ip,
                        details={
                            "api_key_id": api_key_record.api_key_id,
                            "allowed_ips": api_key_record.allowed_ips,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )
                    logger.warning("API Key认证失败: IP不在白名单中, IP=%s, 允许IP=%s",
                                  client_ip, api_key_record.allowed_ips)
                    return {
                        'authenticated': False,
                        'reason': "IP地址不在白名单中"
                    }

            # 更新最后使用时间
            api_key_record.update_last_used()
            session.commit()

            log_audit(
                action=AuditAction.AUTH_SUCCESS.value,
                user_id=user.user_id,
                ip_address=client_ip,
                details={
                    "api_key_id": api_key_record.api_key_id,
                    "api_key_name": api_key_record.name,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            # 获取角色信息
            # 优先使用 API Key 的角色
            if api_key_record.roles:
                roles = [r for r in api_key_record.roles if r in self._valid_roles]
            else:
                roles = [user.role.value]

            # 确保至少有一个有效角色
            if not roles:
                roles = [UserRole.API_USER.value]

            role = roles[0]

            # 获取权限信息
            permissions = api_key_record.permissions or user.permissions or []

            # 构建用户信息
            user_info = {
                'id': user.user_id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'strategy': role,
                'roles': roles,
                'permissions': permissions,
                'api_key_id': api_key_record.api_key_id,
                'api_key_name': api_key_record.name,
            }

            logger.info("API Key认证成功: 用户=%s, 密钥名称=%s", user.username, api_key_record.name)

            return {
                'authenticated': True,
                'user': user_info
            }

    async def _verify_api_key_fallback(self, api_key: str, request: Request) -> Dict[str, Any]:
        """API Key 降级验证（开发环境）"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        client_ip = self._get_client_ip(request)

        from datamind.core.domain.enums import AuditAction

        # 开发环境允许的测试密钥
        valid_keys = {
            "test_api_key_123": {
                "id": "test_user",
                "username": "test_user",
                "strategy": UserRole.DEVELOPER.value,
                "roles": [UserRole.DEVELOPER.value],
                "permissions": ["predict", "view_metrics", "admin"]
            },
            "demo-key": {
                "id": "demo_user",
                "username": "demo_user",
                "strategy": UserRole.DEVELOPER.value,
                "roles": [UserRole.DEVELOPER.value],
                "permissions": ["predict", "view_metrics"]
            },
            "prod_api_key_456": {
                "id": "api_user",
                "username": "api_user",
                "strategy": UserRole.API_USER.value,
                "roles": [UserRole.API_USER.value],
                "permissions": ["predict"]
            }
        }

        if api_key not in valid_keys:
            logger.warning("API Key降级认证失败: 无效密钥, 前缀=%s", api_key[:8])
            return {
                'authenticated': False,
                'reason': "无效的API Key"
            }

        user_info = valid_keys[api_key]

        log_audit(
            action=AuditAction.AUTH_SUCCESS.value,
            user_id=user_info['id'],
            ip_address=client_ip,
            details={
                "api_key_prefix": api_key[:8] + "...",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.info("API Key降级认证成功: 用户=%s (开发环境)", user_info['username'])

        return {
            'authenticated': True,
            'user': user_info
        }

    async def _verify_basic_auth(self, auth_header: str, request: Request) -> Dict[str, Any]:
        """验证Basic Auth"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        client_ip = self._get_client_ip(request)

        try:
            # 解码Basic Auth
            encoded = auth_header.replace("Basic ", "")
            decoded = base64.b64decode(encoded).decode('utf-8')
            username, password = decoded.split(':', 1)

            from datamind.core.db.database import get_db
            from datamind.core.db.models import User
            from datamind.core.security import verify_password

            # 使用线程池执行数据库操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sync_verify_basic_auth,
                username, password, client_ip, request_id, trace_id, span_id, parent_span_id
            )
            return result

        except Exception as e:
            logger.warning("Basic Auth验证失败: %s", e)
            return {'authenticated': False, 'reason': "认证失败"}

    @staticmethod
    def _sync_verify_basic_auth(
            username: str,
            password: str,
            client_ip: Optional[str],
            request_id: str,
            trace_id: str,
            span_id: str,
            parent_span_id: str
    ) -> Dict[str, Any]:
        """同步验证Basic Auth（在线程池中执行）"""
        from datamind.core.db.database import get_db
        from datamind.core.db.models import User
        from datamind.core.security import verify_password
        from datamind.core.domain.enums import AuditAction

        with next(get_db()) as session:
            # 支持用户名或邮箱登录 - 使用 UserStatus 枚举
            user = session.query(User).filter(
                (User.username == username) | (User.email == username),
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None)
            ).first()

            if not user:
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id="unknown",
                    ip_address=client_ip,
                    details={
                        "username": username,
                        "reason": "用户不存在",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("Basic Auth认证失败: 用户不存在, 用户名=%s", username)
                return {'authenticated': False, 'reason': "用户名或密码错误"}

            # 检查账户是否被锁定
            if user.is_locked():
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id=user.user_id,
                    ip_address=client_ip,
                    details={
                        "username": username,
                        "reason": "账户已锁定",
                        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("Basic Auth认证失败: 账户已锁定, 用户=%s", username)
                return {'authenticated': False, 'reason': "账户已被锁定，请稍后再试"}

            # 验证密码
            if not verify_password(password, user.password_hash):
                user.increment_failed_login()
                session.commit()

                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id=user.user_id,
                    ip_address=client_ip,
                    details={
                        "username": username,
                        "reason": "密码错误",
                        "failed_attempts": user.failed_login_attempts,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                logger.warning("Basic Auth认证失败: 密码错误, 用户=%s, 失败次数=%d",
                              username, user.failed_login_attempts)
                return {'authenticated': False, 'reason': "用户名或密码错误"}

            # 记录登录成功
            user.record_login(client_ip)
            session.commit()

            log_audit(
                action=AuditAction.AUTH_SUCCESS.value,
                user_id=user.user_id,
                ip_address=client_ip,
                details={
                    "username": username,
                    "strategy": user.role.value,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.info("Basic Auth认证成功: 用户=%s, 角色=%s", username, user.role.value)

            return {
                'authenticated': True,
                'user': {
                    'id': user.user_id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.full_name,
                    'strategy': user.role.value,
                    'roles': [user.role.value],
                    'permissions': user.permissions or [],
                }
            }


# JWT工具函数
def create_jwt_token(
        user_id: str,
        username: str,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        expires_delta: Optional[timedelta] = None,
        extra_payload: Optional[Dict[str, Any]] = None
) -> str:
    """创建JWT token

    参数:
        user_id: 用户ID
        username: 用户名
        roles: 角色列表（字符串值）
        permissions: 权限列表
        expires_delta: 过期时间增量
        extra_payload: 额外的payload数据

    返回:
        JWT token 字符串
    """
    settings = get_settings()

    # 验证角色是否有效
    valid_roles = [r.value for r in UserRole]
    if roles:
        roles = [r for r in roles if r in valid_roles]
    else:
        roles = [UserRole.API_USER.value]

    # 构建payload
    payload = {
        'sub': user_id,
        'username': username,
        'roles': roles,
        'permissions': permissions or [],
        'iat': int(datetime.now().timestamp()),
        'exp': int(
            (datetime.now() + (expires_delta or timedelta(minutes=settings.auth.jwt_expire_minutes))).timestamp())
    }

    if extra_payload:
        payload.update(extra_payload)

    token = jwt.encode(
        payload,
        settings.auth.jwt_secret_key,
        algorithm=settings.auth.jwt_algorithm
    )

    logger.debug("JWT Token创建成功: 用户=%s, 过期时间=%d秒", username, settings.auth.jwt_expire_minutes * 60)
    return token


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """验证JWT token

    参数:
        token: JWT token 字符串

    返回:
        字典包含 valid, user_id, username, roles, permissions, reason
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret_key,
            algorithms=[settings.auth.jwt_algorithm]
        )

        # 验证角色是否有效
        roles = payload.get('roles', [])
        valid_roles = [r.value for r in UserRole]
        valid_roles_list = [r for r in roles if r in valid_roles]

        logger.debug("JWT Token验证成功: 用户=%s", payload.get('username'))

        return {
            'valid': True,
            'user_id': payload.get('sub'),
            'username': payload.get('username'),
            'roles': valid_roles_list,
            'permissions': payload.get('permissions', []),
            'exp': payload.get('exp'),
            'iat': payload.get('iat')
        }

    except jwt.ExpiredSignatureError:
        logger.warning("JWT Token验证失败: Token已过期")
        return {'valid': False, 'reason': 'Token已过期'}
    except jwt.InvalidTokenError as e:
        logger.warning("JWT Token验证失败: 无效Token, 错误=%s", e)
        return {'valid': False, 'reason': f'无效的Token: {str(e)}'}


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """解码JWT token（不验证签名）

    参数:
        token: JWT token 字符串

    返回:
        解码后的payload，失败返回None
    """
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None


def refresh_jwt_token(token: str) -> Optional[str]:
    """刷新JWT token

    参数:
        token: 旧的JWT token

    返回:
        新的JWT token，如果验证失败返回None
    """
    verification = verify_jwt_token(token)
    if not verification['valid']:
        logger.warning("JWT Token刷新失败: 原Token无效")
        return None

    # 创建新token，保持原有信息
    new_token = create_jwt_token(
        user_id=verification['user_id'],
        username=verification['username'],
        roles=verification['roles'],
        permissions=verification['permissions']
    )
    logger.info("JWT Token刷新成功: 用户=%s", verification['username'])
    return new_token