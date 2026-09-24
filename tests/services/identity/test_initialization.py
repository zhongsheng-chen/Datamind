"""系统初始化服务测试.

验证首次管理员、角色、授权、审计和初始化状态在同一工作单元中创建。

核心功能：
  - test_is_initialized_reads_system_state:
    验证查询初始化状态
  - test_initialize_creates_admin_identity:
    验证创建完整管理员身份
  - test_initialize_reuses_request_context:
    验证日志及审计复用调用上下文
  - test_initialize_rejects_completed_state:
    验证初始化只能执行一次
  - test_initialize_rejects_existing_users:
    验证已有用户时拒绝初始化
  - test_initialize_rejects_existing_admin_role:
    验证角色冲突时拒绝初始化
  - test_initialize_validates_credentials_and_time:
    验证初始化参数
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.services.initialization as initialization_module
from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.db.models.roles import Role
from datamind.db.models.system import SystemState
from datamind.db.models.users import User
from datamind.context.scope import context_scope
from datamind.services.errors import (
    AlreadyInitializedError,
    InitializationError,
)
from datamind.services.initialization import (
    InitializationService,
)


CURRENT_TIME = datetime(
    2026,
    8,
    2,
    8,
    30,
    tzinfo=timezone.utc,
)
TRACE_ID = "0123456789abcdef0123456789abcdef"


class FakeUnitOfWork:
    """系统初始化服务测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        state: SystemState | None,
        users: list[User] | None = None,
        role: Role | None = None,
) -> tuple[
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    """配置系统初始化服务仓储替身."""
    state_repo = MagicMock()
    state_repo.get_or_create_state = AsyncMock(
        return_value=state
    )
    state_repo.get_state = AsyncMock(
        return_value=state
    )
    user_repo = MagicMock()
    user_repo.list_users = AsyncMock(
        return_value=users or []
    )
    user_repo.create_user.return_value = User(
        user_id="usr_test",
        username="admin",
        password_hash="password-hash",
        status="active",
    )
    role_repo = MagicMock()
    role_repo.get_role = AsyncMock(
        return_value=role
    )
    grant_repo = MagicMock()
    audit_repo = MagicMock()

    replacements = {
        "UnitOfWork": FakeUnitOfWork,
        "SystemStateRepository": lambda _session: state_repo,
        "UserRepository": lambda _session: user_repo,
        "RoleRepository": lambda _session: role_repo,
        "GrantRepository": lambda _session: grant_repo,
        "AuditRepository": lambda _session: audit_repo,
        "hash_password": lambda _password: "password-hash",
        "generate_random_id": (
            lambda *, prefix: f"{prefix}_test"
        ),
        "generate_trace_id": lambda: TRACE_ID,
    }

    for name, value in replacements.items():
        monkeypatch.setitem(
            vars(initialization_module),
            name,
            value,
        )

    return (
        state_repo,
        user_repo,
        role_repo,
        grant_repo,
        audit_repo,
    )


@pytest.mark.asyncio
async def test_initialize_reuses_request_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化成功日志与审计复用调用方的请求标识."""
    *_, audit_repo = configure_service(
        monkeypatch,
        state=SystemState(system_id="datamind", initialized=False),
    )
    service_logger = MagicMock()
    monkeypatch.setitem(vars(initialization_module), "logger", service_logger)

    with context_scope(request_id="req_cli", trace_id="a" * 32):
        await InitializationService().initialize(
            username="admin",
            password="secret",
        )

    for fields in (
        audit_repo.create_audit.call_args.kwargs,
        service_logger.info.call_args.kwargs,
    ):
        assert fields["request_id"] == "req_cli"
        assert fields["trace_id"] == "a" * 32


@pytest.mark.asyncio
async def test_is_initialized_reads_system_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试查询系统初始化状态."""
    initialized_state = SystemState(
        system_id="datamind",
        initialized=True,
    )
    state_repo, *_ = configure_service(
        monkeypatch,
        state=initialized_state,
    )

    assert await InitializationService.is_initialized() is True
    state_repo.get_state.assert_awaited_once_with(
        system_id="datamind"
    )


@pytest.mark.asyncio
async def test_initialize_creates_admin_identity(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建完整管理员身份并标记系统已初始化."""
    service_logger = MagicMock()
    monkeypatch.setitem(vars(initialization_module), "logger", service_logger)
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )
    (
        state_repo,
        user_repo,
        role_repo,
        grant_repo,
        audit_repo,
    ) = configure_service(
        monkeypatch,
        state=state,
    )

    result = await InitializationService().initialize(
        username=" admin ",
        password="secret",
        ip="10.0.0.10",
        hostname="datamind-host",
        current_time=CURRENT_TIME,
    )

    assert result.system_id == "datamind"
    assert result.username == "admin"
    assert result.user_id == "usr_test"
    assert result.role_id == "rol_test"
    assert result.initialized_at == CURRENT_TIME
    service_logger.info.assert_called_once()
    log_fields = service_logger.info.call_args.kwargs
    audit_fields = audit_repo.create_audit.call_args.kwargs
    for key in ("request_id", "trace_id", "source", "user", "ip", "hostname"):
        assert log_fields[key] == audit_fields[key]
    assert log_fields["status"] == "success"
    assert "secret" not in repr(service_logger.mock_calls)
    user_repo.create_user.assert_called_once_with(
        user_id="usr_test",
        username="admin",
        password_hash="password-hash",
        display_name="Administrator",
        created_by="system:bootstrap",
    )
    created_user = user_repo.create_user.return_value
    assert created_user.password_changed_at == CURRENT_TIME
    role_repo.create_role.assert_called_once_with(
        role_id="rol_test",
        name="administrator",
        description="系统管理员角色",
        permissions=[
            "*"
        ],
        created_by="system:bootstrap",
    )
    grant_repo.create_grant.assert_called_once_with(
        grant_id="grt_test",
        user_id="usr_test",
        role_id="rol_test",
        granted_by="system:bootstrap",
        granted_at=CURRENT_TIME,
    )
    state_repo.mark_initialized.assert_called_once_with(
        state,
        initialized_at=CURRENT_TIME,
        initialized_by="system:bootstrap",
    )
    audit_repo.create_audit.assert_called_once_with(
        audit_id="aud_test",
        action="system.initialize",
        resource="system",
        operation="initialize",
        target_type="system",
        target_id="datamind",
        source=AuditSource.CLI,
        trace_id=TRACE_ID,
        request_id="req_test",
        user="system:bootstrap",
        ip="10.0.0.10",
        hostname="datamind-host",
        status=AuditStatus.SUCCESS,
        after={
            "initialized": True,
            "admin_user_id": "usr_test",
            "admin_username": "admin",
            "admin_role_id": "rol_test",
        },
        occurred_at=CURRENT_TIME,
    )


@pytest.mark.asyncio
async def test_initialize_rejects_completed_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化只能执行一次."""
    state = SystemState(
        system_id="datamind",
        initialized=True,
        initialized_at=CURRENT_TIME,
        initialized_by="system:bootstrap",
    )
    configure_service(
        monkeypatch,
        state=state,
    )

    with pytest.raises(
            AlreadyInitializedError,
            match="已经完成初始化",
    ):
        await InitializationService().initialize(
            username="admin",
            password="secret",
        )


@pytest.mark.asyncio
async def test_initialize_rejects_existing_users(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有用户时拒绝初始化."""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )
    user = User(
        user_id="usr_existing",
        username="alice",
        password_hash="password-hash",
        status="active",
    )
    configure_service(
        monkeypatch,
        state=state,
        users=[
            user
        ],
    )

    with pytest.raises(
            InitializationError,
            match="检测到已有用户",
    ):
        await InitializationService().initialize(
            username="admin",
            password="secret",
        )


@pytest.mark.asyncio
async def test_initialize_rejects_existing_admin_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试角色冲突时拒绝初始化."""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )
    role = Role(
        role_id="rol_existing",
        name="administrator",
        permissions=[
            "*"
        ],
        status="active",
    )
    configure_service(
        monkeypatch,
        state=state,
        role=role,
    )

    with pytest.raises(
            InitializationError,
            match="administrator 角色已经存在",
    ):
        await InitializationService().initialize(
            username="admin",
            password="secret",
        )


@pytest.mark.parametrize(
    (
        "kwargs",
        "message",
    ),
    [
        (
            {
                "username": " ",
                "password": "secret",
            },
            "管理员用户名不能为空",
        ),
        (
            {
                "username": "admin",
                "password": "",
            },
            "管理员密码不能为空",
        ),
        (
            {
                "username": "admin",
                "password": "secret",
                "current_time": datetime(
                    2026,
                    8,
                    2,
                ),
            },
            "current_time 必须包含时区信息",
        ),
    ],
)
@pytest.mark.asyncio
async def test_initialize_validates_credentials_and_time(
        kwargs: dict[str, Any],
        message: str,
) -> None:
    """测试初始化用户名、密码和时间."""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        await InitializationService().initialize(
            **kwargs
        )
