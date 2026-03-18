# Datamind/datamind/api/dependencies.py
from fastapi import Header, HTTPException, Depends, Request
from typing import Optional

from datamind.core import log_manager, get_request_id
from datamind.config import settings


async def get_api_key(
        x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    获取并验证API密钥
    """
    if not settings.API_KEY_ENABLED:
        return "anonymous"

    if not x_api_key:
        log_manager.log_audit(
            action="API_KEY_MISSING",
            user_id="unknown",
            details={"error": "API密钥缺失"}
        )
        raise HTTPException(status_code=401, detail="缺少API密钥")

    # TODO: 验证API密钥有效性
    # 这里应该调用认证服务验证API密钥

    return x_api_key


async def get_current_user(
        request: Request,
        x_api_key: str = Depends(get_api_key)
) -> str:
    """
    获取当前用户
    """
    # TODO: 从API密钥获取用户信息
    # 这里应该解析API密钥对应的用户
    user_id = "system"

    # 记录用户操作
    log_manager.set_request_id(get_request_id())

    return user_id


async def require_admin(
        request: Request,
        current_user: str = Depends(get_current_user)
) -> str:
    """
    要求管理员权限
    """
    # TODO: 检查用户是否为管理员
    # 这里应该调用权限服务

    is_admin = True  # 临时设置

    if not is_admin:
        log_manager.log_audit(
            action="ADMIN_REQUIRED",
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            details={"path": request.url.path}
        )
        raise HTTPException(status_code=403, detail="需要管理员权限")

    return current_user


async def get_application_id(
        request: Request,
        x_application_id: Optional[str] = Header(None, alias="X-Application-ID")
) -> str:
    """
    获取应用ID
    """
    if not x_application_id:
        # 生成临时ID
        import uuid
        x_application_id = f"APP_{uuid.uuid4().hex[:8].upper()}"

    return x_application_id


async def log_request(
        request: Request,
        current_user: str = Depends(get_current_user)
):
    """
    记录请求日志
    """
    # 已经在中间件中记录，这里可以添加额外信息
    pass