# Datamind/datamind/api/dependencies.py

"""API依赖项

定义 FastAPI 的依赖注入函数，提供认证、授权、请求日志等通用功能。

依赖项分类：
  - 认证相关：API密钥验证、用户身份获取
  - 授权相关：管理员权限检查
  - 请求上下文：应用ID获取、请求日志记录

使用方式：
  在路由函数中通过 Depends() 注入依赖：

    @app.post("/models")
    async def create_model(
        current_user: str = Depends(get_current_user),
        application_id: str = Depends(get_application_id)
    ):
        # 使用 current_user 和 application_id
        pass

TODO:
  - 实现完整的 API 密钥验证逻辑
  - 实现从 API 密钥获取用户信息的逻辑
  - 实现管理员权限检查逻辑
  - 集成认证服务或权限服务
"""

from fastapi import Header, HTTPException, Depends, Request
from typing import Optional

from datamind.core.logging import log_manager, debug_print
from datamind.core.logging import context
from datamind.config import settings


async def get_api_key(
        x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    获取并验证API密钥

    从请求头中提取 X-API-Key，验证其有效性。

    参数:
        x_api_key: API密钥，从请求头获取

    返回:
        验证通过的API密钥，或 "anonymous"（如果未启用API密钥认证）

    抛出:
        HTTPException: 401 如果API密钥缺失（且认证已启用）

    注意:
        - 如果 settings.API_KEY_ENABLED 为 False，直接返回 "anonymous"
        - 当前仅做基础验证，完整验证逻辑待实现
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

    根据API密钥获取对应的用户ID。

    参数:
        request: FastAPI 请求对象
        x_api_key: API密钥（从依赖项获取）

    返回:
        用户ID

    注意:
        - 当前返回 "system" 作为临时用户
        - 完整实现需要解析API密钥对应的用户信息
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

    检查当前用户是否具有管理员权限。

    参数:
        request: FastAPI 请求对象
        current_user: 当前用户（从依赖项获取）

    返回:
        当前用户ID

    抛出:
        HTTPException: 403 如果用户不是管理员

    注意:
        - 当前临时返回 True，完整实现需要检查用户权限
        - 无权限时会记录审计日志
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

    从请求头中提取 X-Application-ID，如果不存在则生成临时ID。

    参数:
        request: FastAPI 请求对象
        x_application_id: 应用ID，从请求头获取

    返回:
        应用ID（如果请求头不存在，则生成临时ID）

    注意:
        - 生成的应用ID格式：APP_XXXXXXXX（8位随机十六进制）
        - 临时ID用于未提供应用ID的请求
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

    用于在路由函数中记录额外的请求信息。

    参数:
        request: FastAPI 请求对象
        current_user: 当前用户（从依赖项获取）

    注意:
        - 当前为空实现，主要日志在中间件中完成
        - 可用于记录业务特定的请求信息
    """
    # 已经在中间件中记录，这里可以添加额外信息
    pass