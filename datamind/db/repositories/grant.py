"""角色授予仓储

提供用户角色关系的查询、创建、撤销和重新激活能力。

核心功能：
  - get_grant: 获取单个角色授予记录
  - list_grants: 获取角色授予列表
  - list_active_grants: 获取有效角色授予列表
  - create_grant: 创建角色授予记录
  - activate_grant: 重新激活角色授予
  - revoke_grant: 撤销角色授予

使用示例：
  from datamind.auth.enums import GrantStatus
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.grant import GrantRepository

  async with UnitOfWork() as uow:
      repo = GrantRepository(uow.session)

      grant = repo.create_grant(
          grant_id="grt_0123456789abcdef",
          user_id="usr_0123456789abcdef",
          role_id="rol_0123456789abcdef",
          status=GrantStatus.ACTIVE,
          granted_by="usr_fedcba9876543210",
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.auth.enums import GrantStatus
from datamind.db.models.grants import Grant
from datamind.db.repositories.base import BaseRepository


class GrantRepository(BaseRepository):
    """角色授予仓储"""

    async def get_grant(
            self,
            *,
            grant_id: str | None = None,
            user_id: str | None = None,
            role_id: str | None = None,
    ) -> Grant | None:
        """获取单个角色授予记录

        参数：
            grant_id: 授予 ID（可选）
            user_id: 用户 ID（可选）
            role_id: 角色 ID（可选）

        返回：
            角色授予对象，不存在时返回 None

        异常：
            ValueError: 查询条件不合法
        """
        by_grant_id = grant_id is not None
        by_user_role = (
            user_id is not None
            and role_id is not None
        )

        if by_grant_id == by_user_role:
            raise ValueError(
                "必须提供 grant_id，"
                "或者同时提供 user_id 和 role_id"
            )

        stmt = select(
            Grant
        )

        if grant_id is not None:
            stmt = stmt.where(
                Grant.grant_id == grant_id
            )
        else:
            stmt = stmt.where(
                Grant.user_id == user_id,
                Grant.role_id == role_id,
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_grants(
            self,
            *,
            user_id: str | None = None,
            role_id: str | None = None,
            status: GrantStatus | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Grant]:
        """获取角色授予列表

        参数：
            user_id: 用户 ID（可选）
            role_id: 角色 ID（可选）
            status: 授予状态（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            角色授予列表，按授予时间倒序排列
        """
        stmt = select(
            Grant
        )

        if user_id is not None:
            stmt = stmt.where(
                Grant.user_id == user_id
            )

        if role_id is not None:
            stmt = stmt.where(
                Grant.role_id == role_id
            )

        if status is not None:
            stmt = stmt.where(
                Grant.status == str(
                    status
                )
            )

        stmt = stmt.order_by(
            Grant.granted_at.desc()
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

    async def list_active_grants(
            self,
            *,
            user_id: str | None = None,
            role_id: str | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Grant]:
        """获取有效角色授予列表

        参数：
            user_id: 用户 ID（可选）
            role_id: 角色 ID（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            有效角色授予列表
        """
        return await self.list_grants(
            user_id=user_id,
            role_id=role_id,
            status=GrantStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_grant(
            self,
            *,
            grant_id: str,
            user_id: str,
            role_id: str,
            status: GrantStatus = GrantStatus.ACTIVE,
            granted_by: str | None = None,
            granted_at: datetime | None = None,
    ) -> Grant:
        """创建角色授予记录

        参数：
            grant_id: 授予 ID
            user_id: 用户 ID
            role_id: 角色 ID
            status: 授予状态
            granted_by: 授予用户 ID（可选）
            granted_at: 授予时间（可选）

        返回：
            创建后的角色授予对象
        """
        new_grant = Grant(
            grant_id=grant_id,
            user_id=user_id,
            role_id=role_id,
            status=str(
                status
            ),
        )

        if granted_by is not None:
            new_grant.granted_by = granted_by

        if granted_at is not None:
            new_grant.granted_at = granted_at

        self.add(
            new_grant
        )

        return new_grant

    def activate_grant(
            self,
            grant: Grant,
            *,
            granted_by: str | None = None,
            granted_at: datetime | None = None,
    ) -> Grant:
        """重新激活角色授予

        参数：
            grant: 角色授予对象
            granted_by: 授予用户 ID（可选）
            granted_at: 授予时间（可选）

        返回：
            重新激活后的角色授予对象
        """
        grant.status = str(
            GrantStatus.ACTIVE
        )
        grant.granted_by = granted_by
        grant.granted_at = (
            granted_at
            or datetime.now(
                timezone.utc
            )
        )
        grant.revoked_by = None
        grant.revoked_at = None

        return grant

    def revoke_grant(
            self,
            grant: Grant,
            *,
            revoked_by: str | None = None,
            revoked_at: datetime | None = None,
    ) -> Grant:
        """撤销角色授予

        参数：
            grant: 角色授予对象
            revoked_by: 撤销用户 ID（可选）
            revoked_at: 撤销时间（可选）

        返回：
            撤销后的角色授予对象
        """
        grant.status = str(
            GrantStatus.REVOKED
        )
        grant.revoked_by = revoked_by
        grant.revoked_at = (
            revoked_at
            or datetime.now(
                timezone.utc
            )
        )

        return grant
