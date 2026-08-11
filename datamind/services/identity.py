# datamind/services/identity.py

"""身份管理服务

提供 LOCAL 用户、角色和角色授予的管理能力。

核心功能：
  - create_user: 创建用户并授予初始角色
  - list_users: 查询用户列表
  - get_user: 查询用户详情
  - update_user: 更新用户资料和角色
  - enable_user: 启用用户
  - disable_user: 停用用户
  - change_password: 修改当前用户密码
  - reset_password: 重置用户密码
  - delete_user: 删除用户
  - create_role: 创建角色
  - list_roles: 查询角色列表
  - get_role: 查询角色详情
  - update_role: 更新角色资料与权限
  - enable_role: 启用角色
  - disable_role: 停用角色
  - grant_role: 授予用户角色
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
from datamind.audit.sanitizer import sanitize_audit_mapping
from datamind.auth.enums import (
    GrantStatus,
    RoleStatus,
    UserStatus,
)
from datamind.auth.password import (
    hash_password,
    verify_password,
)
from datamind.constants.identity import (
    ADMINISTRATOR_ROLE_NAME,
    BUILTIN_ROLE_NAMES,
    SYSTEM_BOOTSTRAP_ACTOR,
)
from datamind.constants.permissions import SUPPORTED_PERMISSIONS
from datamind.context.keys import (
    HOSTNAME,
    IP,
    REQUEST_ID,
    TRACE_ID,
)
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
    UserPatch,
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

    def __init__(
            self,
            *,
            audit_source: AuditSource = AuditSource.CLI,
            audit_context: dict[str, Any] | None = None,
    ) -> None:
        """初始化身份管理服务"""
        self._audit_source = audit_source
        self._audit_context = (
            sanitize_audit_mapping(
                audit_context
            )
            or {}
        )

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

            existing_user = await user_repo.get_user(
                username=normalized_username
            )

            if (
                    existing_user is not None
                    and getattr(
                        existing_user,
                        "deleted_at",
                        None,
                    ) is None
            ):
                raise IdentityConflictError(
                    f"用户名已存在: {normalized_username}"
                )

            normalized_email = self._optional_text(
                email,
                "邮箱",
                maximum=254,
            )

            if normalized_email is not None:
                email_owner = await user_repo.get_user(
                    email=normalized_email
                )

                if (
                        email_owner is not None
                        and (
                            existing_user is None
                            or email_owner.user_id
                            != existing_user.user_id
                        )
                ):
                    raise IdentityConflictError(
                        f"邮箱已存在: {normalized_email}"
                    )

            roles = await self._resolve_roles(
                role_repo=role_repo,
                role_names=normalized_roles,
            )
            normalized_display_name = self._optional_text(
                display_name,
                "显示名称",
                maximum=128,
            )

            if existing_user is None:
                user = user_repo.create_user(
                    user_id=generate_random_id(
                        prefix="usr"
                    ),
                    username=normalized_username,
                    password_hash=hash_password(
                        password
                    ),
                    display_name=normalized_display_name,
                    email=normalized_email,
                    created_by=operator_id,
                )
                user.password_changed_at = now
                audit_action = "user.create"
                audit_operation = "create"
                before = None
            else:
                user = existing_user
                before = self._user_result(
                    user,
                    roles=[],
                )
                user_repo.update_user(
                    user,
                    patch=UserPatch(
                        display_name=normalized_display_name,
                        email=normalized_email,
                    ),
                    updated_by=operator_id,
                )
                user_repo.update_password(
                    user,
                    password_hash=hash_password(
                        password
                    ),
                    changed_at=now,
                    updated_by=operator_id,
                )
                user_repo.restore_user(
                    user,
                    restored_at=now,
                    restored_by=operator_id,
                )
                audit_action = "user.restore"
                audit_operation = "restore"

            for role in roles:
                grant = (
                    await grant_repo.get_grant(
                        user_id=user.user_id,
                        role_id=role.role_id,
                    )
                    if existing_user is not None
                    else None
                )

                if grant is None:
                    grant_repo.create_grant(
                        grant_id=generate_random_id(
                            prefix="grt"
                        ),
                        user_id=user.user_id,
                        role_id=role.role_id,
                        granted_by=operator_id,
                        granted_at=now,
                    )
                elif getattr(
                        grant,
                        "status",
                        None,
                ) != str(GrantStatus.ACTIVE):
                    grant_repo.activate_grant(
                        grant,
                        granted_by=operator_id,
                        granted_at=now,
                    )

            result = self._user_result(
                user,
                roles=normalized_roles,
            )
            result["action"] = audit_operation
            self._audit(
                audit_repo,
                action=audit_action,
                operation=audit_operation,
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                before=before,
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

    async def update_user(
            self,
            *,
            username: str,
            new_username: str,
            operator_id: str,
            operator: str,
            display_name: str | None = None,
            email: str | None = None,
            role_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """更新用户名、显示名称、邮箱和角色

        系统初始化创建的内置管理员账户只允许修改邮箱和附加角色，
        其用户名、显示名称和 administrator 角色保持不变。
        """
        logger.info(
            "开始更新用户资料",
            username=username,
            new_username=new_username,
            role_names=role_names,
            operator=operator,
        )
        normalized_username = self._required_text(
            username,
            "用户名",
            maximum=64,
        )
        normalized_new_username = self._required_text(
            new_username,
            "新用户名",
            maximum=64,
        )
        normalized_display_name = self._nullable_text(
            display_name,
            "显示名称",
            maximum=128,
        )
        normalized_email = self._nullable_text(
            email,
            "邮箱",
            maximum=254,
        )
        normalized_roles = (
            self._normalize_permissions(
                role_names
            )
            if role_names is not None
            else None
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
                username=normalized_username,
            )
            self._protect_builtin_user_update(
                user=user,
                new_username=normalized_new_username,
                display_name=normalized_display_name,
                role_names=normalized_roles,
            )

            username_owner = await user_repo.get_user(
                username=normalized_new_username
            )

            if (
                    username_owner is not None
                    and username_owner.user_id != user.user_id
            ):
                raise IdentityConflictError(
                    f"用户名已存在: {normalized_new_username}"
                )

            if normalized_email is not None:
                email_owner = await user_repo.get_user(
                    email=normalized_email
                )

                if (
                        email_owner is not None
                        and email_owner.user_id != user.user_id
                ):
                    raise IdentityConflictError(
                        f"邮箱已被使用: {normalized_email}"
                    )

            current_role_names = await self._user_role_names(
                user=user,
                grant_repo=grant_repo,
                role_repo=role_repo,
            )
            before = self._user_result(
                user,
                roles=current_role_names,
            )
            user_repo.replace_profile(
                user,
                username=normalized_new_username,
                display_name=normalized_display_name,
                email=normalized_email,
                updated_by=operator_id,
            )

            if normalized_roles is not None:
                result_role_names = await self._replace_user_roles(
                    user=user,
                    role_names=normalized_roles,
                    current_role_names=current_role_names,
                    operator_id=operator_id,
                    user_repo=user_repo,
                    role_repo=role_repo,
                    grant_repo=grant_repo,
                )
            else:
                result_role_names = current_role_names

            result = self._user_result(
                user,
                roles=result_role_names,
            )
            self._audit(
                audit_repo,
                action="user.update",
                operation="update",
                target_type="user",
                target_id=user.user_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

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
                include_deleted=True,
            )

            if getattr(
                    user,
                    "deleted_at",
                    None,
            ) is not None:
                raise IdentityConflictError(
                    "用户已被逻辑删除，请使用 "
                    f"datamind user create {user.username} "
                    "设置新密码并恢复用户"
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
            self._reject_builtin_user_action(
                user=user,
                operation="停用",
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

    async def change_password(
            self,
            *,
            username: str,
            current_password: str,
            new_password: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """修改当前用户密码并撤销已有登录会话"""
        logger.info(
            "开始修改用户密码",
            username=username,
            operator=operator,
        )
        self._validate_password(
            current_password
        )
        self._validate_password(
            new_password
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
            password_hash = user.password_hash or ""

            if not verify_password(
                    password=current_password,
                    password_hash=password_hash,
            ):
                raise IdentityConflictError(
                    "当前密码不正确"
                )

            if verify_password(
                    password=new_password,
                    password_hash=password_hash,
            ):
                raise IdentityConflictError(
                    "新密码不能与当前密码相同"
                )

            user_repo.update_password(
                user,
                password_hash=hash_password(
                    new_password
                ),
                updated_by=operator_id,
            )
            await token_repo.revoke_user_tokens(
                user_id=user.user_id,
                revoked_by=operator_id,
                revoke_reason="用户修改密码",
            )
            result = {
                "user_id": user.user_id,
                "username": user.username,
                "password_changed_at": format_iso_utc(
                    user.password_changed_at
                ),
            }
            self._audit(
                audit_repo,
                action="user.change_password",
                operation="change_password",
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
            operator_id: str,
            operator: str,
            reason: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除用户并撤销角色与登录会话"""
        logger.info(
            "开始删除用户",
            username=username,
            operator=operator,
        )
        deletion_reason = self._optional_text(
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
            self._reject_builtin_user_action(
                user=user,
                operation="删除",
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

    async def update_role(
            self,
            *,
            name: str,
            description: str | None,
            permissions: list[str],
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """更新普通角色的描述与权限"""
        logger.info(
            "开始更新角色资料与权限",
            name=name,
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
        normalized_description = self._nullable_text(
            description,
            "角色描述",
            maximum=2000,
        )

        if not normalized_permissions:
            raise ValueError(
                "请至少指定一项权限"
            )

        self._validate_role_permissions(
            normalized_permissions
        )
        self._reject_builtin_role_action(
            role_name=normalized_name,
            operation="修改",
        )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            role = await self._require_role(
                role_repo,
                name=normalized_name,
            )
            before = self._role_result(
                role
            )
            role_repo.replace_description(
                role,
                description=normalized_description,
                updated_by=operator_id,
            )
            role_repo.replace_permissions(
                role,
                permissions=normalized_permissions,
                updated_by=operator_id,
            )
            result = self._role_result(
                role
            )
            self._audit(
                audit_repo,
                action="role.update",
                operation="update",
                target_type="role",
                target_id=role.role_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def enable_role(
            self,
            *,
            name: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """启用角色"""
        logger.info(
            "开始启用角色",
            name=name,
            operator=operator,
        )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            role = await self._require_role(
                role_repo,
                name=name,
            )
            before = self._role_result(
                role
            )
            role_repo.activate_role(
                role,
                updated_by=operator_id,
            )
            result = self._role_result(
                role
            )
            self._audit(
                audit_repo,
                action="role.enable",
                operation="enable",
                target_type="role",
                target_id=role.role_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def disable_role(
            self,
            *,
            name: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """停用角色并暂时收回其权限"""
        logger.info(
            "开始停用角色",
            name=name,
            operator=operator,
        )
        normalized_name = self._required_text(
            name,
            "角色名称",
            maximum=64,
        )
        self._reject_builtin_role_action(
            role_name=normalized_name,
            operation="停用",
        )

        async with UnitOfWork() as uow:
            role_repo = RoleRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )
            role = await self._require_role(
                role_repo,
                name=normalized_name,
            )
            before = self._role_result(
                role
            )
            role_repo.deactivate_role(
                role,
                updated_by=operator_id,
            )
            result = self._role_result(
                role
            )
            self._audit(
                audit_repo,
                action="role.disable",
                operation="disable",
                target_type="role",
                target_id=role.role_id,
                operator=operator,
                before=before,
                after=result,
            )

        return result

    async def grant_role(
            self,
            *,
            username: str,
            role_name: str,
            operator_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """授予用户角色"""
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

            if role.name == ADMINISTRATOR_ROLE_NAME:
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
            operator_id: str,
            operator: str,
            reason: str | None = None,
    ) -> dict[str, Any]:
        """逻辑删除没有有效授予的角色"""
        logger.info(
            "开始删除角色",
            name=name,
            operator=operator,
        )
        deletion_reason = self._optional_text(
            reason,
            "删除原因",
            maximum=2000,
        )
        normalized_name = self._required_text(
            name,
            "角色名称",
            maximum=64,
        )
        self._reject_builtin_role_action(
            role_name=normalized_name,
            operation="删除",
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
                name=normalized_name,
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

    async def _replace_user_roles(
            self,
            *,
            user: User,
            role_names: list[str],
            current_role_names: list[str],
            operator_id: str,
            user_repo: UserRepository,
            role_repo: RoleRepository,
            grant_repo: GrantRepository,
    ) -> list[str]:
        """替换用户的有效角色授予"""
        roles = await self._resolve_roles(
            role_repo=role_repo,
            role_names=role_names,
        )
        target_role_ids = {
            role.role_id
            for role in roles
        }
        current_grants = await grant_repo.list_active_grants(
            user_id=user.user_id,
            limit=None,
        )
        current_role_ids = {
            grant.role_id
            for grant in current_grants
        }

        if (
                ADMINISTRATOR_ROLE_NAME
                in current_role_names
                and ADMINISTRATOR_ROLE_NAME
                not in role_names
        ):
            await self._protect_last_admin(
                user=user,
                user_repo=user_repo,
                role_repo=role_repo,
                grant_repo=grant_repo,
            )

        for grant in current_grants:
            if grant.role_id not in target_role_ids:
                grant_repo.revoke_grant(
                    grant,
                    revoked_by=operator_id,
                )

        for role in roles:
            if role.role_id in current_role_ids:
                continue

            grant = await grant_repo.get_grant(
                user_id=user.user_id,
                role_id=role.role_id,
            )

            if grant is None:
                grant_repo.create_grant(
                    grant_id=generate_random_id(
                        prefix="grt"
                    ),
                    user_id=user.user_id,
                    role_id=role.role_id,
                    granted_by=operator_id,
                )
            else:
                grant_repo.activate_grant(
                    grant,
                    granted_by=operator_id,
                )

        return role_names

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
            name=ADMINISTRATOR_ROLE_NAME
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
                "不能移除最后一个有效的 administrator 用户"
            )

    @staticmethod
    def _reject_builtin_user_action(
            *,
            user: User,
            operation: str,
    ) -> None:
        """拒绝停用或删除系统初始化创建的管理员账户"""
        if user.created_by == SYSTEM_BOOTSTRAP_ACTOR:
            raise IdentityConflictError(
                f"内置管理员账户不能{operation}"
            )

    @staticmethod
    def _protect_builtin_user_update(
            *,
            user: User,
            new_username: str,
            display_name: str | None,
            role_names: list[str] | None,
    ) -> None:
        """保护内置管理员账户的固定身份和管理员角色"""
        if user.created_by != SYSTEM_BOOTSTRAP_ACTOR:
            return

        if new_username != user.username:
            raise IdentityConflictError(
                "内置管理员账户的用户名不能修改"
            )

        if display_name != user.display_name:
            raise IdentityConflictError(
                "内置管理员账户的显示名称不能修改"
            )

        if (
                role_names is not None
                and ADMINISTRATOR_ROLE_NAME not in role_names
        ):
            raise IdentityConflictError(
                "内置管理员账户必须保留 administrator 角色"
            )

    @staticmethod
    def _reject_builtin_role_action(
            *,
            role_name: str,
            operation: str,
    ) -> None:
        """拒绝停用或删除内置角色"""
        if role_name in BUILTIN_ROLE_NAMES:
            raise IdentityConflictError(
                f"{role_name} 为系统保留角色，"
                f"不能{operation}"
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
            "is_builtin": (
                user.created_by
                == SYSTEM_BOOTSTRAP_ACTOR
            ),
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
            "is_builtin": (
                role.name in BUILTIN_ROLE_NAMES
            ),
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

    def _audit(
            self,
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
        audit_context = dict(
            self._audit_context
        )
        sanitized_context = sanitize_audit_mapping(
            context
        )
        if sanitized_context:
            audit_context.update(
                sanitized_context
            )

        repository.create_audit(
            audit_id=generate_random_id(
                prefix="aud"
            ),
            action=action,
            resource=target_type,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            source=self._audit_source,
            trace_id=self._audit_context_value(
                audit_context,
                TRACE_ID,
            ),
            request_id=self._audit_context_value(
                audit_context,
                REQUEST_ID,
            ),
            user=operator,
            ip=self._audit_context_value(
                audit_context,
                IP,
            ),
            hostname=self._audit_context_value(
                audit_context,
                HOSTNAME,
            ),
            status=AuditStatus.SUCCESS,
            before=before,
            after=after,
            context=audit_context or None,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _audit_context_value(
            context: dict[str, Any],
            key: str,
    ) -> str | None:
        """读取已净化的标准审计上下文字段"""
        value = context.get(
            key
        )
        return value if isinstance(value, str) else None

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
    def _nullable_text(
            cls,
            value: str | None,
            field_name: str,
            *,
            maximum: int,
    ) -> str | None:
        """规范化允许清空的文本"""
        if value is None or value.strip() == "":
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
