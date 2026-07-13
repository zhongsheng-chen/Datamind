# tests/services/test_identity.py

"""身份管理服务测试

验证用户、角色、角色授予、令牌撤销和安全保护规则。

核心功能：
  - test_create_user_creates_identity_and_initial_grants:
    验证创建用户及初始角色授予
  - test_create_role_rejects_builtin_role:
    验证普通身份管理不能创建内置角色
  - test_create_role_restores_deleted_role:
    验证重新创建已删除角色时恢复原记录
  - test_create_role_rejects_unsupported_permission:
    验证创建角色拒绝未注册权限
  - test_reset_password_revokes_existing_sessions:
    验证重置密码并撤销已有会话
  - test_disable_user_rejects_current_operator:
    验证不能停用当前登录用户
  - test_delete_user_revokes_grants_and_sessions:
    验证逻辑删除用户并撤销授权和会话
  - test_disable_user_preserves_last_system_admin:
    验证保护最后一个系统管理员
  - test_grant_role_reactivates_existing_grant:
    验证重新激活已撤销角色授予
  - test_delete_role_rejects_reserved_or_assigned_role:
    验证系统角色和仍被授予的角色不能删除
"""

from datetime import (
    datetime,
    timezone,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.services.identity as identity_module
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
    """身份服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user(
        **overrides: object,
) -> User:
    """创建用户测试对象"""
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
    """创建角色测试对象"""
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
    """创建角色授予测试对象"""
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
    """配置身份服务仓储替身"""
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
async def test_create_user_creates_identity_and_initial_grants(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建用户及初始角色授予"""
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
async def test_create_role_rejects_builtin_role() -> None:
    """测试 system-admin 只能由系统初始化创建"""
    with pytest.raises(
            IdentityConflictError,
            match="只能由 datamind init 创建",
    ):
        await IdentityService().create_role(
            name="system-admin",
            permissions=[
                "*"
            ],
            operator_id="usr_admin",
            operator="admin",
        )


@pytest.mark.asyncio
async def test_create_role_restores_deleted_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新创建已删除角色时恢复原记录"""
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
    """测试创建角色拒绝未注册权限"""
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
async def test_reset_password_revokes_existing_sessions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重置密码并撤销已有会话"""
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
    """测试不能停用当前登录用户"""
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
async def test_delete_user_revokes_grants_and_sessions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试逻辑删除用户并撤销授权和会话"""
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
async def test_disable_user_preserves_last_system_admin(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保护最后一个系统管理员"""
    user_repo, role_repo, grant_repo, _, _ = configure_service(
        monkeypatch
    )
    user = create_user(
        user_id="usr_admin",
        username="admin",
    )
    role = create_role(
        role_id="rol_admin",
        name="system-admin",
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
    """测试重新激活已撤销角色授予"""
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
async def test_delete_role_rejects_reserved_or_assigned_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试系统角色和仍被授予的角色不能删除"""
    with pytest.raises(
            IdentityConflictError,
            match="系统保留角色",
    ):
        await IdentityService().delete_role(
            name="system-admin",
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
