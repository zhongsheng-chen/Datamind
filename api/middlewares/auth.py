# datamind/api/middlewares/auth.py
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional, List, Dict, Any
import time
import jwt
from datetime import datetime, timedelta

from core.logging import log_manager, get_request_id
from config.settings import settings


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    认证中间件

    处理JWT token验证和API密钥认证
    """

    def __init__(
            self,
            app: ASGIApp,
            exclude_paths: List[str] = None,
            public_paths: List[str] = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/ui",
            "/static"
        ]
        self.public_paths = public_paths or [
            "/api/v1/auth/login",
            "/api/v1/auth/register"
        ]
        self.security = HTTPBearer(auto_error=False)

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        request_id = get_request_id()
        start_time = time.time()

        # 检查是否为排除路径
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        # 获取认证信息
        auth_result = await self._authenticate(request)

        if not auth_result['authenticated']:
            # 记录认证失败
            duration = (time.time() - start_time) * 1000
            log_manager.log_audit(
                action="AUTH_FAILED",
                user_id="anonymous",
                ip_address=request.client.host if request.client else None,
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "reason": auth_result['reason'],
                    "duration_ms": round(duration, 2)
                },
                request_id=request_id
            )

            raise HTTPException(
                status_code=401,
                detail=auth_result['reason']
            )

        # 将用户信息添加到request.state
        request.state.user = auth_result['user']
        request.state.token = auth_result.get('token')

        # 记录认证成功
        duration = (time.time() - start_time) * 1000
        log_manager.log_audit(
            action="AUTH_SUCCESS",
            user_id=auth_result['user'].get('id', 'unknown'),
            ip_address=request.client.host if request.client else None,
            details={
                "path": request.url.path,
                "method": request.method,
                "auth_type": auth_result['auth_type'],
                "duration_ms": round(duration, 2)
            },
            request_id=request_id
        )

        response = await call_next(request)
        return response

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
        1. Bearer Token (JWT)
        2. API Key
        3. Basic Auth (可选)
        """
        # 尝试获取Authorization header
        auth_header = request.headers.get("Authorization")
        api_key = request.headers.get(settings.API_KEY_HEADER)

        result = {
            'authenticated': False,
            'reason': None,
            'user': None,
            'auth_type': None
        }

        # 1. 尝试Bearer Token认证
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            auth_result = await self._verify_jwt_token(token)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'jwt'
                return result

        # 2. 尝试API Key认证
        if api_key and settings.API_KEY_ENABLED:
            auth_result = await self._verify_api_key(api_key)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'api_key'
                return result

        # 3. 尝试Basic Auth (可选)
        if auth_header and auth_header.startswith("Basic "):
            auth_result = await self._verify_basic_auth(auth_header)
            if auth_result['authenticated']:
                result.update(auth_result)
                result['auth_type'] = 'basic'
                return result

        # 所有认证方式都失败
        result['reason'] = "未提供有效的认证信息"
        return result

    async def _verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """验证JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

            # 检查token是否过期
            exp = payload.get('exp')
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                return {
                    'authenticated': False,
                    'reason': "Token已过期"
                }

            return {
                'authenticated': True,
                'user': {
                    'id': payload.get('sub'),
                    'username': payload.get('username'),
                    'roles': payload.get('roles', []),
                    'permissions': payload.get('permissions', [])
                },
                'token': token
            }

        except jwt.ExpiredSignatureError:
            return {
                'authenticated': False,
                'reason': "Token已过期"
            }
        except jwt.InvalidTokenError as e:
            return {
                'authenticated': False,
                'reason': f"无效的Token: {str(e)}"
            }

    async def _verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """验证API Key"""
        # TODO: 从数据库或缓存中验证API Key
        # 这里简化处理，实际应该查询API Key存储

        # 示例：简单验证
        if api_key == "demo-key":
            return {
                'authenticated': True,
                'user': {
                    'id': "demo_user",
                    'username': "Demo User",
                    'roles': ["user"],
                    'api_key': api_key
                }
            }

        # 可以添加更复杂的验证逻辑
        # 例如：从Redis中获取API Key信息
        # api_key_info = await redis.get(f"api_key:{api_key}")

        return {
            'authenticated': False,
            'reason': "无效的API Key"
        }

    async def _verify_basic_auth(self, auth_header: str) -> Dict[str, Any]:
        """验证Basic Auth"""
        import base64

        try:
            # 解码Basic Auth
            encoded = auth_header.replace("Basic ", "")
            decoded = base64.b64decode(encoded).decode('utf-8')
            username, password = decoded.split(':', 1)

            # TODO: 验证用户名密码
            # 这里简化处理
            if username == "admin" and password == "admin":
                return {
                    'authenticated': True,
                    'user': {
                        'id': username,
                        'username': username,
                        'roles': ["admin"]
                    }
                }

            return {
                'authenticated': False,
                'reason': "用户名或密码错误"
            }

        except Exception as e:
            return {
                'authenticated': False,
                'reason': f"Basic Auth解析失败: {str(e)}"
            }


# JWT工具函数
def create_jwt_token(
        user_id: str,
        username: str,
        roles: List[str] = None,
        permissions: List[str] = None,
        expires_delta: timedelta = None
) -> str:
    """创建JWT token"""
    payload = {
        'sub': user_id,
        'username': username,
        'iat': datetime.now(),
        'exp': datetime.now() + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    }

    if roles:
        payload['roles'] = roles
    if permissions:
        payload['permissions'] = permissions

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """验证JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        return {
            'valid': True,
            'user_id': payload.get('sub'),
            'username': payload.get('username'),
            'roles': payload.get('roles', []),
            'permissions': payload.get('permissions', [])
        }

    except jwt.ExpiredSignatureError:
        return {'valid': False, 'reason': 'Token已过期'}
    except jwt.InvalidTokenError as e:
        return {'valid': False, 'reason': f'无效的Token: {str(e)}'}