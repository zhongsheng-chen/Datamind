# datamind/auth/providers/local.py

"""本地认证提供方

使用用户表中的 Argon2 密码哈希完成本地用户认证。

核心功能：
  - LocalProviderConfig: 本地认证配置
  - LocalAuthProvider.authenticate: 校验本地用户名和密码

使用示例：
  from datamind.auth.providers.base import (
      PasswordCredentials,
  )
  from datamind.auth.providers.local import (
      LocalAuthProvider,
  )

  # 创建本地认证提供方
  provider = LocalAuthProvider(
      user_repo=user_repo
  )

  # 校验本地用户名和密码
  identity = await provider.authenticate(
      PasswordCredentials(
          username="admin",
          password="P@ssw1rd",
      )
  )
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from datamind.auth.enums import UserStatus
from datamind.auth.errors import (
    InvalidCredentialsError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.password import (
    hash_password,
    needs_rehash,
    verify_password,
)
from datamind.auth.providers.base import (
    BaseAuthProvider,
    PasswordCredentials,
    ProviderIdentity,
)
from datamind.db.models.users import User
from datamind.db.repositories.user import (
    UserRepository,
)


_DUMMY_PASSWORD_HASH = hash_password(
    "datamind-invalid-user-password"
)


@dataclass(
    slots=True,
    frozen=True,
)
class LocalProviderConfig:
    """本地认证配置"""

    max_failed_login_attempts: int = 5
    lock_minutes: int = 30
    upgrade_password_hash: bool = True
    break_glass_only: bool = False

    def __post_init__(
            self,
    ) -> None:
        """校验配置"""
        if self.max_failed_login_attempts <= 0:
            raise ValueError(
                "max_failed_login_attempts 必须大于 0"
            )

        if self.lock_minutes <= 0:
            raise ValueError(
                "lock_minutes 必须大于 0"
            )


class LocalAuthProvider(
    BaseAuthProvider
):
    """本地认证提供方"""

    def __init__(
            self,
            *,
            user_repo: UserRepository,
            config: LocalProviderConfig | None = None,
    ) -> None:
        """初始化本地认证提供方"""
        self.user_repo = user_repo
        self.config = (
            config
            or LocalProviderConfig()
        )

    async def authenticate(
            self,
            credentials: PasswordCredentials,
            *,
            current_time: datetime | None = None,
    ) -> ProviderIdentity:
        """校验本地用户名和密码"""
        now = self._normalize_current_time(
            current_time
        )

        user = await self.user_repo.get_user(
            username=credentials.username
        )

        if user is None:
            verify_password(
                password=credentials.password,
                password_hash=_DUMMY_PASSWORD_HASH,
            )
            raise InvalidCredentialsError()

        if (
                self.config.break_glass_only
                and not bool(
                    user.is_break_glass
                )
        ):
            raise InvalidCredentialsError()

        self._validate_user_status(
            user,
            current_time=now,
        )

        password_hash = user.password_hash

        if password_hash is None:
            raise InvalidCredentialsError()

        if not verify_password(
                password=credentials.password,
                password_hash=password_hash,
        ):
            self._record_login_failure(
                user,
                current_time=now,
            )

        password_rehashed = (
            self._upgrade_password_hash(
                user,
                password=credentials.password,
                current_time=now,
            )
        )

        self.user_repo.record_login_success(
            user,
            logged_in_at=now,
        )

        return ProviderIdentity(
            subject=user.user_id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            claims={
                "user_id": user.user_id,
                "status": user.status,
                "password_rehashed": password_rehashed,
            },
        )

    def _validate_user_status(
            self,
            user: User,
            *,
            current_time: datetime,
    ) -> None:
        """校验用户状态"""
        if user.status == str(
                UserStatus.DISABLED
        ):
            raise UserDisabledError()

        if user.status == str(
                UserStatus.LOCKED
        ):
            locked_until = user.locked_until

            if (
                    locked_until is not None
                    and self._to_utc(
                        locked_until
                    ) <= current_time
            ):
                self.user_repo.unlock_user(
                    user
                )
                return

            raise UserLockedError()

        if user.status != str(
                UserStatus.ACTIVE
        ):
            raise InvalidCredentialsError()

    def _record_login_failure(
            self,
            user: User,
            *,
            current_time: datetime,
    ) -> None:
        """记录登录失败并按阈值锁定用户"""
        self.user_repo.record_login_failure(
            user
        )

        failed_count = (
            user.failed_login_count
            or 0
        )

        if (
                failed_count
                < self.config.max_failed_login_attempts
        ):
            raise InvalidCredentialsError()

        locked_until = (
            current_time
            + timedelta(
                minutes=self.config.lock_minutes
            )
        )

        self.user_repo.lock_user(
            user,
            locked_until=locked_until,
        )

        raise UserLockedError(
            "用户登录失败次数过多，"
            f"已锁定至 {locked_until.isoformat()}"
        )

    def _upgrade_password_hash(
            self,
            user: User,
            *,
            password: str,
            current_time: datetime,
    ) -> bool:
        """按当前 Argon2 参数升级密码哈希"""
        if not self.config.upgrade_password_hash:
            return False

        password_hash = user.password_hash

        if (
                password_hash is None
                or not needs_rehash(
                    password_hash
                )
        ):
            return False

        self.user_repo.update_password(
            user,
            password_hash=hash_password(
                password
            ),
            changed_at=(
                user.password_changed_at
                or current_time
            ),
        )

        return True

    @staticmethod
    def _normalize_current_time(
            value: datetime | None,
    ) -> datetime:
        """获取 UTC 当前时间"""
        if value is None:
            return datetime.now(
                timezone.utc
            )

        return LocalAuthProvider._to_utc(
            value
        )

    @staticmethod
    def _to_utc(
            value: datetime,
    ) -> datetime:
        """转换为 UTC 时间"""
        if (
                value.tzinfo is None
                or value.utcoffset() is None
        ):
            raise ValueError(
                "datetime 必须包含时区信息"
            )

        return value.astimezone(
            timezone.utc
        )


__all__ = [
    "LocalProviderConfig",
    "LocalAuthProvider",
]
