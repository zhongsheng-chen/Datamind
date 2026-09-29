"""角色仓储.

提供角色的查询、创建、更新、权限配置和状态管理能力。

核心功能：
  - get_role: 获取单个角色
  - list_roles: 获取角色列表
  - list_active_roles: 获取活跃角色列表
  - create_role: 创建角色
  - update_role: 更新角色基础信息
  - replace_permissions: 替换角色权限
  - activate_role: 启用角色
  - deactivate_role: 停用角色
  - mark_deleted: 逻辑删除角色
  - restore_role: 恢复角色

使用示例：
  from datamind.auth.enums import RoleStatus
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.role import RoleRepository

  async with UnitOfWork() as uow:
      repo = RoleRepository(uow.session)

      role = repo.create_role(
          role_id="rol_0123456789abcdef",
          name="admin",
          description="系统管理员",
          permissions=[
              "model.*",
              "deploy.*",
              "experiment.*",
              "user.*",
          ],
          status=RoleStatus.ACTIVE,
          created_by="usr_0123456789abcdef",
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

from datamind.auth.enums import RoleStatus
from datamind.db.models.roles import Role
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class RolePatch:
    """角色更新结构.

    注意：
        不允许通过 patch 修改 permissions 和 status，
        分别由权限替换方法和生命周期方法控制。

    属性：
        name: 角色名称
        description: 角色说明
    """

    name: str | None = None
    description: str | None = None


class RoleRepository(BaseRepository):
    """角色仓储."""

    async def get_role(
            self,
            *,
            role_id: str | None = None,
            name: str | None = None,
    ) -> Role | None:
        """获取单个角色.

        参数：
            role_id: 角色 ID（可选）
            name: 角色名称（可选）

        返回：
            角色对象，不存在时返回 None

        异常：
            ValueError: 未提供查询条件或同时提供多个查询条件
        """
        conditions = [
            value is not None
            for value in (
                role_id,
                name,
            )
        ]

        if sum(conditions) != 1:
            raise ValueError(
                "role_id、name 必须且只能提供一个"
            )

        stmt = select(
            Role
        )

        if role_id is not None:
            stmt = stmt.where(
                Role.role_id == role_id
            )
        else:
            stmt = stmt.where(
                Role.name == name
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_roles(
            self,
            *,
            status: RoleStatus | None = None,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Role]:
        """获取角色列表.

        参数：
            status: 角色状态（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            角色列表，按创建时间倒序排列
        """
        stmt = select(
            Role
        )

        if status is not None:
            stmt = stmt.where(
                Role.status == str(
                    status
                )
            )

        stmt = stmt.order_by(
            Role.created_at.desc()
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

    async def list_active_roles(
            self,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Role]:
        """获取活跃角色列表.

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            活跃角色列表，按创建时间倒序排列
        """
        return await self.list_roles(
            status=RoleStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_role(
            self,
            *,
            role_id: str,
            name: str,
            description: str | None = None,
            permissions: list[str] | None = None,
            status: RoleStatus = RoleStatus.ACTIVE,
            created_by: str | None = None,
    ) -> Role:
        """创建角色.

        参数：
            role_id: 角色 ID
            name: 角色名称
            description: 角色说明（可选）
            permissions: 权限标识列表（可选）
            status: 角色状态
            created_by: 创建用户 ID（可选）

        返回：
            创建后的角色对象
        """
        new_role = Role(
            role_id=role_id,
            name=name,
            permissions=permissions,
            status=str(
                status
            ),
        )

        if description is not None:
            new_role.description = description

        if created_by is not None:
            new_role.created_by = created_by

        self.add(
            new_role
        )

        return new_role

    def update_role(
            self,
            role: Role,
            *,
            patch: RolePatch,
            updated_by: str | None = None,
    ) -> Role:
        """更新角色基础信息.

        参数：
            role: 角色对象
            patch: 角色更新内容
            updated_by: 更新用户 ID（可选）

        返回：
            更新后的角色对象
        """
        for field in fields(
            RolePatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            setattr(
                role,
                field.name,
                value,
            )

        if updated_by is not None:
            role.updated_by = updated_by

        return role

    def replace_permissions(
            self,
            role: Role,
            *,
            permissions: list[str] | None,
            updated_by: str | None = None,
    ) -> Role:
        """替换角色权限.

        参数：
            role: 角色对象
            permissions: 新权限标识列表，为 None 时清空权限
            updated_by: 更新用户 ID（可选）

        返回：
            更新后的角色对象
        """
        role.permissions = permissions

        if updated_by is not None:
            role.updated_by = updated_by

        return role

    def activate_role(
            self,
            role: Role,
            *,
            updated_by: str | None = None,
    ) -> Role:
        """启用角色.

        参数：
            role: 角色对象
            updated_by: 更新用户 ID（可选）

        返回：
            启用后的角色对象
        """
        role.status = str(
            RoleStatus.ACTIVE
        )

        if updated_by is not None:
            role.updated_by = updated_by

        return role

    def deactivate_role(
            self,
            role: Role,
            *,
            updated_by: str | None = None,
    ) -> Role:
        """停用角色.

        参数：
            role: 角色对象
            updated_by: 更新用户 ID（可选）

        返回：
            停用后的角色对象
        """
        role.status = str(
            RoleStatus.INACTIVE
        )

        if updated_by is not None:
            role.updated_by = updated_by

        return role

    def replace_description(
            self,
            role: Role,
            *,
            description: str | None,
            updated_by: str | None = None,
    ) -> Role:
        """替换角色描述，允许清空现有描述."""
        role.description = description

        if updated_by is not None:
            role.updated_by = updated_by

        return role

    def mark_deleted(
            self,
            role: Role,
            *,
            deleted_by: str,
            deletion_reason: str | None = None,
            deleted_at: datetime | None = None,
    ) -> Role:
        """逻辑删除角色.

        删除后角色保持 inactive 状态，保留授权和审计关联信息。

        参数：
            role: 角色对象
            deleted_by: 删除操作人
            deletion_reason: 删除原因（可选）
            deleted_at: 删除时间（可选）

        返回：
            逻辑删除后的角色对象
        """
        if getattr(
                role,
                "deleted_at",
                None,
        ) is not None:
            return role

        role.status = str(
            RoleStatus.INACTIVE
        )
        role.deleted_at = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        role.deleted_by = deleted_by
        role.deletion_reason = deletion_reason
        role.updated_by = deleted_by

        return role

    def restore_role(
            self,
            role: Role,
            *,
            restored_at: datetime | None = None,
            restored_by: str | None = None,
    ) -> Role:
        """恢复已逻辑删除的角色.

        恢复后角色重新处于 active 状态，
        将创建时间更新为本次恢复时间，
        并清除原删除信息。

        参数：
            role: 角色对象
            restored_at: 恢复时间（可选）
            restored_by: 恢复操作人（可选）

        返回：
            恢复后的角色对象
        """
        role.status = str(
            RoleStatus.ACTIVE
        )
        role.created_at = (
            restored_at
            if restored_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        role.deleted_at = None
        role.deleted_by = None
        role.deletion_reason = None

        if restored_by is not None:
            role.updated_by = restored_by

        return role
