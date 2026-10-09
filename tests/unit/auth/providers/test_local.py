"""本地认证提供方测试.

验证本地认证配置、用户状态校验、密码校验、登录失败锁定、
临时锁定自动解除、密码哈希升级和统一身份返回逻辑。

核心功能：
  - test_local_provider_config_validates_parameters:
    验证本地认证配置参数
  - test_authenticate_requires_break_glass_user:
    验证应急模式拒绝普通本地账户
  - test_authenticate_returns_identity:
    验证本地认证成功并返回统一身份
  - test_authenticate_rejects_missing_user:
    验证用户不存在时拒绝认证
  - test_authenticate_rejects_non_local_user:
    验证非本地认证用户拒绝密码登录
  - test_authenticate_validates_user_status:
    验证停用、锁定和未知状态用户
  - test_authenticate_unlocks_expired_lock:
    验证临时锁定到期后自动解锁
  - test_authenticate_rejects_missing_password_hash:
    验证本地用户缺少密码哈希时拒绝认证
  - test_authenticate_records_login_failure:
    验证密码错误时记录登录失败
  - test_authenticate_locks_user_at_failure_threshold:
    验证达到失败阈值时锁定用户
  - test_authenticate_upgrades_password_hash:
    验证按当前 Argon2 参数升级密码哈希
  - test_authenticate_skips_password_hash_upgrade:
    验证关闭或无需升级时不更新密码哈希
  - test_authenticate_rejects_naive_current_time:
    验证拒绝不包含时区的当前时间
  - test_local_provider_config_uses_defaults:
    测试本地认证配置默认值
  - test_authenticate_does_not_disclose_disabled_user_for_wrong_password:
    测试密码错误时不暴露用户停用状态
  - test_authenticate_preserves_password_changed_at:
    测试升级密码哈希时保留原密码变更时间
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.auth.providers.local as local_module
from datamind.auth.enums import UserStatus
from datamind.auth.errors import (
    InvalidCredentialsError,
    UserDisabledError,
    UserLockedError,
)
from datamind.auth.providers import (
    LocalAuthProvider,
    LocalProviderConfig,
    PasswordCredentials,
)


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)


def create_user(
        **overrides: Any,
) -> SimpleNamespace:
    """创建本地认证测试用户."""
    values: dict[str, Any] = {
        "user_id": "usr_123456789abc",
        "username": "alice",
        "display_name": "Alice",
        "email": "alice@example.com",
        "status": str(
            UserStatus.ACTIVE
        ),
        "password_hash": "argon2-password-hash",
        "password_changed_at": None,
        "failed_login_count": 0,
        "locked_until": None,
        "is_break_glass": False,
    }
    values.update(
        overrides
    )

    return SimpleNamespace(
        **values
    )


def create_user_repo(
        *,
        user: SimpleNamespace | None = None,
) -> MagicMock:
    """创建用户仓储测试替身."""
    user_repo = MagicMock()
    user_repo.get_user = AsyncMock(
        return_value=user
    )

    return user_repo


@pytest.mark.parametrize(
    (
        "arguments",
        "expected_message",
    ),
    [
        (
            {
                "max_failed_login_attempts": 0,
            },
            (
                "max_failed_login_attempts "
                "必须大于 0"
            ),
        ),
        (
            {
                "max_failed_login_attempts": -1,
            },
            (
                "max_failed_login_attempts "
                "必须大于 0"
            ),
        ),
        (
            {
                "lock_minutes": 0,
            },
            "lock_minutes 必须大于 0",
        ),
        (
            {
                "lock_minutes": -1,
            },
            "lock_minutes 必须大于 0",
        ),
    ],
)
def test_local_provider_config_validates_parameters(
        arguments: dict[str, Any],
        expected_message: str,
) -> None:
    """测试本地认证配置参数."""
    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        LocalProviderConfig(
            **arguments
        )


def test_local_provider_config_uses_defaults() -> None:
    """测试本地认证配置默认值."""
    config = LocalProviderConfig()

    assert config.max_failed_login_attempts == 5
    assert config.lock_minutes == 30
    assert config.upgrade_password_hash is True
    assert config.break_glass_only is False


@pytest.mark.asyncio
async def test_authenticate_requires_break_glass_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应急模式拒绝普通本地账户."""
    user = create_user(
        is_break_glass=False
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo,
        config=LocalProviderConfig(
            break_glass_only=True
        ),
    )
    verify_password = MagicMock()

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        verify_password,
    )

    with pytest.raises(
            InvalidCredentialsError
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="P@ssw1rd",
            ),
            current_time=CURRENT_TIME,
        )

    verify_password.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_returns_identity(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地认证成功并返回统一身份."""
    user = create_user()
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "needs_rehash",
        lambda password_hash: False,
    )

    identity = await provider.authenticate(
        PasswordCredentials(
            username="alice",
            password="P@ssw1rd",
        ),
        current_time=CURRENT_TIME,
    )

    user_repo.get_user.assert_awaited_once_with(
        username="alice"
    )
    user_repo.record_login_success.assert_called_once_with(
        user,
        logged_in_at=CURRENT_TIME,
    )
    user_repo.record_login_failure.assert_not_called()
    user_repo.update_password.assert_not_called()

    assert identity.subject == user.user_id
    assert identity.username == user.username
    assert identity.display_name == user.display_name
    assert identity.email == user.email
    assert identity.claims[
        "user_id"
    ] == user.user_id
    assert identity.claims[
        "status"
    ] == str(
        UserStatus.ACTIVE
    )
    assert identity.claims[
        "password_rehashed"
    ] is False


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_user(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试用户不存在时拒绝认证."""
    user_repo = create_user_repo()
    provider = LocalAuthProvider(
        user_repo=user_repo
    )
    verify_password = MagicMock()

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        verify_password,
    )

    with pytest.raises(
            InvalidCredentialsError
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="missing-user",
                password="P@ssw1rd",
            ),
            current_time=CURRENT_TIME,
        )

    verify_password.assert_called_once_with(
        password="P@ssw1rd",
        password_hash=(
            local_module._DUMMY_PASSWORD_HASH
        ),
    )
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "status",
        "locked_until",
        "expected_error",
    ),
    [
        (
            UserStatus.DISABLED,
            None,
            UserDisabledError,
        ),
        (
            UserStatus.LOCKED,
            None,
            UserLockedError,
        ),
        (
            UserStatus.LOCKED,
            (
                CURRENT_TIME
                + timedelta(
                    minutes=30
                )
            ),
            UserLockedError,
        ),
        (
            "unknown",
            None,
            InvalidCredentialsError,
        ),
    ],
)
async def test_authenticate_validates_user_status(
        monkeypatch: pytest.MonkeyPatch,
        status: UserStatus | str,
        locked_until: datetime | None,
        expected_error: type[Exception],
) -> None:
    """测试停用、锁定和未知状态用户."""
    user = create_user(
        status=str(
            status
        ),
        locked_until=locked_until,
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )
    verify_password = MagicMock(
        return_value=True
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        verify_password,
    )

    with pytest.raises(
            expected_error
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="P@ssw1rd",
            ),
            current_time=CURRENT_TIME,
        )

    verify_password.assert_called_once_with(
        password="P@ssw1rd",
        password_hash=user.password_hash,
    )
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_does_not_disclose_disabled_user_for_wrong_password(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试密码错误时不暴露用户停用状态."""
    user = create_user(
        status=str(
            UserStatus.DISABLED
        )
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **_kwargs: False,
    )

    with pytest.raises(
            InvalidCredentialsError
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="wrong-password",
            ),
            current_time=CURRENT_TIME,
        )

    user_repo.record_login_failure.assert_not_called()
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_unlocks_expired_lock(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试临时锁定到期后自动解锁."""
    user = create_user(
        status=str(
            UserStatus.LOCKED
        ),
        locked_until=(
            CURRENT_TIME
            - timedelta(
                seconds=1
            )
        ),
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "needs_rehash",
        lambda password_hash: False,
    )

    identity = await provider.authenticate(
        PasswordCredentials(
            username="alice",
            password="P@ssw1rd",
        ),
        current_time=CURRENT_TIME,
    )

    user_repo.unlock_user.assert_called_once_with(
        user
    )
    user_repo.record_login_success.assert_called_once_with(
        user,
        logged_in_at=CURRENT_TIME,
    )
    assert identity.subject == user.user_id


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_password_hash(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地用户缺少密码哈希时拒绝认证."""
    user = create_user(
        password_hash=None
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )
    verify_password = MagicMock()

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        verify_password,
    )

    with pytest.raises(
            InvalidCredentialsError
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="P@ssw1rd",
            ),
            current_time=CURRENT_TIME,
        )

    verify_password.assert_not_called()
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_records_login_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试密码错误时记录登录失败."""
    user = create_user(
        failed_login_count=2
    )
    user_repo = create_user_repo(
        user=user
    )

    def record_login_failure(
            failed_user: SimpleNamespace,
    ) -> None:
        failed_user.failed_login_count += 1

    user_repo.record_login_failure.side_effect = (
        record_login_failure
    )
    provider = LocalAuthProvider(
        user_repo=user_repo,
        config=LocalProviderConfig(
            max_failed_login_attempts=5,
            lock_minutes=30,
        ),
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: False,
    )

    with pytest.raises(
            InvalidCredentialsError
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="wrong-password",
            ),
            current_time=CURRENT_TIME,
        )

    user_repo.record_login_failure.assert_called_once_with(
        user
    )
    assert user.failed_login_count == 3
    user_repo.lock_user.assert_not_called()
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_locks_user_at_failure_threshold(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试达到失败阈值时锁定用户."""
    user = create_user(
        failed_login_count=4
    )
    user_repo = create_user_repo(
        user=user
    )

    def record_login_failure(
            failed_user: SimpleNamespace,
    ) -> None:
        failed_user.failed_login_count += 1

    user_repo.record_login_failure.side_effect = (
        record_login_failure
    )
    provider = LocalAuthProvider(
        user_repo=user_repo,
        config=LocalProviderConfig(
            max_failed_login_attempts=5,
            lock_minutes=30,
        ),
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: False,
    )

    expected_locked_until = (
        CURRENT_TIME
        + timedelta(
            minutes=30
        )
    )

    with pytest.raises(
            UserLockedError,
            match="用户登录失败次数过多",
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="wrong-password",
            ),
            current_time=CURRENT_TIME,
        )

    user_repo.record_login_failure.assert_called_once_with(
        user
    )
    assert user.failed_login_count == 5
    user_repo.lock_user.assert_called_once_with(
        user,
        locked_until=expected_locked_until,
    )
    user_repo.record_login_success.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_upgrades_password_hash(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按当前 Argon2 参数升级密码哈希."""
    user = create_user(
        password_changed_at=None
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "needs_rehash",
        lambda password_hash: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "hash_password",
        lambda password: "new-password-hash",
    )

    identity = await provider.authenticate(
        PasswordCredentials(
            username="alice",
            password="P@ssw1rd",
        ),
        current_time=CURRENT_TIME,
    )

    user_repo.update_password.assert_called_once_with(
        user,
        password_hash="new-password-hash",
        changed_at=CURRENT_TIME,
    )
    user_repo.record_login_success.assert_called_once_with(
        user,
        logged_in_at=CURRENT_TIME,
    )
    assert identity.claims[
        "password_rehashed"
    ] is True


@pytest.mark.asyncio
async def test_authenticate_preserves_password_changed_at(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试升级密码哈希时保留原密码变更时间."""
    password_changed_at = (
        CURRENT_TIME
        - timedelta(
            days=10
        )
    )
    user = create_user(
        password_changed_at=password_changed_at
    )
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "needs_rehash",
        lambda password_hash: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "hash_password",
        lambda password: "new-password-hash",
    )

    await provider.authenticate(
        PasswordCredentials(
            username="alice",
            password="P@ssw1rd",
        ),
        current_time=CURRENT_TIME,
    )

    user_repo.update_password.assert_called_once_with(
        user,
        password_hash="new-password-hash",
        changed_at=password_changed_at,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "upgrade_password_hash",
        "needs_upgrade",
    ),
    [
        (
            False,
            True,
        ),
        (
            True,
            False,
        ),
    ],
)
async def test_authenticate_skips_password_hash_upgrade(
        monkeypatch: pytest.MonkeyPatch,
        upgrade_password_hash: bool,
        needs_upgrade: bool,
) -> None:
    """测试关闭或无需升级时不更新密码哈希."""
    user = create_user()
    user_repo = create_user_repo(
        user=user
    )
    provider = LocalAuthProvider(
        user_repo=user_repo,
        config=LocalProviderConfig(
            upgrade_password_hash=(
                upgrade_password_hash
            )
        ),
    )
    needs_rehash = MagicMock(
        return_value=needs_upgrade
    )
    hash_password = MagicMock(
        return_value="new-password-hash"
    )

    monkeypatch.setitem(
        vars(local_module),
        "verify_password",
        lambda **kwargs: True,
    )
    monkeypatch.setitem(
        vars(local_module),
        "needs_rehash",
        needs_rehash,
    )
    monkeypatch.setitem(
        vars(local_module),
        "hash_password",
        hash_password,
    )

    identity = await provider.authenticate(
        PasswordCredentials(
            username="alice",
            password="P@ssw1rd",
        ),
        current_time=CURRENT_TIME,
    )

    user_repo.update_password.assert_not_called()
    hash_password.assert_not_called()
    assert identity.claims[
        "password_rehashed"
    ] is False

    if upgrade_password_hash:
        needs_rehash.assert_called_once_with(
            user.password_hash
        )
    else:
        needs_rehash.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_rejects_naive_current_time() -> None:
    """测试拒绝不包含时区的当前时间."""
    user_repo = create_user_repo(
        user=create_user()
    )
    provider = LocalAuthProvider(
        user_repo=user_repo
    )

    with pytest.raises(
            ValueError,
            match="datetime 必须包含时区信息",
    ):
        await provider.authenticate(
            PasswordCredentials(
                username="alice",
                password="P@ssw1rd",
            ),
            current_time=datetime(
                2026,
                7,
                26,
                8,
                30,
            ),
        )

    user_repo.get_user.assert_not_awaited()
