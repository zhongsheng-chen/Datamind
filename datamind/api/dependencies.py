# datamind/api/dependencies.py

"""API 依赖注入模块

提供 FastAPI 依赖注入功能，包括：
  - 数据库会话依赖
  - 认证依赖
  - 权限依赖
  - 模型加载依赖
  - A/B测试依赖
  - 请求上下文依赖
  - 分页依赖
  - 速率限制依赖
"""

import time
import logging
from collections import defaultdict
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from fastapi import Request, HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from datamind.core.db.database import get_db
from datamind.core.ml.model import model_loader
from datamind.core.ml.model import model_registry
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.logging import log_audit, context
from datamind.core.domain.enums import AuditAction, UserRole, UserStatus
from datamind.config import get_settings
from datamind.config.settings import RateLimitConfig


# ==================== 数据库依赖 ====================

def get_database() -> Session:
    """获取数据库会话"""
    return next(get_db())


# ==================== API Key 辅助函数 ====================

async def get_api_key(
        request: Request,
        authorization: Optional[str] = Header(None, alias="Authorization"),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Optional[str]:
    """
    获取当前请求的 API Key

    参数:
        request: FastAPI 请求对象
        authorization: Authorization 头
        x_api_key: X-API-Key 头

    返回:
        Optional[str]: API Key，如果不存在返回 None
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]

    if x_api_key:
        return x_api_key

    return None


def _get_client_ip(request: Optional[Request]) -> Optional[str]:
    """获取客户端真实IP"""
    if request is None:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else None


# ==================== 认证依赖 ====================

security = HTTPBearer(auto_error=False)


async def verify_api_key(
        request: Request,
        authorization: Optional[str] = Header(None, alias="Authorization"),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """
    验证 API 密钥

    返回:
        Dict: 包含 api_key, user_id, roles, permissions 等信息
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    settings = get_settings()
    client_ip = _get_client_ip(request)

    api_key = await get_api_key(request, authorization, x_api_key)

    if not api_key:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id="unknown",
            ip_address=client_ip,
            details={
                "reason": "missing_api_key",
                "auth_type": "api_key",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 如果未启用 API Key 认证，跳过验证
    if not settings.auth.api_key_enabled:
        return {
            "api_key": api_key,
            "user_id": "system",
            "roles": ["admin"],
            "permissions": ["*"],
            "authenticated": True,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        }

    # 从数据库验证 API Key
    try:
        from datamind.core.db.database import get_db
        from datamind.core.db.models import ApiKey
        from datamind.core.db.models import User

        with next(get_db()) as session:
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
                        "reason": "invalid_api_key",
                        "auth_type": "api_key",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid API Key"
                )

            # 检查过期时间
            if api_key_record.expires_at and api_key_record.expires_at < datetime.now():
                log_audit(
                    action=AuditAction.AUTH_FAILED.value,
                    user_id=api_key_record.user_id,
                    ip_address=client_ip,
                    details={
                        "reason": "api_key_expired",
                        "expires_at": api_key_record.expires_at.isoformat(),
                        "auth_type": "api_key",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API Key expired"
                )

            # 获取关联用户
            user = session.query(User).filter_by(
                user_id=api_key_record.user_id,
                status=UserStatus.ACTIVE
            ).first()

            # 更新最后使用时间
            api_key_record.last_used_at = datetime.now()
            session.commit()

            # 获取角色
            if api_key_record.roles:
                roles = api_key_record.roles
            elif user:
                roles = [user.role.value]
            else:
                roles = [UserRole.API_USER.value]

            # 获取权限
            if api_key_record.permissions:
                permissions = api_key_record.permissions
            elif user and user.permissions:
                permissions = user.permissions
            else:
                permissions = []

            log_audit(
                action=AuditAction.AUTH_SUCCESS.value,
                user_id=api_key_record.user_id,
                ip_address=client_ip,
                details={
                    "api_key_id": api_key_record.id,
                    "username": user.username if user else None,
                    "roles": roles,
                    "auth_type": "api_key",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return {
                "api_key": api_key,
                "api_key_id": api_key_record.id,
                "user_id": api_key_record.user_id,
                "username": user.username if user else None,
                "roles": roles,
                "permissions": permissions,
                "authenticated": True,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            }

    except ImportError as e:
        # 如果 ApiKey 模型不存在，使用简单验证（开发环境）
        logging.warning(f"Database models not available for API key validation: {e}")
        valid_keys = ["test_api_key_123", "demo-key", "prod_api_key_456"]
        if api_key not in valid_keys:
            log_audit(
                action=AuditAction.AUTH_FAILED.value,
                user_id="unknown",
                ip_address=client_ip,
                details={
                    "reason": "invalid_api_key",
                    "auth_type": "api_key_fallback",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key"
            )

        # 根据 API Key 返回不同角色
        role_map = {
            "test_api_key_123": UserRole.DEVELOPER.value,
            "demo-key": UserRole.DEVELOPER.value,
            "prod_api_key_456": UserRole.API_USER.value
        }
        role = role_map.get(api_key, UserRole.API_USER.value)

        log_audit(
            action=AuditAction.AUTH_SUCCESS.value,
            user_id=f"api_user_{api_key[:8]}",
            ip_address=client_ip,
            details={
                "strategy": role,
                "auth_type": "api_key_fallback",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return {
            "api_key": api_key,
            "user_id": f"api_user_{api_key[:8]}",
            "username": f"api_user_{api_key[:8]}",
            "roles": [role],
            "permissions": ["predict"] if role == UserRole.API_USER.value else ["predict", "view_metrics", "admin"],
            "authenticated": True,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        }

    except Exception as e:
        logging.error(f"API key validation error: {e}")
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id="unknown",
            ip_address=client_ip,
            details={
                "reason": "validation_error",
                "error": str(e),
                "auth_type": "api_key",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key validation error"
        )


async def verify_oauth2_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    验证 OAuth2 Token (JWT)
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    settings = get_settings()
    token = credentials.credentials

    if not settings.auth.jwt_secret_key:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id="unknown",
            details={
                "reason": "jwt_secret_not_configured",
                "auth_type": "jwt",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret key not configured"
        )

    try:
        import jwt

        payload = jwt.decode(
            token,
            settings.auth.jwt_secret_key,
            algorithms=[settings.auth.jwt_algorithm]
        )

        # 验证角色是否有效
        roles = payload.get("roles", [])
        valid_roles = [r.value for r in UserRole]
        valid_roles_list = [r for r in roles if r in valid_roles]
        if not valid_roles_list:
            valid_roles_list = [UserRole.API_USER.value]  # 默认使用 API_USER

        log_audit(
            action=AuditAction.AUTH_SUCCESS.value,
            user_id=payload.get("sub", "unknown"),
            details={
                "username": payload.get("username"),
                "roles": valid_roles_list,
                "auth_type": "jwt",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "roles": valid_roles_list,
            "permissions": payload.get("permissions", []),
            "exp": payload.get("exp"),
            "authenticated": True,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        }
    except jwt.ExpiredSignatureError:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id="unknown",
            details={
                "reason": "token_expired",
                "auth_type": "jwt",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id="unknown",
            details={
                "reason": "invalid_token",
                "error": str(e),
                "auth_type": "jwt",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT library not installed"
        )


async def get_current_user(
        auth_info: Dict[str, Any] = Depends(verify_api_key),
) -> Dict[str, Any]:
    """获取当前用户信息"""
    return auth_info


async def require_admin(
        current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """要求管理员权限"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()

    roles = current_user.get("roles", [])
    if UserRole.ADMIN.value not in roles and "admin" not in roles:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id=current_user.get("user_id", "unknown"),
            details={
                "reason": "admin_required",
                "roles": roles,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def require_permission(
        permission: str,
        current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """要求特定权限"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()

    permissions = current_user.get("permissions", [])
    roles = current_user.get("roles", [])

    if UserRole.ADMIN.value in roles or "admin" in roles:
        return current_user

    if permission not in permissions:
        log_audit(
            action=AuditAction.AUTH_FAILED.value,
            user_id=current_user.get("user_id", "unknown"),
            details={
                "reason": "permission_required",
                "required_permission": permission,
                "user_permissions": permissions,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}"
        )

    return current_user


# ==================== 模型依赖 ====================

async def get_model(
        model_id: str,
        current_user: Dict[str, Any] = Depends(get_current_user),
        request: Request = None,
) -> Any:
    """获取已加载的模型"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = _get_client_ip(request)

    model = model_loader.get_model(model_id)

    if not model:
        try:
            loaded = model_loader.load_model(
                model_id=model_id,
                operator=current_user.get("user_id", "system"),
                ip_address=client_ip
            )
            if not loaded:
                log_audit(
                    action=AuditAction.MODEL_LOAD.value,
                    user_id=current_user.get("user_id", "system"),
                    details={
                        "model_id": model_id,
                        "reason": "model_not_found",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model not found or failed to load: {model_id}"
                )
            model = model_loader.get_model(model_id)
        except HTTPException:
            raise
        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_LOAD.value,
                user_id=current_user.get("user_id", "system"),
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load model: {str(e)}"
            )

    return model


async def get_model_metadata(
        model_id: str,
        current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取模型元数据"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()

    metadata = model_registry.get_model_info(model_id)

    if not metadata:
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id=current_user.get("user_id", "system"),
            details={
                "model_id": model_id,
                "reason": "not_found",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not found: {model_id}"
        )

    return metadata


# ==================== A/B 测试依赖 ====================

async def get_ab_test_assignment(
        test_id: str,
        user_id: str,
        request: Request,
) -> Dict[str, Any]:
    """获取 A/B 测试分组"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    settings = get_settings()
    client_ip = _get_client_ip(request)

    if not settings.ab_test.enabled:
        return {
            "test_id": test_id,
            "group_name": "default",
            "model_id": None,
            "in_test": False
        }

    try:
        assignment = ab_test_manager.get_assignment(
            test_id=test_id,
            user_id=user_id,
            ip_address=client_ip
        )

        log_audit(
            action=AuditAction.AB_TEST_ASSIGNMENT.value,
            user_id=user_id,
            ip_address=client_ip,
            resource_type="ab_test",
            resource_id=test_id,
            details={
                "group_name": assignment.get("group_name"),
                "in_test": assignment.get("in_test", False),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return assignment
    except Exception as e:
        log_audit(
            action=AuditAction.AB_TEST_ERROR.value,
            user_id=user_id,
            ip_address=client_ip,
            resource_type="ab_test",
            resource_id=test_id,
            details={
                "error": str(e),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            reason="A/B test assignment failed",
            request_id=request_id
        )
        return {
            "test_id": test_id,
            "group_name": "default",
            "model_id": None,
            "in_test": False,
            "error": str(e)
        }


# ==================== 请求上下文依赖 ====================

async def set_request_context(
        request: Request,
) -> None:
    """设置请求上下文（中间件使用）"""
    # 从请求头获取或生成请求ID
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = context.generate_request_id()
    context.set_request_id(request_id)

    # 从请求头获取或生成 trace_id
    trace_id = request.headers.get("X-Trace-ID")
    if not trace_id:
        trace_id = context.generate_trace_id()
    context.set_trace_id(trace_id)

    # 从请求头获取 parent_span_id（用于链路追踪）
    parent_span_id = request.headers.get("X-Parent-Span-ID")
    if parent_span_id:
        context.set_parent_span_id(parent_span_id)
    else:
        context.set_parent_span_id("")

    # 生成 span_id
    span_id = context.generate_span_id()
    context.set_span_id(span_id)

    # 存储到 request.state 供后续使用
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    request.state.span_id = span_id
    request.state.parent_span_id = parent_span_id


def get_request_id(request: Request) -> str:
    """获取当前请求ID"""
    return getattr(request.state, "request_id", context.get_request_id())


def get_trace_id(request: Request) -> str:
    """获取当前 trace_id"""
    return getattr(request.state, "trace_id", context.get_trace_id())


def get_span_id(request: Request) -> str:
    """获取当前 span_id"""
    return getattr(request.state, "span_id", context.get_span_id())


def get_parent_span_id(request: Request) -> str:
    """获取当前 parent_span_id"""
    return getattr(request.state, "parent_span_id", context.get_parent_span_id())


# ==================== 分页依赖 ====================

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")


def get_pagination_params(
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
) -> PaginationParams:
    """获取分页参数"""
    page_size = min(page_size, 100)
    return PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )


def get_offset_limit(params: PaginationParams) -> Tuple[int, int]:
    """计算偏移量和限制"""
    offset = (params.page - 1) * params.page_size
    limit = params.page_size
    return offset, limit


def get_pagination_response(
        items: List[Any],
        total: int,
        params: PaginationParams,
) -> Dict[str, Any]:
    """构建分页响应"""
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": (total + params.page_size - 1) // params.page_size,
        "has_next": params.page * params.page_size < total,
        "has_prev": params.page > 1
    }


# ==================== 速率限制依赖 ====================

class RateLimiter:
    """速率限制器（支持 Redis 和内存）"""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self._requests = defaultdict(list)
        self._config = config or get_settings().rate_limit
        self._use_redis = False
        self._redis_client = None

        if self._config.rate_limit_enabled:
            try:
                settings = get_settings()
                import redis.asyncio as redis
                self._redis_client = redis.from_url(
                    settings.redis.url,
                    decode_responses=True
                )
                self._use_redis = True
            except Exception as e:
                logging.warning(f"Redis connection failed, falling back to memory: {e}")
                self._use_redis = False

    def _check_memory(self, key: str, limit: int, period: int) -> Tuple[bool, Dict]:
        """使用内存检查速率限制"""
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if now - t < period]

        current = len(self._requests[key])
        remaining = limit - current

        if current >= limit:
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset": int(self._requests[key][0] + period) if self._requests[key] else int(now + period)
            }

        self._requests[key].append(now)
        return True, {
            "limit": limit,
            "remaining": remaining - 1,
            "reset": int(now + period)
        }

    async def _check_redis(self, key: str, limit: int, period: int) -> Tuple[bool, Dict]:
        """使用 Redis 检查速率限制"""
        try:
            now = int(time.time())
            window_key = f"rate_limit:{key}:{now // period}"

            lua_script = """
            local key = KEYS[1]
            local limit = tonumber(ARGV[1])
            local period = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])

            local current = redis.call('GET', key)
            if current and tonumber(current) >= limit then
                return {0, current}
            end

            local new_count = redis.call('INCR', key)
            redis.call('EXPIRE', key, period)
            return {1, new_count}
            """

            result = await self._redis_client.eval(lua_script, 1, window_key, limit, period, now)
            allowed = result[0] == 1
            current = int(result[1]) if result[1] else 0

            return allowed, {
                "limit": limit,
                "remaining": limit - current,
                "reset": ((now // period) + 1) * period
            }
        except Exception as e:
            logging.error(f"Redis rate limit check failed: {e}")
            return self._check_memory(key, limit, period)

    async def check(self, key: str, limit: int, period: int) -> Tuple[bool, Dict]:
        """检查是否超过限制"""
        if self._use_redis and self._redis_client:
            return await self._check_redis(key, limit, period)
        return self._check_memory(key, limit, period)

    def reset(self, key: str) -> None:
        """重置限流器"""
        if key in self._requests:
            del self._requests[key]
        if self._redis_client:
            try:
                pattern = f"rate_limit:{key}:*"
                for redis_key in self._redis_client.scan_iter(match=pattern):
                    self._redis_client.delete(redis_key)
            except Exception as e:
                logging.error(f"Failed to reset rate limit: {e}")


# 全局速率限制器实例
_rate_limiter = RateLimiter()


async def check_rate_limit(
        request: Request,
        current_user: Dict[str, Any] = Depends(get_current_user),
) -> None:
    """检查速率限制"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    settings = get_settings()
    client_ip = _get_client_ip(request)

    if not settings.security.rate_limit_enabled:
        return

    user_id = current_user.get("user_id", "anonymous")
    key = f"user:{user_id}"

    # 根据用户角色获取不同的限制
    roles = current_user.get("roles", [])
    if UserRole.ADMIN.value in roles:
        limit = settings.security.rate_limit_requests
        period = settings.security.rate_limit_period
    elif UserRole.DEVELOPER.value in roles:
        limit = settings.security.rate_limit_requests
        period = settings.security.rate_limit_period
    elif UserRole.ANALYST.value in roles:
        limit = settings.security.rate_limit_requests
        period = settings.security.rate_limit_period
    elif UserRole.API_USER.value in roles:
        limit = settings.security.rate_limit_requests
        period = settings.security.rate_limit_period
    else:
        limit = settings.security.rate_limit_requests
        period = settings.security.rate_limit_period

    allowed, info = await _rate_limiter.check(
        key=key,
        limit=limit,
        period=period
    )

    if not allowed:
        log_audit(
            action=AuditAction.RATE_LIMIT_EXCEEDED.value,
            user_id=user_id,
            ip_address=client_ip,
            details={
                "limit": info["limit"],
                "remaining": info["remaining"],
                "reset": info["reset"],
                "path": request.url.path,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        response_headers = {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"])
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {info['limit']} requests per {period} seconds",
            headers=response_headers
        )

    request.state.rate_limit = info


def get_rate_limit_info(request: Request) -> Dict[str, Any]:
    """获取速率限制信息"""
    return getattr(request.state, "rate_limit", {})


# ==================== 日志依赖 ====================

def log_request(request: Request) -> None:
    """记录请求信息（用于审计）"""
    request_id = get_request_id(request)
    trace_id = get_trace_id(request)
    span_id = get_span_id(request)
    parent_span_id = get_parent_span_id(request)
    client_ip = _get_client_ip(request)

    log_audit(
        action=AuditAction.MODEL_QUERY.value,  # 使用 MODEL_QUERY 或考虑新增 API_REQUEST
        user_id=getattr(request.state, "user_id", "anonymous"),
        ip_address=client_ip,
        resource_type="api",
        resource_id=request.url.path,
        details={
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "request_id": request_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        },
        request_id=request_id
    )