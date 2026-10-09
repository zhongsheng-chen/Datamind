"""身份管理服务测试.

验证用户、角色、角色授予、令牌撤销和安全保护行为。

核心功能：
  - test_creation_logs_after_commit:
    验证创建完成日志仅在提交成功后记录
  - test_identity_list_logs_at_debug:
    验证身份列表查询使用调试日志
  - test_create_user_creates_identity_and_initial_grants:
    验证创建用户及初始角色授予
  - test_create_user_restores_deleted_user:
    验证重新创建已删除用户时恢复原记录
  - test_create_role_rejects_builtin_role:
    验证普通身份管理不能创建内置角色
  - test_create_role_restores_deleted_role:
    验证重新创建已删除角色时恢复原记录
  - test_create_role_rejects_unsupported_permission:
    验证创建角色拒绝未注册权限
  - test_enable_role_activates_role:
    验证启用角色并记录审计
  - test_disable_role_deactivates_role:
    验证停用角色但保留角色授予
  - test_disable_role_rejects_builtin_role:
    验证不能停用系统保留角色
  - test_reset_password_revokes_existing_sessions:
    验证重置密码并撤销已有会话
  - test_disable_user_rejects_current_operator:
    验证不能停用当前登录用户
  - test_enable_user_rejects_deleted_user:
    验证启用命令提示重新创建已删除用户
  - test_delete_user_revokes_grants_and_sessions:
    验证逻辑删除用户并撤销授权和会话
  - test_delete_user_rejects_builtin_administrator:
    验证不能删除系统初始化创建的管理员账户
  - test_disable_user_rejects_builtin_administrator:
    验证不能停用系统初始化创建的管理员账户
  - test_update_user_replaces_profile:
    验证更新用户名、显示名称和邮箱
  - test_update_user_replaces_roles:
    验证编辑用户时替换角色授予
  - test_update_builtin_user_rejects_identity_changes:
    验证内置管理员账户的身份字段保持不变
  - test_update_builtin_user_requires_administrator_role:
    验证内置管理员账户必须保留管理员角色
  - test_change_password_verifies_current_password:
    验证当前用户修改密码并撤销登录会话
  - test_disable_user_preserves_last_administrator:
    验证保护最后一个系统管理员
  - test_grant_role_reactivates_existing_grant:
    验证重新激活已撤销角色授予
  - test_grant_role_allows_administrator:
    验证管理员角色可以授予其他受信任用户
  - test_revoke_role_preserves_last_administrator:
    验证不能撤销最后一个有效管理员的角色
  - test_delete_role_rejects_reserved_or_assigned_role:
    验证系统角色和仍被授予的角色不能删除
  - test_update_role_replaces_description_and_permissions:
    验证更新普通角色描述与权限
  - test_role_result_marks_builtin_role:
    测试角色结果标识内置管理员角色
  - test_delete_user_accepts_missing_reason:
    测试逻辑删除用户允许省略删除原因
  - test_delete_role_accepts_missing_reason:
    测试逻辑删除角色允许省略删除原因
"""

from datetime import (
    datetime,
    timezone,
)
from unittest.mock import (
    ANY,
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.services.identity as identity_module
from datamind.audit.enums import AuditSource
from datamind.context.core import get_context
from datamind.context.scope import context_scope
from datamind.db.models.grants import Grant
from datamind.db.models.roles import Role
from datamind.db.models.users import User
from datamind.services.errors import IdentityConflictError
from datamind.services.identity import IdentityService


CURRENT_TIME = datetime(
    2026,
    8,
    3,
    9,
    30,
    tzinfo=timezone.utc,
)


class FakeUnitOfWork:
    """身份服务测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user(
        **overrides: object,
) -> User:
    """创建用户测试对象."""
    values: dict[str, object] = {
        "user_id": "usr_analyst",
        "username": "analyst",
        "password_hash": "password-hash",
        "display_name": "分析员",
        "email": "analyst@example.com",
        "status": "active",
        "is_break_glass": False,
        "failed_login_count": 0,
        "locked_until": None,
        "last_login_at": None,
        "password_changed_at": CURRENT_TIME,
        "created_at": CURRENT_TIME,
        "updated_at": CURRENT_TIME,
        "deleted_at": None,
        "deleted_by": None,
        "deletion_reason": None,
    }
    values.update(
        overrides
    )

    return User(
        **values
    )


def create_role(
        **overrides: object,
) -> Role:
    """创建角色测试对象."""
    values: dict[str, object] = {
        "role_id": "rol_reader",
        "name": "model-reader",
        "description": "模型只读角色",
        "permissions": [
            "model.read"
        ],
        "status": "active",
        "created_at": CURRENT_TIME,
        "updated_at": CURRENT_TIME,
        "deleted_at": None,
        "deleted_by": None,
        "deletion_reason": None,
    }
    values.update(
        overrides
    )

    return Role(
        **values
    )


def create_grant(
        **overrides: object,
) -> Grant:
    """创建角色授予测试对象."""
    values: dict[str, object] = {
        "grant_id": "grt_test",
        "user_id": "usr_analyst",
        "role_id": "rol_reader",
        "status": "active",
    }
    values.update(
        overrides
    )

    return Grant(
        **values
    )


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    """配置身份服务仓储替身."""
    user_repo = MagicMock()
    role_repo = MagicMock()
    grant_repo = MagicMock()
    token_repo = MagicMock()
    audit_repo = MagicMock()

    replacements = {
        "UnitOfWork": FakeUnitOfWork,
        "UserRepository": lambda _session: user_repo,
        "RoleRepository": lambda _session: role_repo,
        "GrantRepository": lambda _session: grant_repo,
        "TokenRepository": lambda _session: token_repo,
        "AuditRepository": lambda _session: audit_repo,
        "hash_password": lambda _password: "new-password-hash",
        "generate_random_id": (
            lambda *, prefix: f"{prefix}_test"
        ),
    }

    for name, value in replacements.items():
        monkeypatch.setitem(
            vars(identity_module),
            name,
            value,
        )

    return (
        user_repo,
        role_repo,
        grant_repo,
        token_repo,
        audit_repo,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ["user", "role"])
@pytest.mark.parametrize("commit_fails", [False, True])
async def test_creation_logs_after_commit(
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        commit_fails: bool,
) -> None:
    """测试创建日志关联请求且仅在事务提交成功后报告完成."""
    user_repo, role_repo, _, _, audit_repo = configure_service(monkeypatch)
    user_repo.get_user = AsyncMock(return_value=None)
    user_repo.create_user.return_value = create_user()
    role_repo.get_role = AsyncMock(return_value=None)
    role_repo.create_role.return_value = create_role()
    committed = False
    events = []

    class CommitUnitOfWork(FakeUnitOfWork):
        async def __aexit__(self, *_args: object) -> bool:
            nonlocal committed
            if commit_fails:
                raise RuntimeError("commit failed")
            committed = True
            return False

    def record_log(message, **fields) -> None:
        events.append((message, {**get_context(), **fields}, committed))

    service_logger = MagicMock()
    service_logger.info.side_effect = record_log
    monkeypatch.setitem(vars(identity_module), "logger", service_logger)
    monkeypatch.setitem(vars(identity_module), "UnitOfWork", CommitUnitOfWork)
    context = {"request_id": "req_create", "trace_id": "a" * 32}
    service = IdentityService(audit_context=context)

    async def create() -> None:
        if resource == "user":
            await service.create_user(
                username="analyst",
                password="private-password",
                operator_id="usr_admin",
                operator="admin",
            )
        else:
            await service.create_role(
                name="model-reader",
                permissions=["model.read"],
                operator_id="usr_admin",
                operator="admin",
            )

    with context_scope(**context):
        if commit_fails:
            with pytest.raises(RuntimeError, match="commit failed"):
                await create()
        else:
            await create()

    label = "用户" if resource == "user" else "角色"
    assert events[0][0] == f"开始创建{label}"
    assert events[0][2] is False
    assert len(events) == (1 if commit_fails else 2)
    if not commit_fails:
        completed_message, completed_fields, after_commit = events[1]
        assert completed_message == f"{label}创建完成"
        assert after_commit is True
        assert completed_fields["action"] == f"{resource}.create"
        assert completed_fields["status"] == "success"
        for key in context:
            assert completed_fields[key] == events[0][1][key]
            assert completed_fields[key] == audit_repo.create_audit.call_args.kwargs[key]
    assert "private-password" not in repr(events)


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ["user", "role"])
async def test_identity_list_logs_at_debug(
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
) -> None:
    """测试用户和角色列表查询只记录调试日志."""
    user_repo, role_repo, *_ = configure_service(monkeypatch)
    user_repo.list_users = AsyncMock(return_value=[])
    role_repo.list_roles = AsyncMock(return_value=[])
    service_logger = MagicMock()
    monkeypatch.setitem(vars(identity_module), "logger", service_logger)
    service = IdentityService()

    if resource == "user":
        await service.list_users()
    else:
        await service.list_roles()

    service_logger.debug.assert_called_once()
    service_logger.info.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_creates_identity_and_initial_grants(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建用户及初始角色授予."""
    (
        user_repo,
        role_repo,
        grant_repo,
        _,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    role = create_role()
    user_repo.get_user = AsyncMock(
        return_value=None
    )
    user_repo.create_user.return_value = user
    role_repo.get_role = AsyncMock(
        return_value=role
    )

    result = await IdentityService().create_user(
        username=" analyst ",
        password="secret",
        display_name="分析员",
        email="analyst@example.com",
        role_names=[
            "model-reader"
        ],
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["username"] == "analyst"
    assert result["action"] == "create"
    assert result["roles"] == [
        "model-reader"
    ]
    user_repo.create_user.assert_called_once()
    grant_repo.create_grant.assert_called_once_with(
        grant_id="grt_test",
        user_id="usr_analyst",
        role_id="rol_reader",
        granted_by="usr_admin",
        granted_at=user.password_changed_at,
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_restores_deleted_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新创建已删除用户时恢复原记录."""
    (
        user_repo,
        role_repo,
        grant_repo,
        _,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user(
        status="disabled",
        deleted_at=CURRENT_TIME,
        deleted_by="usr_admin",
        deletion_reason="员工离职",
    )
    role = create_role()
    grant = create_grant(
        status="revoked"
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.get_grant = AsyncMock(
        return_value=grant
    )

    result = await IdentityService().create_user(
        username="analyst",
        password="new-secret",
        role_names=[
            "model-reader"
        ],
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["user_id"] == user.user_id
    assert result["action"] == "restore"
    assert result["roles"] == [
        "model-reader"
    ]
    user_repo.create_user.assert_not_called()
    user_repo.update_password.assert_called_once_with(
        user,
        password_hash="new-password-hash",
        changed_at=ANY,
        updated_by="usr_admin",
    )
    user_repo.restore_user.assert_called_once_with(
        user,
        restored_at=ANY,
        restored_by="usr_admin",
    )
    grant_repo.activate_grant.assert_called_once_with(
        grant,
        granted_by="usr_admin",
        granted_at=ANY,
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_create_role_rejects_builtin_role() -> None:
    """测试 administrator 只能由系统初始化创建."""
    with pytest.raises(
            IdentityConflictError,
            match="只能由 datamind init 创建",
    ):
        await IdentityService().create_role(
            name="administrator",
            permissions=[
                "*"
            ],
            operator_id="usr_admin",
            operator="admin",
        )


def test_role_result_marks_builtin_role() -> None:
    """测试角色结果标识内置管理员角色."""
    builtin = IdentityService._role_result(
        create_role(
            name="administrator"
        )
    )
    ordinary = IdentityService._role_result(
        create_role(
            name="developer"
        )
    )

    assert builtin["is_builtin"] is True
    assert ordinary["is_builtin"] is False


@pytest.mark.asyncio
async def test_create_role_restores_deleted_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新创建已删除角色时恢复原记录."""
    _, role_repo, _, _, audit_repo = configure_service(
        monkeypatch
    )
    role = create_role(
        name="developer",
        status="inactive",
        deleted_at=CURRENT_TIME,
        deleted_by="usr_admin",
        deletion_reason="角色停用",
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )

    result = await IdentityService().create_role(
        name="developer",
        permissions=[
            "model.read",
            "model.write",
        ],
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["role_id"] == role.role_id
    role_repo.create_role.assert_not_called()
    role_repo.replace_permissions.assert_called_once_with(
        role,
        permissions=[
            "model.read",
            "model.write",
        ],
        updated_by="usr_admin",
    )
    role_repo.restore_role.assert_called_once_with(
        role,
        restored_by="usr_admin",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permission",
    [
        "model.execute",
        "unknown.*",
        "MODEL.READ",
    ],
)
async def test_create_role_rejects_unsupported_permission(
        permission: str,
) -> None:
    """测试创建角色拒绝未注册权限."""
    with pytest.raises(
            ValueError,
            match="不支持的权限",
    ):
        await IdentityService().create_role(
            name="developer",
            permissions=[
                permission
            ],
            operator_id="usr_admin",
            operator="admin",
        )


@pytest.mark.asyncio
async def test_enable_role_activates_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用角色并记录审计."""
    _, role_repo, _, _, audit_repo = configure_service(
        monkeypatch
    )
    role = create_role(
        name="developer",
        status="inactive",
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )

    result = await IdentityService().enable_role(
        name="developer",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["name"] == "developer"
    role_repo.activate_role.assert_called_once_with(
        role,
        updated_by="usr_admin",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_disable_role_deactivates_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用角色但保留角色授予."""
    _, role_repo, grant_repo, _, audit_repo = configure_service(
        monkeypatch
    )
    role = create_role(
        name="developer"
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )

    result = await IdentityService().disable_role(
        name="developer",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["name"] == "developer"
    role_repo.deactivate_role.assert_called_once_with(
        role,
        updated_by="usr_admin",
    )
    grant_repo.revoke_grant.assert_not_called()
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_disable_role_rejects_builtin_role() -> None:
    """测试不能停用系统保留角色."""
    with pytest.raises(
            IdentityConflictError,
            match="系统保留角色",
    ):
        await IdentityService().disable_role(
            name="administrator",
            operator_id="usr_admin",
            operator="admin",
        )


@pytest.mark.asyncio
async def test_reset_password_revokes_existing_sessions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重置密码并撤销已有会话."""
    (
        user_repo,
        _,
        _,
        token_repo,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    token_repo.revoke_user_tokens = AsyncMock(
        return_value=[]
    )

    result = await IdentityService().reset_password(
        username="analyst",
        password="new-secret",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["username"] == "analyst"
    user_repo.update_password.assert_called_once_with(
        user,
        password_hash="new-password-hash",
        updated_by="usr_admin",
    )
    token_repo.revoke_user_tokens.assert_awaited_once_with(
        user_id="usr_analyst",
        revoked_by="usr_admin",
        revoke_reason="密码已重置",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_disable_user_rejects_current_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不能停用当前登录用户."""
    user_repo, _, _, _, _ = configure_service(
        monkeypatch
    )
    user_repo.get_user = AsyncMock(
        return_value=create_user()
    )

    with pytest.raises(
            IdentityConflictError,
            match="当前登录用户",
    ):
        await IdentityService().disable_user(
            username="analyst",
            operator_id="usr_analyst",
            operator="analyst",
        )


@pytest.mark.asyncio
async def test_enable_user_rejects_deleted_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用命令提示重新创建已删除用户."""
    user_repo, _, _, _, _ = configure_service(
        monkeypatch
    )
    user_repo.get_user = AsyncMock(
        return_value=create_user(
            status="disabled",
            deleted_at=CURRENT_TIME,
        )
    )

    with pytest.raises(
            IdentityConflictError,
            match="user create analyst",
    ):
        await IdentityService().enable_user(
            username="analyst",
            operator_id="usr_admin",
            operator="admin",
        )

    user_repo.activate_user.assert_not_called()


@pytest.mark.asyncio
async def test_delete_user_revokes_grants_and_sessions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除用户并撤销授权和会话."""
    (
        user_repo,
        role_repo,
        grant_repo,
        token_repo,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    grant = create_grant()
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        side_effect=[
            None,
            create_role(),
        ]
    )
    grant_repo.list_active_grants = AsyncMock(
        side_effect=[
            [
                grant
            ],
            [
                grant
            ],
        ]
    )
    token_repo.revoke_user_tokens = AsyncMock(
        return_value=[]
    )

    result = await IdentityService().delete_user(
        username="analyst",
        reason="员工离职",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["username"] == "analyst"
    grant_repo.revoke_grant.assert_called_once_with(
        grant,
        revoked_by="usr_admin",
    )
    token_repo.revoke_user_tokens.assert_awaited_once()
    user_repo.mark_deleted.assert_called_once_with(
        user,
        deleted_by="usr_admin",
        deletion_reason="员工离职",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user_accepts_missing_reason(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除用户允许省略删除原因."""
    (
        user_repo,
        role_repo,
        grant_repo,
        token_repo,
        _,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=None
    )
    grant_repo.list_active_grants = AsyncMock(
        side_effect=[
            [],
            [],
        ]
    )
    token_repo.revoke_user_tokens = AsyncMock(
        return_value=[]
    )

    await IdentityService().delete_user(
        username="analyst",
        operator_id="usr_admin",
        operator="admin",
    )

    user_repo.mark_deleted.assert_called_once_with(
        user,
        deleted_by="usr_admin",
        deletion_reason=None,
    )


@pytest.mark.asyncio
async def test_delete_user_rejects_builtin_administrator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不能删除系统初始化创建的管理员账户."""
    user_repo, _, _, token_repo, _ = configure_service(
        monkeypatch
    )
    user_repo.get_user = AsyncMock(
        return_value=create_user(
            user_id="usr_admin",
            username="admin",
            created_by="system:bootstrap",
        )
    )

    with pytest.raises(
            IdentityConflictError,
            match="内置管理员账户不能删除",
    ):
        await IdentityService().delete_user(
            username="admin",
            operator_id="usr_other_admin",
            operator="other-admin",
        )

    user_repo.mark_deleted.assert_not_called()
    token_repo.revoke_user_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_disable_user_rejects_builtin_administrator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不能停用系统初始化创建的管理员账户."""
    user_repo, _, _, token_repo, _ = configure_service(
        monkeypatch
    )
    user_repo.get_user = AsyncMock(
        return_value=create_user(
            user_id="usr_admin",
            username="admin",
            created_by="system:bootstrap",
        )
    )

    with pytest.raises(
            IdentityConflictError,
            match="内置管理员账户不能停用",
    ):
        await IdentityService().disable_user(
            username="admin",
            operator_id="usr_other_admin",
            operator="other-admin",
        )

    user_repo.disable_user.assert_not_called()
    token_repo.revoke_user_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_disable_user_preserves_last_administrator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保护最后一个系统管理员."""
    user_repo, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user(
        user_id="usr_admin",
        username="admin",
    )
    role = create_role(
        role_id="rol_admin",
        name="administrator",
        permissions=[
            "*"
        ],
    )
    grant = create_grant(
        user_id="usr_admin",
        role_id="rol_admin",
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.get_grant = AsyncMock(
        return_value=grant
    )
    grant_repo.list_active_grants = AsyncMock(
        return_value=[
            grant
        ]
    )

    with pytest.raises(
            IdentityConflictError,
            match="最后一个有效",
    ):
        await IdentityService().disable_user(
            username="admin",
            operator_id="usr_other_admin",
            operator="other-admin",
        )


@pytest.mark.asyncio
async def test_grant_role_reactivates_existing_grant(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新激活已撤销角色授予."""
    user_repo, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user()
    role = create_role()
    grant = create_grant(
        status="revoked"
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.get_grant = AsyncMock(
        return_value=grant
    )

    result = await IdentityService().grant_role(
        username="analyst",
        role_name="model-reader",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["username"] == "analyst"
    grant_repo.activate_grant.assert_called_once_with(
        grant,
        granted_by="usr_admin",
    )


@pytest.mark.asyncio
async def test_grant_role_allows_administrator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试管理员角色可以授予其他受信任用户."""
    user_repo, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user()
    role = create_role(
        role_id="rol_admin",
        name="administrator",
        permissions=[
            "*"
        ],
    )
    grant = create_grant(
        role_id=role.role_id
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.get_grant = AsyncMock(
        return_value=None
    )
    grant_repo.create_grant.return_value = grant

    result = await IdentityService().grant_role(
        username=user.username,
        role_name=role.name,
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["role"] == "administrator"
    grant_repo.create_grant.assert_called_once()


@pytest.mark.asyncio
async def test_revoke_role_preserves_last_administrator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不能撤销最后一个有效管理员的角色."""
    user_repo, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user(
        user_id="usr_admin",
        username="admin",
    )
    role = create_role(
        role_id="rol_admin",
        name="administrator",
        permissions=[
            "*"
        ],
    )
    grant = create_grant(
        user_id=user.user_id,
        role_id=role.role_id,
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.get_grant = AsyncMock(
        return_value=grant
    )
    grant_repo.list_active_grants = AsyncMock(
        return_value=[
            grant
        ]
    )

    with pytest.raises(
            IdentityConflictError,
            match="最后一个有效",
    ):
        await IdentityService().revoke_role(
            username=user.username,
            role_name=role.name,
            operator_id="usr_other_admin",
            operator="other-admin",
        )

    grant_repo.revoke_grant.assert_not_called()


@pytest.mark.asyncio
async def test_delete_role_rejects_reserved_or_assigned_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试系统角色和仍被授予的角色不能删除."""
    with pytest.raises(
            IdentityConflictError,
            match="系统保留角色",
    ):
        await IdentityService().delete_role(
            name="administrator",
            reason="test",
            operator_id="usr_admin",
            operator="admin",
        )

    _, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    role_repo.get_role = AsyncMock(
        return_value=create_role()
    )
    grant_repo.list_active_grants = AsyncMock(
        return_value=[
            create_grant()
        ]
    )

    with pytest.raises(
            IdentityConflictError,
            match="先撤销",
    ):
        await IdentityService().delete_role(
            name="model-reader",
            reason="test",
            operator_id="usr_admin",
            operator="admin",
        )


@pytest.mark.asyncio
async def test_delete_role_accepts_missing_reason(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除角色允许省略删除原因."""
    _, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    role = create_role()
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo.list_active_grants = AsyncMock(
        return_value=[]
    )

    await IdentityService().delete_role(
        name="model-reader",
        operator_id="usr_admin",
        operator="admin",
    )

    role_repo.mark_deleted.assert_called_once_with(
        role,
        deleted_by="usr_admin",
        deletion_reason=None,
    )


@pytest.mark.asyncio
async def test_update_user_replaces_profile(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试更新用户名、显示名称和邮箱."""
    (
        user_repo,
        _,
        grant_repo,
        _,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    user_repo.get_user = AsyncMock(
        side_effect=[
            user,
            user,
            None,
        ]
    )
    grant_repo.list_active_grants = AsyncMock(
        return_value=[]
    )

    result = await IdentityService(
        audit_source=AuditSource.HTTP,
        audit_context={
            "source": AuditSource.HTTP,
            "user": "admin",
            "request_id": "req_identity_update",
            "trace_id": (
                "0123456789abcdef0123456789abcdef"
            ),
            "ip": "127.0.0.1",
            "hostname": "console-host",
        },
    ).update_user(
        username="analyst",
        new_username="alice",
        display_name="Alice",
        email="alice@example.com",
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["user_id"] == "usr_analyst"
    user_repo.replace_profile.assert_called_once_with(
        user,
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        updated_by="usr_admin",
    )
    audit_repo.create_audit.assert_called_once()
    audit_call = audit_repo.create_audit.call_args
    assert audit_call.kwargs["request_id"] == (
        "req_identity_update"
    )
    assert audit_call.kwargs["trace_id"] == (
        "0123456789abcdef0123456789abcdef"
    )
    assert audit_call.kwargs["ip"] == "127.0.0.1"
    assert audit_call.kwargs["hostname"] == "console-host"
    assert audit_call.kwargs["context"] == {
        "source": "http",
        "user": "admin",
        "request_id": "req_identity_update",
        "trace_id": "0123456789abcdef0123456789abcdef",
        "ip": "127.0.0.1",
        "hostname": "console-host",
    }


@pytest.mark.asyncio
async def test_update_user_replaces_roles(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试编辑用户时替换角色授予."""
    (
        user_repo,
        role_repo,
        grant_repo,
        _,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    reader = create_role()
    writer = create_role(
        role_id="rol_writer",
        name="model-writer",
        permissions=[
            "model.read",
            "model.write",
        ],
    )
    reader_grant = create_grant()
    user_repo.get_user = AsyncMock(
        side_effect=[
            user,
            user,
        ]
    )

    async def get_role(
            *,
            role_id: str | None = None,
            name: str | None = None,
    ) -> Role | None:
        if role_id == reader.role_id:
            return reader

        if name == writer.name:
            return writer

        return None

    role_repo.get_role = AsyncMock(
        side_effect=get_role
    )
    grant_repo.list_active_grants = AsyncMock(
        side_effect=[
            [
                reader_grant,
            ],
            [
                reader_grant,
            ],
        ]
    )
    grant_repo.get_grant = AsyncMock(
        return_value=None
    )

    result = await IdentityService().update_user(
        username="analyst",
        new_username="analyst",
        role_names=[
            "model-writer",
        ],
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["roles"] == [
        "model-writer",
    ]
    grant_repo.revoke_grant.assert_called_once_with(
        reader_grant,
        revoked_by="usr_admin",
    )
    grant_repo.create_grant.assert_called_once_with(
        grant_id="grt_test",
        user_id="usr_analyst",
        role_id="rol_writer",
        granted_by="usr_admin",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "new_username",
        "display_name",
        "message",
    ),
    [
        (
            "renamed-admin",
            "系统管理员",
            "用户名不能修改",
        ),
        (
            "admin",
            "管理员",
            "显示名称不能修改",
        ),
    ],
)
async def test_update_builtin_user_rejects_identity_changes(
        monkeypatch: pytest.MonkeyPatch,
        new_username: str,
        display_name: str,
        message: str,
) -> None:
    """测试内置管理员账户的用户名和显示名称保持不变."""
    user_repo, _, _, _, _ = configure_service(
        monkeypatch
    )
    user = create_user(
        username="admin",
        display_name="系统管理员",
        created_by=(
            identity_module.SYSTEM_BOOTSTRAP_ACTOR
        ),
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )

    with pytest.raises(
            IdentityConflictError,
            match=message,
    ):
        await IdentityService().update_user(
            username="admin",
            new_username=new_username,
            display_name=display_name,
            operator_id="usr_admin",
            operator="admin",
        )

    user_repo.replace_profile.assert_not_called()


@pytest.mark.asyncio
async def test_update_builtin_user_requires_administrator_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试内置管理员账户不能取消 administrator 角色."""
    user_repo, _, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user(
        username="admin",
        display_name="系统管理员",
        created_by=(
            identity_module.SYSTEM_BOOTSTRAP_ACTOR
        ),
    )
    user_repo.get_user = AsyncMock(
        return_value=user
    )

    with pytest.raises(
            IdentityConflictError,
            match="必须保留 administrator 角色",
    ):
        await IdentityService().update_user(
            username="admin",
            new_username="admin",
            display_name="系统管理员",
            role_names=[
                "viewer",
            ],
            operator_id="usr_admin",
            operator="admin",
        )

    user_repo.replace_profile.assert_not_called()
    grant_repo.revoke_grant.assert_not_called()


@pytest.mark.asyncio
async def test_change_password_verifies_current_password(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试当前用户修改密码并撤销登录会话."""
    (
        user_repo,
        _,
        _,
        token_repo,
        audit_repo,
    ) = configure_service(
        monkeypatch
    )
    user = create_user()
    user_repo.get_user = AsyncMock(
        return_value=user
    )
    token_repo.revoke_user_tokens = AsyncMock(
        return_value=[]
    )
    monkeypatch.setitem(
        vars(identity_module),
        "verify_password",
        lambda *, password, password_hash: (
            password == "current-secret"
            and password_hash == "password-hash"
        ),
    )

    result = await IdentityService().change_password(
        username="analyst",
        current_password="current-secret",
        new_password="new-secret",
        operator_id="usr_analyst",
        operator="analyst",
    )

    assert result["username"] == "analyst"
    user_repo.update_password.assert_called_once_with(
        user,
        password_hash="new-password-hash",
        updated_by="usr_analyst",
    )
    token_repo.revoke_user_tokens.assert_awaited_once_with(
        user_id="usr_analyst",
        revoked_by="usr_analyst",
        revoke_reason="用户修改密码",
    )
    audit_repo.create_audit.assert_called_once()


@pytest.mark.asyncio
async def test_update_role_replaces_description_and_permissions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试更新普通角色描述与权限."""
    _, role_repo, _, _, audit_repo = configure_service(
        monkeypatch
    )
    role = create_role(
        name="developer"
    )
    role_repo.get_role = AsyncMock(
        return_value=role
    )

    result = await IdentityService().update_role(
        name="developer",
        description="模型开发角色",
        permissions=[
            "model.write",
            "model.read",
        ],
        operator_id="usr_admin",
        operator="admin",
    )

    assert result["name"] == "developer"
    role_repo.replace_description.assert_called_once_with(
        role,
        description="模型开发角色",
        updated_by="usr_admin",
    )
    role_repo.replace_permissions.assert_called_once_with(
        role,
        permissions=[
            "model.read",
            "model.write",
        ],
        updated_by="usr_admin",
    )
    audit_repo.create_audit.assert_called_once()
    audit_call = audit_repo.create_audit.call_args
    assert audit_call.kwargs["action"] == "role.update"
    assert audit_call.kwargs["operation"] == "update"
