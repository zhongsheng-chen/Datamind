"""认证工厂

根据统一配置和数据库会话创建本地认证服务。

核心功能：
  - create_auth_service: 创建认证服务

使用示例：
  from datamind.auth.factory import create_auth_service
  from datamind.db.core import UnitOfWork

  async with UnitOfWork() as uow:
      service = create_auth_service(
          session=uow.session
      )
"""

from sqlalchemy.ext.asyncio import AsyncSession

from datamind.auth.errors import AuthError
from datamind.auth.providers import (
    LocalAuthProvider,
    LocalProviderConfig,
)
from datamind.auth.service import AuthService
from datamind.config import get_settings
from datamind.constants import Environment
from datamind.db.repositories import (
    GrantRepository,
    RoleRepository,
    TokenRepository,
    UserRepository,
)


def create_auth_service(
        *,
        session: AsyncSession,
) -> AuthService:
    """创建认证服务

    参数：
        session: SQLAlchemy 异步数据库会话

    返回：
        认证服务

    异常：
        AuthError: 认证功能未启用或生产网段未配置
    """
    settings = get_settings()
    auth_config = settings.auth
    local_config = auth_config.local

    if not auth_config.enabled:
        raise AuthError(
            "认证功能未启用"
        )

    if (
            settings.service.environment
            in {
                Environment.STAGING,
                Environment.PRODUCTION,
            }
            and not local_config.allowed_networks
    ):
        raise AuthError(
            "预发布和生产环境启用认证时，"
            "必须配置 allowed_networks"
        )

    user_repo = UserRepository(
        session
    )

    return AuthService(
        user_repo=user_repo,
        role_repo=RoleRepository(
            session
        ),
        grant_repo=GrantRepository(
            session
        ),
        token_repo=TokenRepository(
            session
        ),
        secret_key=(
            auth_config
            .secret_key
            .get_secret_value()
        ),
        provider=LocalAuthProvider(
            user_repo=user_repo,
            config=LocalProviderConfig(
                max_failed_login_attempts=(
                    local_config
                    .max_failed_login_attempts
                ),
                lock_minutes=local_config.lock_minutes,
                upgrade_password_hash=(
                    local_config
                    .upgrade_password_hash
                ),
                break_glass_only=(
                    local_config.break_glass_only
                ),
            ),
        ),
        algorithm=auth_config.algorithm,
        access_token_expires_minutes=(
            auth_config
            .access_token_expires_minutes
        ),
        refresh_token_expires_days=(
            auth_config
            .refresh_token_expires_days
        ),
        local_allowed_networks=(
            local_config.allowed_networks
        ),
        break_glass_access_token_expires_minutes=(
            local_config
            .break_glass_access_token_expires_minutes
        ),
    )


__all__ = [
    "create_auth_service",
]
