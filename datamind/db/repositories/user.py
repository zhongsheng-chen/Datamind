"""用户仓储

提供用户的查询、创建、更新和状态管理能力。

核心功能：
  - get_user: 获取单个用户
  - list_users: 获取用户列表
  - list_active_users: 获取活跃用户列表
  - create_user: 创建用户
  - update_user: 更新用户
  - replace_profile: 替换用户资料
  - update_password: 更新密码哈希
  - activate_user: 启用用户
  - disable_user: 停用用户
  - mark_deleted: 逻辑删除用户
  - restore_user: 恢复用户
  - lock_user: 锁定用户
  - unlock_user: 解锁用户
  - record_login_success: 记录登录成功
  - record_login_failure: 记录登录失败

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.user import UserRepository

  async with UnitOfWork() as uow:
      repo = UserRepository(uow.session)

      user = repo.create_user(
          user_id="usr_0123456789abcdef",
          username="admin",
          password_hash="$argon2id$...",
          display_name="Administrator",
          email="admin@example.com",
          created_by="usr_fedcba9876543210",
      )
"""

from dataclasses import (
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.auth.enums import UserStatus
from datamind.db.models.users import User
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class UserPatch:
    """用户更新结构

    注意：
        不允许通过 patch 修改 password_hash 和 status，
        分别由密码更新方法和生命周期方法控制。

    属性：
        username: 登录用户名
        display_name: 用户显示名称
        email: 用户邮箱
    """

    username: str | None = None
    display_name: str | None = None
    email: str | None = None


class UserRepository(BaseRepository):
    """用户仓储"""

    async def get_user(
            self,
            *,
            user_id: str | None = None,
            username: str | None = None,
            email: str | None = None,
    ) -> User | None:
        """获取单个用户

        参数：
            user_id: 用户 ID（可选）
            username: 登录用户名（可选）
            email: 用户邮箱（可选）

        返回：
            用户对象，不存在时返回 None

        异常：
            ValueError: 未提供查询条件或同时提供多个查询条件
        """
        conditions = [
            value is not None
            for value in (
                user_id,
                username,
                email,
            )
        ]

        if sum(conditions) != 1:
            raise ValueError(
                "user_id、username、email 必须且只能提供一个"
            )

        stmt = select(
            User
        )

        if user_id is not None:
            stmt = stmt.where(
                User.user_id == user_id
            )

        elif username is not None:
            stmt = stmt.where(
                User.username == username
            )

        else:
            stmt = stmt.where(
                User.email == email
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_users(
            self,
            *,
            status: UserStatus | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[User]:
        """获取用户列表

        参数：
            status: 用户状态（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            用户列表，按创建时间倒序排列
        """
        stmt = select(
            User
        )

        if status is not None:
            stmt = stmt.where(
                User.status == str(
                    status
                )
            )

        stmt = stmt.order_by(
            User.created_at.desc()
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def list_active_users(
            self,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[User]:
        """获取活跃用户列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            活跃用户列表，按创建时间倒序排列
        """
        return await self.list_users(
            status=UserStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_user(
            self,
            *,
            user_id: str,
            username: str,
            password_hash: str,
            display_name: str | None = None,
            email: str | None = None,
            status: UserStatus = UserStatus.ACTIVE,
            is_break_glass: bool = False,
            created_by: str | None = None,
    ) -> User:
        """创建用户

        参数：
            user_id: 用户 ID
            username: 登录用户名
            password_hash: 密码哈希
            display_name: 用户显示名称（可选）
            email: 用户邮箱（可选）
            status: 用户状态
            is_break_glass: 是否为本地应急账户
            created_by: 创建用户 ID（可选）

        返回：
            创建后的用户对象
        """
        new_user = User(
            user_id=user_id,
            username=username,
            status=str(
                status
            ),
            password_hash=password_hash,
            is_break_glass=is_break_glass,
        )

        if display_name is not None:
            new_user.display_name = display_name

        if email is not None:
            new_user.email = email

        if created_by is not None:
            new_user.created_by = created_by

        self.add(
            new_user
        )

        return new_user

    def update_user(
            self,
            user: User,
            *,
            patch: UserPatch,
            updated_by: str | None = None,
    ) -> User:
        """更新用户

        参数：
            user: 用户对象
            patch: 用户更新内容
            updated_by: 更新用户 ID（可选）

        返回：
            更新后的用户对象
        """
        for field in fields(
            UserPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            setattr(
                user,
                field.name,
                value,
            )

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def replace_profile(
            self,
            user: User,
            *,
            username: str,
            display_name: str | None,
            email: str | None,
            updated_by: str | None = None,
    ) -> User:
        """替换用户资料

        参数：
            user: 用户对象
            username: 新用户名
            display_name: 新显示名称
            email: 新邮箱
            updated_by: 更新用户 ID（可选）

        返回：
            更新后的用户对象
        """
        user.username = username
        user.display_name = display_name
        user.email = email

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def update_password(
            self,
            user: User,
            *,
            password_hash: str,
            changed_at: datetime | None = None,
            updated_by: str | None = None,
    ) -> User:
        """更新密码哈希

        参数：
            user: 用户对象
            password_hash: 新密码哈希
            changed_at: 密码修改时间（可选）
            updated_by: 更新用户 ID（可选）

        返回：
            更新后的用户对象
        """
        user.password_hash = password_hash
        user.password_changed_at = (
            changed_at
            or datetime.now(
                timezone.utc
            )
        )

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def activate_user(
            self,
            user: User,
            *,
            updated_by: str | None = None,
    ) -> User:
        """启用用户

        参数：
            user: 用户对象
            updated_by: 更新用户 ID（可选）

        返回：
            启用后的用户对象
        """
        user.status = str(
            UserStatus.ACTIVE
        )
        user.failed_login_count = 0
        user.locked_until = None

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def disable_user(
            self,
            user: User,
            *,
            updated_by: str | None = None,
    ) -> User:
        """停用用户

        参数：
            user: 用户对象
            updated_by: 更新用户 ID（可选）

        返回：
            停用后的用户对象
        """
        user.status = str(
            UserStatus.DISABLED
        )
        user.locked_until = None

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def mark_deleted(
            self,
            user: User,
            *,
            deleted_by: str,
            deletion_reason: str | None = None,
            deleted_at: datetime | None = None,
    ) -> User:
        """逻辑删除用户

        删除后用户保持 disabled 状态，保留身份和审计关联信息。

        参数：
            user: 用户对象
            deleted_by: 删除操作人
            deletion_reason: 删除原因（可选）
            deleted_at: 删除时间（可选）

        返回：
            逻辑删除后的用户对象
        """
        if getattr(
                user,
                "deleted_at",
                None,
        ) is not None:
            return user

        timestamp = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        user.status = str(
            UserStatus.DISABLED
        )
        user.locked_until = None
        user.deleted_at = timestamp
        user.deleted_by = deleted_by
        user.deletion_reason = deletion_reason
        user.updated_by = deleted_by

        return user

    def restore_user(
            self,
            user: User,
            *,
            restored_at: datetime | None = None,
            restored_by: str | None = None,
    ) -> User:
        """恢复已逻辑删除的用户

        恢复后用户重新处于 active 状态，更新创建时间，
        并清除原删除和锁定信息。

        参数：
            user: 用户对象
            restored_at: 恢复时间（可选）
            restored_by: 恢复操作人（可选）

        返回：
            恢复后的用户对象
        """
        user.status = str(
            UserStatus.ACTIVE
        )
        user.created_at = (
            restored_at
            if restored_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        user.failed_login_count = 0
        user.locked_until = None
        user.deleted_at = None
        user.deleted_by = None
        user.deletion_reason = None

        if restored_by is not None:
            user.updated_by = restored_by

        return user

    def lock_user(
            self,
            user: User,
            *,
            locked_until: datetime | None = None,
            updated_by: str | None = None,
    ) -> User:
        """锁定用户

        参数：
            user: 用户对象
            locked_until: 临时锁定截止时间（可选）
            updated_by: 更新用户 ID（可选）

        返回：
            锁定后的用户对象
        """
        user.status = str(
            UserStatus.LOCKED
        )
        user.locked_until = locked_until

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def unlock_user(
            self,
            user: User,
            *,
            updated_by: str | None = None,
    ) -> User:
        """解锁用户

        参数：
            user: 用户对象
            updated_by: 更新用户 ID（可选）

        返回：
            解锁后的用户对象
        """
        user.status = str(
            UserStatus.ACTIVE
        )
        user.failed_login_count = 0
        user.locked_until = None

        if updated_by is not None:
            user.updated_by = updated_by

        return user

    def record_login_success(
            self,
            user: User,
            *,
            logged_in_at: datetime | None = None,
    ) -> User:
        """记录登录成功

        参数：
            user: 用户对象
            logged_in_at: 登录时间（可选）

        返回：
            更新后的用户对象
        """
        user.failed_login_count = 0
        user.last_login_at = (
            logged_in_at
            or datetime.now(
                timezone.utc
            )
        )

        return user

    def record_login_failure(
            self,
            user: User,
    ) -> User:
        """记录登录失败

        参数：
            user: 用户对象

        返回：
            更新后的用户对象
        """
        user.failed_login_count += 1

        return user
