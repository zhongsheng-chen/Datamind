# datamind/services/identity.py

"""身份管理服务

提供 LOCAL 用户、角色和角色授予的管理能力。

核心功能：
  - create_user: 创建用户并授予初始角色
  - list_users: 查询用户列表
  - get_user: 查询用户详情
  - enable_user: 启用用户
  - disable_user: 停用用户
  - reset_password: 重置用户密码
  - delete_user: 删除用户
  - create_role: 创建角色
  - list_roles: 查询角色列表
  - get_role: 查询角色详情
  - grant_role: 向用户授予角色
  - revoke_role: 撤销用户角色
  - delete_role: 删除角色

使用示例：
  from datamind.services.identity import IdentityService

  result = await IdentityService().create_user(
      username="alice",
      password="P@ssw1rd",
      role_names=[
          "developer",
      ],
      operator_id="usr_0123456789abcdef",
      operator="admin",
  )
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Any

import structlog

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.auth.enums import (
    GrantStatus,
    RoleStatus,
    UserStatus,
)
from datamind.auth.password import hash_password
from datamind.constants.identity import (
    BUILTIN_ROLE_NAMES,
    SYSTEM_ADMIN_ROLE_NAME,
)
from datamind.constants.permissions import SUPPORTED_PERMISSIONS
from datamind.db.core import UnitOfWork
from datamind.db.models import (
    Role,
    User,
)
from datamind.db.repositories import (
    AuditRepository,
    GrantRepository,
    RoleRepository,
    RolePatch,
    TokenRepository,
    UserRepository,
)
from datamind.services.errors import (
    IdentityConflictError,
    RoleNotFoundError,
    UserNotFoundError,
)
from datamind.utils import generate_random_id
from datamind.utils.datetime import format_iso_utc


logger = structlog.get_logger(__name__)


class IdentityService:
    """身份管理服务"""

    async def create_user(
            self,
            *,
            username: str,
            password: str,
            operator_id: str,
            operator: str,
            display_name: str | None = None,
            email: str | None = None,
            role_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """创建用户并授予角色"""
        logger.info(
            "开始创建用户",
            username=username,
            role_names=role_names,
            operator=operator,
        )
        normalized_username = self._required_text(
            username,
            "用户名",
            maximum=64,
        )
        self._validate_password(
            password
        )
        normalized_roles = self._normalize_permissions(
            role_names or []
        )
        now = datetime.now(
            timezone.utc
        )

        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )

            if await user_repo.get_user(
                    username=normalized_username
            ) is not None:
                raise IdentityConflictError(
                    f"用户名已存在: {normalized_username}"
                )

            normalized_email = self._optional_text(
                email,
                "邮箱",
                maximum=254,
            )

            if (
                    normalized_email is not None
                    and await user_repo.get_user(
                        email=normalized_email
                    ) is not None
            ):
                raise IdentityConflictError(
                    f"邮箱已存在: {normalized_email}"
                )

            roles = await self._resolve_roles(
                role_repo=role_repo,
                role_names=normalized_roles,
            )
            user = user_repo.create_user(
                user_id=generate_random_id(
                    prefix="usr"
                ),
                username=normalized_username,
                password_hash=hash_password(
                    password
                ),
                display_name=self._optional_text(
                    display_name,
                    "显示名称",
                    maximum=128,
                ),
                email=normalized_email,
                created_by=operator_id,
            )
            user.password_changed_at = now

            for role in roles:
                grant_repo.create_grant(
                    grant_id=generate_random_id(
                        prefix="grt"
                    ),
                    user_id=user.user_id,
                    role_id=role.role_id,
                    granted_by=operator_id,
                    granted_at=now,
                )

            result = self._user_result(
                user,
                roles=normalized_roles,
            )
            self._audit(
                audit_repo,
                action="user.create",
                operation="create",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                after=result,
                occurred_at=now,
            )

        return result

    async def list_users(
            self,
            *,
            status: UserStatus | None = None,
            include_deleted: bool = False,
            limit: int = 100,
            offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取用户列表"""
        logger.info(
            "开始查询用户列表",
            status=status,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            users = await user_repo.list_users(
                status=status,
                limit=None,
            )
            visible_users = [
                user
                for user in users
                if (
                    include_deleted
                    or getattr(
                        user,
                        "deleted_at",
                        None,
                    ) is None
                )
            ][offset:offset + limit]

            return [
                self._user_result(
                    user,
                    roles=await self._user_role_names(
                        user=user,
                        grant_repo=grant_repo,
                        role_repo=role_repo,
                    ),
                )
                for user in visible_users
            ]

    async def get_user(
            self,
            *,
            username: str,
            include_deleted: bool = False,
    ) -> dict[str, Any]:
        """按用户名获取用户"""
        logger.info(
            "开始查询用户详情",
            username=username,
            include_deleted=include_deleted,
        )
        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
                include_deleted=include_deleted,
            )

            return self._user_result(
                user,
                roles=await self._user_role_names(
                    user=user,
                    grant_repo=grant_repo,
                    role_repo=role_repo,
                ),
            )

    async def enable_user(
            self,
            *,
            username: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """启用用户"""
        logger.info(
            "开始启用用户",
            username=username,
            operator=operator,
        )
        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            before = self._user_result(
                user
            )
            user_repo.activate_user(
                user,
                updated_by=operator_id,
            )
            result = self._user_result(
                user
            )
            self._audit(
                audit_repo,
                action="user.enable",
                operation="enable",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def disable_user(
            self,
            *,
            username: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """停用用户并撤销其登录会话"""
        logger.info(
            "开始停用用户",
            username=username,
            operator=operator,
        )
        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            token_repo = TokenRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            self._reject_self_action(
                user=user,
                operator_id=operator_id,
                operation="停用",
            )
            await self._protect_last_admin(
                user=user,
                user_repo=user_repo,
                role_repo=role_repo,
                grant_repo=grant_repo,
            )
            before = self._user_result(
                user
            )
            user_repo.disable_user(
                user,
                updated_by=operator_id,
            )
            await token_repo.revoke_user_tokens(
                user_id=user.user_id,
                revoked_by=operator_id,
                revoke_reason="用户已停用",
            )
            result = self._user_result(
                user
            )
            self._audit(
                audit_repo,
                action="user.disable",
                operation="disable",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def reset_password(
            self,
            *,
            username: str,
            password: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """重置用户密码并撤销其登录会话"""
        logger.info(
            "开始重置用户密码",
            username=username,
            operator=operator,
        )
        self._validate_password(
            password
        )

        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            token_repo = TokenRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            user_repo.update_password(
                user,
                password_hash=hash_password(
                    password
                ),
                updated_by=operator_id,
            )
            await token_repo.revoke_user_tokens(
                user_id=user.user_id,
                revoked_by=operator_id,
                revoke_reason="密码已重置",
            )
            result = self._user_result(
                user
            )
            self._audit(
                audit_repo,
                action="user.reset_password",
                operation="reset_password",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                after={
                    "password_changed_at": result[
                        "password_changed_at"
                    ],
                },
            )

        return result

    async def delete_user(
            self,
            *,
            username: str,
            reason: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """逻辑删除用户并撤销角色与登录会话"""
        logger.info(
            "开始删除用户",
            username=username,
            operator=operator,
        )
        deletion_reason = self._required_text(
            reason,
            "删除原因",
            maximum=2000,
        )

        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            token_repo = TokenRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            self._reject_self_action(
                user=user,
                operator_id=operator_id,
                operation="删除",
            )
            await self._protect_last_admin(
                user=user,
                user_repo=user_repo,
                role_repo=role_repo,
                grant_repo=grant_repo,
            )
            before = self._user_result(
                user,
                roles=await self._user_role_names(
                    user=user,
                    grant_repo=grant_repo,
                    role_repo=role_repo,
                ),
            )
            grants = await grant_repo.list_active_grants(
                user_id=user.user_id,
                limit=None,
            )

            for grant in grants:
                grant_repo.revoke_grant(
                    grant,
                    revoked_by=operator_id,
                )

            await token_repo.revoke_user_tokens(
                user_id=user.user_id,
                revoked_by=operator_id,
                revoke_reason="用户已删除",
            )
            user_repo.mark_deleted(
                user,
                deleted_by=operator_id,
                deletion_reason=deletion_reason,
            )
            result = self._user_result(
                user,
                roles=[],
            )
            self._audit(
                audit_repo,
                action="user.delete",
                operation="delete",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                before=before,
                after=result,
                context={
                    "reason": deletion_reason,
                },
            )

        return result

    async def create_role(
            self,
            *,
            name: str,
            permissions: list[str],
            operator_id: str,
            operator: str,
            description: str | None = None,
    ) -> dict[str, Any]:
        """创建角色"""
        logger.info(
            "开始创建角色",
            name=name,
            permissions=permissions,
            operator=operator,
        )
        normalized_name = self._required_text(
            name,
            "角色名称",
            maximum=64,
        )
        normalized_permissions = self._normalize_permissions(
            permissions
        )
        self._validate_role_permissions(
            normalized_permissions
        )
        normalized_description = self._optional_text(
            description,
            "角色说明",
            maximum=2000,
        )

        if normalized_name in BUILTIN_ROLE_NAMES:
            raise IdentityConflictError(
                f"{normalized_name} 为系统保留角色，"
                "只能由 datamind init 创建"
            )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )

            existing_role = await role_repo.get_role(
                name=normalized_name
            )

            if (
                    existing_role is not None
                    and getattr(
                        existing_role,
                        "deleted_at",
                        None,
                    ) is None
            ):
                raise IdentityConflictError(
                    f"角色已存在: {normalized_name}"
                )

            if existing_role is None:
                role = role_repo.create_role(
                    role_id=generate_random_id(
                        prefix="rol"
                    ),
                    name=normalized_name,
                    description=normalized_description,
                    permissions=normalized_permissions,
                    created_by=operator_id,
                )
                before = None
                audit_action = "role.create"
                audit_operation = "create"
            else:
                role = existing_role
                before = self._role_result(
                    role
                )

                if normalized_description is not None:
                    role_repo.update_role(
                        role,
                        patch=RolePatch(
                            description=normalized_description,
                        ),
                        updated_by=operator_id,
                    )

                role_repo.replace_permissions(
                    role,
                    permissions=normalized_permissions,
                    updated_by=operator_id,
                )
                role_repo.restore_role(
                    role,
                    restored_by=operator_id,
                )
                audit_action = "role.restore"
                audit_operation = "restore"

            result = self._role_result(
                role
            )
            self._audit(
                audit_repo,
                action=audit_action,
                operation=audit_operation,
                target_type="role",
                target_id=role.role_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def list_roles(
            self,
            *,
            status: RoleStatus | None = None,
            include_deleted: bool = False,
            limit: int = 100,
            offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取角色列表"""
        logger.info(
            "开始查询角色列表",
            status=status,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            roles = await role_repo.list_roles(
                status=status,
                limit=None,
            )

            return [
                self._role_result(
                    role
                )
                for role in roles
                if (
                    include_deleted
                    or getattr(
                        role,
                        "deleted_at",
                        None,
                    ) is None
                )
            ][offset:offset + limit]

    async def get_role(
            self,
            *,
            name: str,
            include_deleted: bool = False,
    ) -> dict[str, Any]:
        """按名称获取角色"""
        logger.info(
            "开始查询角色详情",
            name=name,
            include_deleted=include_deleted,
        )
        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            role = await self._require_role(
                role_repo,
                name=name,
                include_deleted=include_deleted,
            )

            return self._role_result(
                role
            )

    async def grant_role(
            self,
            *,
            username: str,
            role_name: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """向用户授予角色"""
        logger.info(
            "开始授予用户角色",
            username=username,
            role_name=role_name,
            operator=operator,
        )
        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            role = await self._require_role(
                role_repo,
                name=role_name,
            )

            if getattr(
                    role,
                    "status",
                    None,
            ) != str(RoleStatus.ACTIVE):
                raise IdentityConflictError(
                    f"角色未启用: {role.name}"
                )

            grant = await grant_repo.get_grant(
                user_id=user.user_id,
                role_id=role.role_id,
            )

            if grant is None:
                grant = grant_repo.create_grant(
                    grant_id=generate_random_id(
                        prefix="grt"
                    ),
                    user_id=user.user_id,
                    role_id=role.role_id,
                    granted_by=operator_id,
                )
            elif getattr(
                    grant,
                    "status",
                    None,
            ) != str(GrantStatus.ACTIVE):
                grant_repo.activate_grant(
                    grant,
                    granted_by=operator_id,
                )

            result = {
                "grant_id": grant.grant_id,
                "username": user.username,
                "role": role.name,
                "status": grant.status,
            }
            self._audit(
                audit_repo,
                action="role.grant",
                operation="grant",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                after=result,
            )

        return result

    async def revoke_role(
            self,
            *,
            username: str,
            role_name: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """撤销用户角色"""
        logger.info(
            "开始撤销用户角色",
            username=username,
            role_name=role_name,
            operator=operator,
        )
        async with UnitOfWork() as uow:
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            user = await self._require_user(
                user_repo,
                username=username,
            )
            role = await self._require_role(
                role_repo,
                name=role_name,
            )
            grant = await grant_repo.get_grant(
                user_id=user.user_id,
                role_id=role.role_id,
            )

            if (
                    grant is None
                    or getattr(
                        grant,
                        "status",
                        None,
                    ) != str(GrantStatus.ACTIVE)
            ):
                raise IdentityConflictError(
                    f"用户 {user.username} 未被授予角色 {role.name}"
                )

            if role.name == SYSTEM_ADMIN_ROLE_NAME:
                await self._protect_last_admin(
                    user=user,
                    user_repo=user_repo,
                    role_repo=role_repo,
                    grant_repo=grant_repo,
                )

            grant_repo.revoke_grant(
                grant,
                revoked_by=operator_id,
            )
            result = {
                "grant_id": grant.grant_id,
                "username": user.username,
                "role": role.name,
                "status": grant.status,
            }
            self._audit(
                audit_repo,
                action="role.revoke",
                operation="revoke",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                after=result,
            )

        return result

    async def delete_role(
            self,
            *,
            name: str,
            reason: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """逻辑删除没有有效授予的角色"""
        logger.info(
            "开始删除角色",
            name=name,
            operator=operator,
        )
        deletion_reason = self._required_text(
            reason,
            "删除原因",
            maximum=2000,
        )

        if name.strip() in BUILTIN_ROLE_NAMES:
            raise IdentityConflictError(
                "system-admin 为系统保留角色，不能删除"
            )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            role = await self._require_role(
                role_repo,
                name=name,
            )
            grants = await grant_repo.list_active_grants(
                role_id=role.role_id,
                limit=None,
            )

            if grants:
                raise IdentityConflictError(
                    "角色仍授予给用户，请先撤销全部角色授予"
                )

            before = self._role_result(
                role
            )
            role_repo.mark_deleted(
                role,
                deleted_by=operator_id,
                deletion_reason=deletion_reason,
            )
            result = self._role_result(
                role
            )
            self._audit(
                audit_repo,
                action="role.delete",
                operation="delete",
                target_type="role",
                target_id=role.role_id,
                operator=operator,
                before=before,
                after=result,
                context={
                    "reason": deletion_reason,
                },
            )

        return result

    @staticmethod
    async def _resolve_roles(
            *,
            role_repo: RoleRepository,
            role_names: list[str],
    ) -> list[Role]:
        """解析待授予的有效角色"""
        roles: list[Role] = []

        for name in role_names:
            role = await role_repo.get_role(
                name=name
            )

            if (
                    role is None
                    or getattr(
                        role,
                        "deleted_at",
                        None,
                    ) is not None
            ):
                raise RoleNotFoundError(
                    f"角色不存在: {name}"
                )

            if getattr(
                    role,
                    "status",
                    None,
            ) != str(RoleStatus.ACTIVE):
                raise IdentityConflictError(
                    f"角色未启用: {name}"
                )

            roles.append(
                role
            )

        return roles

    @staticmethod
    async def _require_user(
            user_repo: UserRepository,
            *,
            username: str,
            include_deleted: bool = False,
    ) -> User:
        """获取有效用户"""
        normalized = username.strip()
        user = await user_repo.get_user(
            username=normalized
        )

        if (
                user is None
                or (
                    getattr(
                        user,
                        "deleted_at",
                        None,
                    ) is not None
                    and not include_deleted
                )
        ):
            raise UserNotFoundError(
                f"用户不存在: {normalized}"
            )

        return user

    @staticmethod
    async def _require_role(
            role_repo: RoleRepository,
            *,
            name: str,
            include_deleted: bool = False,
    ) -> Role:
        """获取有效角色"""
        normalized = name.strip()
        role = await role_repo.get_role(
            name=normalized
        )

        if (
                role is None
                or (
                    getattr(
                        role,
                        "deleted_at",
                        None,
                    ) is not None
                    and not include_deleted
                )
        ):
            raise RoleNotFoundError(
                f"角色不存在: {normalized}"
            )

        return role

    @staticmethod
    async def _user_role_names(
            *,
            user: User,
            grant_repo: GrantRepository,
            role_repo: RoleRepository,
    ) -> list[str]:
        """获取用户的有效角色名称"""
        grants = await grant_repo.list_active_grants(
            user_id=user.user_id,
            limit=None,
        )
        names: list[str] = []

        for grant in grants:
            role = await role_repo.get_role(
                role_id=grant.role_id
            )

            if (
                    role is not None
                    and getattr(
                        role,
                        "deleted_at",
                        None,
                    ) is None
                    and getattr(
                        role,
                        "status",
                        None,
                    ) == str(RoleStatus.ACTIVE)
            ):
                names.append(
                    role.name
                )

        return sorted(
            names
        )

    @staticmethod
    async def _protect_last_admin(
            *,
            user: User,
            user_repo: UserRepository,
            role_repo: RoleRepository,
            grant_repo: GrantRepository,
    ) -> None:
        """保护最后一个有效系统管理员"""
        admin_role = await role_repo.get_role(
            name=SYSTEM_ADMIN_ROLE_NAME
        )

        if admin_role is None:
            return

        target_grant = await grant_repo.get_grant(
            user_id=user.user_id,
            role_id=admin_role.role_id,
        )

        if (
                target_grant is None
                or getattr(
                    target_grant,
                    "status",
                    None,
                ) != str(GrantStatus.ACTIVE)
        ):
            return

        grants = await grant_repo.list_active_grants(
            role_id=admin_role.role_id,
            limit=None,
        )
        active_admin_count = 0

        for grant in grants:
            granted_user = await user_repo.get_user(
                user_id=grant.user_id
            )

            if (
                    granted_user is not None
                    and getattr(
                        granted_user,
                        "deleted_at",
                        None,
                    ) is None
                    and getattr(
                        granted_user,
                        "status",
                        None,
                    ) == str(UserStatus.ACTIVE)
            ):
                active_admin_count += 1

        if active_admin_count <= 1:
            raise IdentityConflictError(
                "不能移除最后一个有效的 system-admin 用户"
            )

    @staticmethod
    def _reject_self_action(
            *,
            user: User,
            operator_id: str,
            operation: str,
    ) -> None:
        """拒绝危险的自身账户操作"""
        if user.user_id == operator_id:
            raise IdentityConflictError(
                f"不能{operation}当前登录用户"
            )

    @staticmethod
    def _user_result(
            user: User,
            *,
            roles: list[str] | None = None,
    ) -> dict[str, Any]:
        """构建用户结果"""
        return {
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "status": user.status,
            "roles": roles or [],
            "last_login_at": format_iso_utc(
                user.last_login_at
            ),
            "password_changed_at": format_iso_utc(
                user.password_changed_at
            ),
            "created_at": format_iso_utc(
                user.created_at
            ),
            "updated_at": format_iso_utc(
                user.updated_at
            ),
            "deleted_at": format_iso_utc(
                user.deleted_at
            ),
            "deleted_by": user.deleted_by,
            "deletion_reason": user.deletion_reason,
        }

    @staticmethod
    def _role_result(
            role: Role,
    ) -> dict[str, Any]:
        """构建角色结果"""
        permissions = role.permissions

        return {
            "role_id": role.role_id,
            "name": role.name,
            "description": role.description,
            "permissions": (
                list(
                    permissions
                )
                if isinstance(permissions, list)
                else []
            ),
            "status": role.status,
            "created_at": format_iso_utc(
                role.created_at
            ),
            "updated_at": format_iso_utc(
                role.updated_at
            ),
            "deleted_at": format_iso_utc(
                role.deleted_at
            ),
            "deleted_by": role.deleted_by,
            "deletion_reason": role.deletion_reason,
        }

    @staticmethod
    def _audit(
            repository: AuditRepository,
            *,
            action: str,
            operation: str,
            target_type: str,
            target_id: str,
            operator: str,
            before: dict[str, Any] | None = None,
            after: dict[str, Any] | None = None,
            context: dict[str, Any] | None = None,
            occurred_at: datetime | None = None,
    ) -> None:
        """记录身份管理审计事件"""
        repository.create_audit(
            audit_id=generate_random_id(
                prefix="aud"
            ),
            action=action,
            resource=target_type,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            source=AuditSource.CLI,
            user=operator,
            status=AuditStatus.SUCCESS,
            before=before,
            after=after,
            context=context,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _required_text(
            value: str,
            field_name: str,
            *,
            maximum: int,
    ) -> str:
        """校验必填文本"""
        normalized = value.strip()

        if normalized == "":
            raise ValueError(
                f"{field_name}不能为空"
            )

        if len(normalized) > maximum:
            raise ValueError(
                f"{field_name}长度不能超过 {maximum}"
            )

        return normalized

    @classmethod
    def _optional_text(
            cls,
            value: str | None,
            field_name: str,
            *,
            maximum: int,
    ) -> str | None:
        """校验可选文本"""
        if value is None:
            return None

        return cls._required_text(
            value,
            field_name,
            maximum=maximum,
        )

    @classmethod
    def _normalize_permissions(
            cls,
            values: list[str],
    ) -> list[str]:
        """规范化权限或角色名称列表"""
        normalized = {
            cls._required_text(
                value,
                "列表项",
                maximum=128,
            )
            for value in values
        }

        return sorted(
            normalized
        )

    @staticmethod
    def _validate_role_permissions(
            permissions: list[str],
    ) -> None:
        """校验角色权限"""
        namespaces = {
            permission.partition(".")[0]
            for permission in SUPPORTED_PERMISSIONS
        }
        invalid_permissions = [
            permission
            for permission in permissions
            if not (
                permission == "*"
                or permission in SUPPORTED_PERMISSIONS
                or (
                    permission.endswith(".*")
                    and permission[:-2] in namespaces
                )
            )
        ]

        if invalid_permissions:
            raise ValueError(
                "不支持的权限: "
                + ", ".join(
                    invalid_permissions
                )
            )

    @staticmethod
    def _validate_password(
            password: str,
    ) -> None:
        """校验明文密码"""
        if password == "":
            raise ValueError(
                "密码不能为空"
            )

        if len(password) > 1024:
            raise ValueError(
                "密码长度不能超过 1024"
            )

    @staticmethod
    def _validate_pagination(
            *,
            limit: int,
            offset: int,
    ) -> None:
        """校验分页参数"""
        if limit < 1:
            raise ValueError(
                "limit 必须大于 0"
            )

        if offset < 0:
            raise ValueError(
                "offset 不能小于 0"
            )


__all__ = [
    "IdentityService",
]
