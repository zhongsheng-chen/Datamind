"""组织目录仓储.

提供机构与部门查询，以及用户组织路径和身份快照的生成能力。

核心功能：
  - get_organization: 获取单个机构
  - get_department: 获取单个部门
  - list_organizations: 获取机构列表
  - list_departments: 获取部门列表
  - catalog: 批量读取组织目录
  - path: 生成完整部门路径
  - profile: 生成用户身份与组织归属快照

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.organization import OrganizationRepository

  async with UnitOfWork() as uow:
      repository = OrganizationRepository(
          uow.session
      )
      catalog = await repository.catalog()
"""

from collections.abc import Iterable
from typing import (
    Any,
    TypedDict,
)

from sqlalchemy import (
    func,
    select,
    text,
)

from datamind.db.models.departments import Department
from datamind.db.models.organizations import Organization
from datamind.db.models.users import User
from datamind.db.repositories.base import BaseRepository


class DepartmentPathItem(TypedDict):
    """部门路径条目."""

    department_id: str
    code: str | None
    name: str


class OrganizationRepository(BaseRepository):
    """组织目录仓储."""

    async def lock_organization_order(
            self,
    ) -> None:
        """串行化机构新增与排序，包含当前尚无机构的情况."""
        await self.session.execute(
            text(
                "SELECT pg_advisory_xact_lock(1684108385, 1)",
            ),
        )

    async def get_organization(
            self,
            organization_id: str,
            *,
            lock: bool = False,
    ) -> Organization | None:
        """按内部 ID 获取机构.

        参数：
            organization_id: 机构 ID
            lock: 是否锁定机构行，用于串行化同机构的部门结构变更

        返回：
            机构对象，不存在时返回 None
        """
        query = select(
            Organization,
        ).where(
            Organization.organization_id == organization_id,
        )

        if lock:
            query = query.with_for_update().execution_options(
                populate_existing=True,
            )

        result = await self.session.execute(
            query,
        )
        return result.scalar_one_or_none()

    async def get_department(
            self,
            department_id: str,
            *,
            lock: bool = False,
    ) -> Department | None:
        """按内部 ID 获取部门.

        参数：
            department_id: 部门 ID
            lock: 是否锁定部门行，防止删除期间新增引用

        返回：
            部门对象，不存在时返回 None
        """
        query = select(
            Department,
        ).where(
            Department.department_id == department_id,
        )

        if lock:
            query = query.with_for_update().execution_options(
                populate_existing=True,
            )

        result = await self.session.execute(
            query,
        )
        return result.scalar_one_or_none()

    async def list_organizations(
            self,
    ) -> list[Organization]:
        """按显示顺序查询全部机构.

        返回：
            机构对象列表
        """
        result = await self.session.execute(
            select(
                Organization,
            ).order_by(
                Organization.sort_order,
                Organization.code.nulls_last(),
                Organization.organization_id,
            ),
        )
        return list(
            result.scalars().all(),
        )

    async def list_departments(
            self,
            organization_id: str | None = None,
    ) -> list[Department]:
        """按显示顺序查询部门.

        参数：
            organization_id: 所属机构 ID，未指定时查询全部机构

        返回：
            部门对象列表
        """
        query = select(
            Department,
        ).order_by(
            Department.sort_order,
            Department.code.nulls_last(),
            Department.department_id,
        ).execution_options(
            populate_existing=True,
        )

        if organization_id is not None:
            query = query.where(
                Department.organization_id == organization_id,
            )

        result = await self.session.execute(
            query,
        )
        return list(
            result.scalars().all(),
        )

    async def organization_references(
            self,
            organization_id: str,
    ) -> tuple[int, int]:
        """返回机构关联用户和所属部门数量，含停用用户和部门."""
        result = await self.session.execute(
            select(
                select(
                    func.count(),
                ).select_from(
                    User,
                ).where(
                    User.organization_id == organization_id,
                ).scalar_subquery(),
                select(
                    func.count(),
                ).select_from(
                    Department,
                ).where(
                    Department.organization_id == organization_id,
                ).scalar_subquery(),
            ),
        )
        users, departments = result.one()
        return int(users), int(departments)

    async def department_references(
            self,
            department_id: str,
    ) -> tuple[int, int]:
        """返回部门直接关联用户和直属子部门数量，含停用记录."""
        result = await self.session.execute(
            select(
                select(
                    func.count(),
                ).select_from(
                    User,
                ).where(
                    User.department_id == department_id,
                ).scalar_subquery(),
                select(
                    func.count(),
                ).select_from(
                    Department,
                ).where(
                    Department.parent_id == department_id,
                ).scalar_subquery(),
            ),
        )
        users, children = result.one()
        return int(users), int(children)

    async def catalog(
            self,
    ) -> "OrganizationCatalog":
        """批量读取组织目录，避免逐用户查询部门路径.

        返回：
            包含机构和部门索引的目录
        """
        organizations = await self.list_organizations()
        departments = await self.list_departments()
        return OrganizationCatalog(
            organizations,
            departments,
        )


class OrganizationCatalog:
    """组织目录索引.

    属性：
        organizations: 机构 ID 与机构对象的映射
        departments: 部门 ID 与部门对象的映射
    """

    def __init__(
            self,
            organizations: Iterable[Organization],
            departments: Iterable[Department],
    ) -> None:
        """构建组织目录索引.

        参数：
            organizations: 机构对象集合
            departments: 部门对象集合
        """
        self.organizations: dict[str, Organization] = {
            item.organization_id: item
            for item in organizations
        }
        self.departments: dict[str, Department] = {
            item.department_id: item
            for item in departments
        }

    def path(
            self,
            department_id: str | None,
    ) -> list[DepartmentPathItem]:
        """从根部门到指定部门生成路径.

        参数：
            department_id: 部门 ID，为空时返回空路径

        返回：
            包含各级部门 ID、编码和名称的有序列表

        异常：
            ValueError: 部门路径不完整或存在循环
        """
        path: list[DepartmentPathItem] = []
        seen = set()

        while department_id is not None:
            if department_id in seen:
                raise ValueError(
                    "部门层级存在循环",
                )
            seen.add(
                department_id,
            )
            department = self.departments.get(
                department_id,
            )
            if department is None:
                raise ValueError(
                    "部门路径不完整",
                )
            path.append(
                {
                    "department_id": department.department_id,
                    "code": department.code,
                    "name": department.name,
                },
            )
            department_id = department.parent_id

        return list(
            reversed(path),
        )

    def department_available(
            self,
            department_id: str,
    ) -> bool:
        """机构与部门路径上所有节点均启用时，才可新增关联."""
        item = self.departments[department_id]
        organization = self.organizations[item.organization_id]
        return (
            organization.is_active is not False
            and all(
                self.departments[node["department_id"]].is_active is not False
                for node in self.path(department_id)
            )
        )

    def profile(
            self,
            user: User,
    ) -> dict[str, Any]:
        """生成独立的用户身份与组织归属快照.

        参数：
            user: 用户对象

        返回：
            用户稳定标识、工号、机构名称和完整部门路径
        """
        organization_id: str | None = getattr(
            user,
            "organization_id",
            None,
        )
        department_id: str | None = getattr(
            user,
            "department_id",
            None,
        )
        organization: Organization | None = None

        if organization_id is not None:
            organization = self.organizations.get(
                organization_id,
            )

        path = self.path(
            department_id,
        )
        return {
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "employee_number": getattr(
                user,
                "employee_number",
                None,
            ),
            "organization_id": organization_id,
            "organization_code": (
                organization.code
                if organization is not None
                else None
            ),
            "organization_name": (
                organization.name
                if organization is not None
                else None
            ),
            "department_id": department_id,
            "department_path": path,
            "department_name": path[-1]["name"] if path else None,
        }
