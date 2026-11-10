"""组织管理服务.

提供机构与部门的创建、修改、启停、删除和查询，以及用户组织归属校验能力。

核心功能：
  - catalog: 查询机构、部门及其完整路径
  - move: 调整机构或部门的同级显示顺序
  - save_organization: 创建或修改机构
  - save_department: 创建或修改部门
  - delete_organization: 删除无关联用户和部门的机构
  - delete_department: 删除无关联用户和下级部门的部门
  - set_organization_active: 停用或启用机构
  - set_department_active: 停用或启用部门
  - validate_profile: 校验用户所属机构与部门
  - attach_user_profiles: 批量补充用户的组织名称和部门路径

使用示例：
  from datamind.services.organization import OrganizationService

  organization = await OrganizationService().save_organization(
      code="HQ",
      name="总行",
  )
"""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.audit import AuditRecorder
from datamind.db.core import UnitOfWork
from datamind.db.models.departments import Department
from datamind.db.models.organizations import Organization
from datamind.db.models.users import User
from datamind.db.repositories.organization import (
    OrganizationCatalog,
    OrganizationRepository,
)
from datamind.services.errors import IdentityConflictError
from datamind.utils import generate_random_id


class _Unset:
    """区分未指定编码和显式清空编码."""


_UNSET = _Unset()


class OrganizationService:
    """组织管理服务."""

    def __init__(
            self,
            *,
            audit_context: dict[str, Any] | None = None,
    ) -> None:
        """初始化组织管理服务.

        参数：
            audit_context: 可信操作上下文，包含已认证操作人及请求标识
        """
        self.audit_context = audit_context

    @staticmethod
    def _required_text(
            value: str,
            label: str,
            maximum: int,
    ) -> str:
        """校验并规范化必填文本.

        参数：
            value: 待校验的文本
            label: 错误消息中的字段名称
            maximum: 允许的最大字符数

        返回：
            去除首尾空白后的文本

        异常：
            ValueError: 输入不是字符串、内容为空或长度超过上限
        """
        if not isinstance(
                value,
                str,
        ):
            raise ValueError(
                f"{label}必须是字符串",
            )
        normalized = value.strip()
        if not normalized:
            raise ValueError(
                f"{label}不能为空",
            )
        if len(normalized) > maximum:
            raise ValueError(
                f"{label}长度不能超过 {maximum}",
            )
        return normalized

    @classmethod
    def _optional_code(
            cls,
            value: str | None | _Unset,
    ) -> str | None:
        """规范化可选业务编码.

        参数：
            value: 业务编码，允许未指定、None 或空字符串

        返回：
            去除首尾空白后的编码；未指定、None 或空字符串返回 None

        异常：
            ValueError: 编码不是字符串或长度超过 64 个字符
        """
        if isinstance(value, _Unset) or value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                "业务编码必须是字符串",
            )
        normalized = value.strip()
        if not normalized:
            return None
        return cls._required_text(
            normalized,
            "业务编码",
            64,
        )

    @staticmethod
    def organization_item(
            item: Organization,
    ) -> dict[str, Any]:
        """生成机构信息.

        参数：
            item: 机构对象

        返回：
            机构 ID、业务编码、名称和启用状态
        """
        return {
            "organization_id": item.organization_id,
            "code": item.code,
            "name": item.name,
            "sort_order": item.sort_order or 0,
            "is_active": item.is_active is not False,
        }

    @staticmethod
    def department_item(
            item: Department,
            catalog: OrganizationCatalog,
    ) -> dict[str, Any]:
        """生成部门信息及完整路径.

        参数：
            item: 部门对象
            catalog: 当前组织目录，用于计算部门路径和可用状态

        返回：
            部门 ID、所属机构、上级部门、业务编码、名称、启用状态、可用状态和完整路径

        说明：
            可用状态取决于所属机构和路径上各级部门的启用状态。
        """
        return {
            "department_id": item.department_id,
            "organization_id": item.organization_id,
            "parent_id": item.parent_id,
            "code": item.code,
            "name": item.name,
            "sort_order": item.sort_order or 0,
            "is_active": item.is_active is not False,
            "is_available": catalog.department_available(item.department_id),
            "path": catalog.path(
                item.department_id,
            ),
        }

    async def catalog(
            self,
    ) -> dict[str, list[dict[str, Any]]]:
        """查询组织目录.

        返回：
            机构列表和部门列表，包含停用记录；部门信息包含完整路径和可用状态
        """
        async with UnitOfWork() as uow:
            catalog = await OrganizationRepository(
                uow.session,
            ).catalog()
            children: dict[str | None, list[Department]] = {}
            for item in catalog.departments.values():
                children.setdefault(item.parent_id, []).append(item)
            ordered = []
            stack = [item for item in reversed(list(catalog.departments.values())) if item.parent_id is None]
            while stack:
                item = stack.pop()
                ordered.append(item)
                stack.extend(reversed(children.get(item.department_id, [])))
            return {
                "organizations": [
                    self.organization_item(item)
                    for item in catalog.organizations.values()
                ],
                "departments": [
                    self.department_item(
                        item,
                        catalog,
                    )
                    for item in ordered
                ],
            }

    async def move(
            self,
            *,
            resource: str,
            target_id: str,
            direction: str,
    ) -> dict[str, Any]:
        """在事务内调整同级顺序，提交成功后记录排序审计.

        参数：
            resource: organization 或 department
            target_id: 待移动的机构或部门 ID
            direction: up 或 down

        返回：
            调整后的记录

        异常：
            ValueError: 参数无效、记录不存在或已到达同级边界
        """
        if resource not in ("organization", "department") or direction not in ("up", "down"):
            raise ValueError("排序参数无效")
        async with UnitOfWork() as uow:
            repo = OrganizationRepository(uow.session)
            siblings: list[Organization | Department]
            catalog: OrganizationCatalog | None = None

            if resource == "organization":
                await repo.lock_organization_order()
                siblings = [
                    item
                    for item in await repo.list_organizations()
                ]
                id_field = "organization_id"
            else:
                target = await repo.get_department(target_id)
                if target is None:
                    raise ValueError("部门不存在")
                await repo.get_organization(target.organization_id, lock=True)
                department_catalog: OrganizationCatalog = await repo.catalog()
                catalog = department_catalog
                target = department_catalog.departments.get(target_id)
                if target is None:
                    raise ValueError("部门不存在")
                siblings = [
                    item
                    for item in department_catalog.departments.values()
                    if (
                        item.organization_id == target.organization_id
                        and item.parent_id == target.parent_id
                    )
                ]
                id_field = "department_id"
            index = next((i for i, item in enumerate(siblings) if getattr(item, id_field) == target_id), None)
            if index is None:
                raise ValueError("机构或部门不存在")
            destination = index + (-1 if direction == "up" else 1)
            if not 0 <= destination < len(siblings):
                raise ValueError("已到达同级排序边界")
            before = {"sibling_ids": [getattr(item, id_field) for item in siblings]}
            siblings[index], siblings[destination] = siblings[destination], siblings[index]
            for position, item in enumerate(siblings, 1):
                item.sort_order = position
            await repo.flush()
            moved_item = siblings[destination]
            if isinstance(moved_item, Organization):
                result = self.organization_item(moved_item)
            else:
                assert catalog is not None
                result = self.department_item(moved_item, catalog)
            after = {"sibling_ids": [getattr(item, id_field) for item in siblings]}
        await self._audit(resource, target_id, before, after, operation="reorder")
        return result

    async def save_organization(
            self,
            *,
            name: str,
            code: str | None | _Unset = _UNSET,
            organization_id: str | None = None,
    ) -> dict[str, Any]:
        """创建或修改机构.

        参数：
            name: 机构名称
            code: 业务编码；修改时省略则保留原值，传入 None 或空字符串可清空
            organization_id: 机构 ID，未指定时创建新机构

        返回：
            保存后的机构信息，包含 ID、业务编码、名称和启用状态

        异常：
            ValueError: 输入无效或指定机构不存在
            IdentityConflictError: 机构业务编码已被使用
        """
        normalized_code = self._optional_code(
            code,
        )
        name = self._required_text(
            name,
            "机构名称",
            128,
        )
        before = None

        try:
            async with UnitOfWork() as uow:
                repo = OrganizationRepository(
                    uow.session,
                )
                await repo.lock_organization_order()
                if organization_id is None:
                    item = Organization(
                        organization_id=generate_random_id(
                            prefix="org",
                        ),
                        name=name,
                        sort_order=max(
                            (entry.sort_order or 0 for entry in await repo.list_organizations()),
                            default=0,
                        ) + 1,
                    )
                    if normalized_code is not None:
                        item.code = normalized_code

                    repo.add(
                        item,
                    )
                else:
                    item = await repo.get_organization(
                        organization_id,
                        lock=True,
                    )
                    if item is None:
                        raise ValueError(
                            "机构不存在",
                        )
                    before = self.organization_item(
                        item,
                    )
                    if not isinstance(code, _Unset):
                        item.code = normalized_code
                    item.name = name

                await repo.flush()
                result = self.organization_item(
                    item,
                )
        except IntegrityError as error:
            raise IdentityConflictError(
                "机构编码已存在",
            ) from error

        await self._audit(
            "organization",
            result["organization_id"],
            before,
            result,
        )
        return result

    async def save_department(
            self,
            *,
            organization_id: str,
            name: str,
            code: str | None | _Unset = _UNSET,
            parent_id: str | None = None,
            department_id: str | None = None,
    ) -> dict[str, Any]:
        """创建或修改部门.

        参数：
            organization_id: 所属机构 ID，已有部门不能更换机构
            name: 部门名称
            code: 业务编码；修改时省略则保留原值，传入 None 或空字符串可清空
            parent_id: 上级部门 ID，未指定或为 None 时作为根部门
            department_id: 部门 ID，未指定时创建新部门

        返回：
            保存后的部门信息，包含完整路径、启用状态和可用状态

        异常：
            ValueError: 机构、部门或上级部门无效，层级存在循环，或向停用组织新增关联
            IdentityConflictError: 同级部门名称或机构内业务编码重复，或组织归属冲突
        """
        normalized_code = self._optional_code(
            code,
        )
        name = self._required_text(
            name,
            "部门名称",
            128,
        )

        try:
            async with UnitOfWork() as uow:
                repo = OrganizationRepository(
                    uow.session,
                )
                # 同机构的部门变更共用机构行锁，避免并发移动形成循环。
                organization = await repo.get_organization(
                    organization_id,
                    lock=True,
                )
                if organization is None:
                    raise ValueError(
                        "机构不存在",
                    )
                catalog = await repo.catalog()
                self._validate_parent(
                    catalog,
                    organization_id,
                    parent_id,
                    department_id,
                )
                item, before = self._prepare_department(
                    catalog,
                    organization_id,
                    department_id,
                )
                new_parent = before is None or item.parent_id != parent_id
                if before is None and not organization.is_active:
                    raise ValueError(
                        "机构已停用，不能新增部门",
                    )
                if new_parent and parent_id and not catalog.department_available(parent_id):
                    raise ValueError(
                        "上级部门或所属机构已停用，不能新增关联",
                    )
                if before is None:
                    repo.add(
                        item,
                    )
                if before is None or not isinstance(code, _Unset):
                    item.code = normalized_code
                if new_parent:
                    item.sort_order = max(
                        (entry.sort_order or 0 for entry in catalog.departments.values()
                         if entry.organization_id == organization_id and entry.parent_id == parent_id
                         and entry.department_id != item.department_id),
                        default=0,
                    ) + 1
                item.name = name
                item.parent_id = parent_id
                catalog.departments[item.department_id] = item
                await repo.flush()
                result = self.department_item(
                    item,
                    catalog,
                )
        except IntegrityError as error:
            raise IdentityConflictError(
                "部门名称或编码已存在，或组织归属冲突",
            ) from error

        await self._audit(
            "department",
            result["department_id"],
            before,
            result,
        )
        return result

    async def delete_organization(
            self,
            *,
            organization_id: str,
    ) -> dict[str, Any]:
        """删除没有关联用户和所属部门的机构.

        参数：
            organization_id: 待删除的机构 ID

        返回：
            删除前的机构信息

        异常：
            ValueError: 机构不存在
            IdentityConflictError: 机构仍有关联用户或所属部门，包括停用记录
        """
        message = "机构仍关联用户或部门，请先调整用户归属并删除所属部门"

        try:
            async with UnitOfWork() as uow:
                repo = OrganizationRepository(
                    uow.session,
                )
                item = await repo.get_organization(
                    organization_id,
                    lock=True,
                )
                if item is None:
                    raise ValueError(
                        "机构不存在",
                    )
                users, departments = await repo.organization_references(organization_id)

                if users or departments:
                    raise IdentityConflictError(
                        f"机构仍关联 {users} 名用户、{departments} 个部门，请先解除关联",
                    )

                before = self.organization_item(item)
                await repo.delete(item)
                await repo.flush()
        except IntegrityError as error:
            # 外键约束同时保护检查之后新增的并发引用。
            raise IdentityConflictError(
                message,
            ) from error

        await self._audit(
            "organization",
            organization_id,
            before,
            None,
        )
        return before

    async def delete_department(
            self,
            *,
            department_id: str,
    ) -> dict[str, Any]:
        """删除没有关联用户和直属下级部门的部门.

        参数：
            department_id: 待删除的部门 ID

        返回：
            删除前的部门信息，包含完整路径

        异常：
            ValueError: 部门不存在
            IdentityConflictError: 部门仍有关联用户或直属下级部门，包括停用记录
        """
        message = "部门仍关联用户或下级部门，请先调整用户归属并移动或删除下级部门"

        try:
            async with UnitOfWork() as uow:
                repo = OrganizationRepository(
                    uow.session,
                )
                item = await repo.get_department(department_id)
                if item is None:
                    raise ValueError(
                        "部门不存在",
                    )
                await repo.get_organization(
                    item.organization_id,
                    lock=True,
                )
                item = await repo.get_department(
                    department_id,
                    lock=True,
                )
                if item is None:
                    raise ValueError(
                        "部门不存在",
                    )
                users, children = await repo.department_references(department_id)

                if users or children:
                    raise IdentityConflictError(
                        f"部门仍关联 {users} 名用户、{children} 个直属下级部门，请先解除关联",
                    )

                before = self.department_item(
                    item,
                    await repo.catalog(),
                )
                await repo.delete(item)
                await repo.flush()
        except IntegrityError as error:
            raise IdentityConflictError(
                message,
            ) from error

        await self._audit(
            "department",
            department_id,
            before,
            None,
        )
        return before

    async def set_organization_active(
            self,
            *,
            organization_id: str,
            is_active: bool,
    ) -> dict[str, Any]:
        """设置机构的启用状态.

        参数：
            organization_id: 机构 ID
            is_active: True 表示启用，False 表示停用

        返回：
            更新后的机构信息

        异常：
            ValueError: 机构不存在

        说明：
            停用后保留已有用户归属，禁止向该机构及其下级部门新增关联。
            机构启停不会修改下级部门各自的启用状态。
        """
        async with UnitOfWork() as uow:
            repo = OrganizationRepository(
                uow.session,
            )
            item = await repo.get_organization(
                organization_id,
                lock=True,
            )
            if item is None:
                raise ValueError(
                    "机构不存在",
                )

            before = self.organization_item(item)
            item.is_active = is_active
            await repo.flush()
            result = self.organization_item(item)

        await self._audit(
            "organization",
            organization_id,
            before,
            result,
            operation="enable" if is_active else "disable",
        )
        return result

    async def set_department_active(
            self,
            *,
            department_id: str,
            is_active: bool,
    ) -> dict[str, Any]:
        """设置部门的启用状态.

        参数：
            department_id: 部门 ID
            is_active: True 表示启用，False 表示停用

        返回：
            更新后的部门信息，包含启用状态和可用状态

        异常：
            ValueError: 部门不存在

        说明：
            停用后保留已有用户归属，禁止向该部门及其下级部门新增关联。
            下级部门各自的启用状态保持不变；只有所属机构和上级部门均启用，当前部门才可用。
        """
        async with UnitOfWork() as uow:
            repo = OrganizationRepository(
                uow.session,
            )
            item = await repo.get_department(department_id)
            if item is None:
                raise ValueError(
                    "部门不存在",
                )
            await repo.get_organization(
                item.organization_id,
                lock=True,
            )
            item = await repo.get_department(
                department_id,
                lock=True,
            )
            if item is None:
                raise ValueError(
                    "部门不存在",
                )
            catalog = await repo.catalog()

            before = self.department_item(item, catalog)
            item.is_active = is_active
            await repo.flush()
            result = self.department_item(item, catalog)

        await self._audit(
            "department",
            department_id,
            before,
            result,
            operation="enable" if is_active else "disable",
        )
        return result

    @staticmethod
    def _validate_parent(
            catalog: OrganizationCatalog,
            organization_id: str,
            parent_id: str | None,
            department_id: str | None,
    ) -> None:
        """校验上级部门的机构归属和层级关系.

        参数：
            catalog: 当前组织目录
            organization_id: 当前部门所属机构 ID
            parent_id: 上级部门 ID，None 表示无上级部门
            department_id: 当前部门 ID，创建部门时为 None

        异常：
            ValueError: 上级部门不存在、属于其他机构，或为当前部门自身或其下级部门
        """
        if parent_id is None:
            return
        parent = catalog.departments.get(
            parent_id,
        )
        if parent is None or parent.organization_id != organization_id:
            raise ValueError(
                "上级部门不存在或不属于该机构",
            )
        if any(
                node["department_id"] == department_id
                for node in catalog.path(parent_id)
        ):
            raise ValueError(
                "上级部门不能是自身或下级部门",
            )

    def _prepare_department(
            self,
            catalog: OrganizationCatalog,
            organization_id: str,
            department_id: str | None,
    ) -> tuple[Department, dict[str, Any] | None]:
        """准备部门对象及修改前的信息.

        参数：
            catalog: 当前组织目录
            organization_id: 所属机构 ID
            department_id: 部门 ID，未指定时构造新部门

        返回：
            部门对象和修改前的信息；新部门的修改前信息为 None

        异常：
            ValueError: 指定部门不存在或不属于该机构
        """
        if department_id is None:
            return Department(
                department_id=generate_random_id(
                    prefix="dpt",
                ),
                organization_id=organization_id,
            ), None

        item = catalog.departments.get(
            department_id,
        )
        if item is None or item.organization_id != organization_id:
            raise ValueError(
                "部门不存在或不属于该机构",
            )
        return item, self.department_item(
            item,
            catalog,
        )

    async def _audit(
            self,
            resource: str,
            target_id: str,
            before: dict[str, Any] | None,
            after: dict[str, Any] | None,
            *,
            operation: str | None = None,
    ) -> None:
        """记录组织变更的审计信息.

        参数：
            resource: 资源类型，organization 或 department
            target_id: 机构或部门 ID
            before: 变更前的信息，创建时为 None
            after: 变更后的信息，删除时为 None
            operation: 操作名称；未指定时根据前后信息判断为创建、修改或删除

        说明：
            在业务事务提交成功后调用，使用当前服务的审计上下文记录操作人信息。
        """
        operation = operation or (
            "delete" if after is None else "update" if before else "create"
        )
        await AuditRecorder().record(
            action=f"{resource}.{operation}",
            target_type=resource,
            target_id=target_id,
            before=before,
            after=after,
            context=self.audit_context,
        )

    @staticmethod
    async def validate_profile(
            session: AsyncSession,
            profile: dict[str, str | None],
            *,
            current_profile: dict[str, Any] | None = None,
    ) -> None:
        """校验用户的机构和部门归属.

        参数：
            session: 当前事务的数据库会话
            profile: 待保存的用户资料，包含机构 ID 和直接所属部门 ID
            current_profile: 用户原有资料；未提供时按新增归属校验

        异常：
            ValueError: 部门缺少所属机构，机构或部门不存在、归属不匹配，或向停用组织新增关联

        说明：
            允许不填写组织资料。新增归属时，所属机构及部门路径上各级部门须启用。
            保留已有归属或清空归属不受停用状态限制。
        """
        organization_id = profile.get(
            "organization_id",
        )
        department_id = profile.get(
            "department_id",
        )
        if not organization_id:
            if department_id:
                raise ValueError(
                    "选择部门前必须指定所属机构",
                )
            return

        repo = OrganizationRepository(
            session,
        )
        organization = await repo.get_organization(
            organization_id,
            lock=True,
        )
        if organization is None:
            raise ValueError(
                "所属机构不存在",
            )
        current = current_profile or {}
        new_association = (
            organization_id != current.get("organization_id")
            or bool(department_id and department_id != current.get("department_id"))
        )
        if new_association and getattr(organization, "is_active", True) is False:
            raise ValueError(
                "所属机构已停用，不能新增关联",
            )
        if department_id:
            department = await repo.get_department(
                department_id,
            )
            if department is None or department.organization_id != organization_id:
                raise ValueError(
                    "部门不存在或不属于所属机构",
                )
            if new_association:
                catalog = await repo.catalog()
                if not catalog.department_available(department_id):
                    raise ValueError(
                        "所属部门或其上级部门已停用，不能新增关联",
                    )


async def attach_user_profiles(
        session: AsyncSession,
        users: list[User],
) -> None:
    """为用户对象补充当前组织信息.

    参数：
        session: 当前事务的数据库会话
        users: 待补充组织信息的用户对象列表

    说明：
        为每个对象设置 organization_profile，包含当前机构名称和完整部门路径。
        仅补充展示信息，不修改数据库或回填历史审计记录。
    """
    has_organization = any(
        getattr(
            user,
            "organization_id",
            None,
        )
        for user in users
    )
    catalog = (
        await OrganizationRepository(session).catalog()
        if has_organization
        else OrganizationCatalog(
            [],
            [],
        )
    )
    for user in users:
        setattr(
            user,
            "organization_profile",
            catalog.profile(user),
        )
