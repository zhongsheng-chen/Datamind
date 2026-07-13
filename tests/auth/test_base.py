# tests/auth/test_base.py

"""认证提供方基础结构测试

验证本地认证凭证、身份对象和提供方抽象接口。

核心功能：
  - 验证用户名密码凭证的规范化和保护
  - 验证认证身份的规范化和不可变语义
  - 验证认证提供方抽象接口
"""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from datamind.auth.providers import (
    BaseAuthProvider,
    PasswordCredentials,
    ProviderCredentials,
    ProviderIdentity,
)


def test_password_credentials_normalizes_username() -> None:
    """验证凭证规范化用户名"""
    credentials = PasswordCredentials(
        username="  alice  ",
        password="P@ssw1rd",
    )

    assert credentials.username == "alice"
    assert credentials.password == "P@ssw1rd"


def test_password_credentials_hides_password() -> None:
    """验证凭证字符串表示隐藏密码"""
    credentials = PasswordCredentials(
        username="alice",
        password="P@ssw1rd",
    )

    assert "P@ssw1rd" not in repr(
        credentials
    )


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("", "password", "username 不能为空"),
        ("   ", "password", "username 不能为空"),
        ("alice", "", "password 不能为空"),
    ],
)
def test_password_credentials_validates_fields(
        username: str,
        password: str,
        message: str,
) -> None:
    """验证凭证拒绝空必填字段"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        PasswordCredentials(
            username=username,
            password=password,
        )


def test_password_credentials_is_frozen() -> None:
    """验证凭证不可修改"""
    credentials = PasswordCredentials(
        username="alice",
        password="password",
    )

    with pytest.raises(FrozenInstanceError):
        credentials.username = "bob"  # type: ignore[misc]


def test_provider_credentials_aliases_password_credentials() -> None:
    """验证提供方凭证仅接受密码凭证"""
    credentials: ProviderCredentials = PasswordCredentials(
        username="alice",
        password="password",
    )

    assert isinstance(
        credentials,
        PasswordCredentials,
    )


def test_provider_identity_normalizes_fields() -> None:
    """验证认证身份规范化文本字段"""
    identity = ProviderIdentity(
        subject=" usr_test ",
        username=" alice ",
        display_name=" Alice ",
        email=" alice@example.com ",
        claims={
            "status": "active",
        },
    )

    assert identity.subject == "usr_test"
    assert identity.username == "alice"
    assert identity.display_name == "Alice"
    assert identity.email == "alice@example.com"
    assert identity.claims == {
        "status": "active",
    }


def test_provider_identity_normalizes_empty_optional_fields() -> None:
    """验证认证身份将空可选字段规范化为 None"""
    identity = ProviderIdentity(
        subject="usr_test",
        username="alice",
        display_name=" ",
        email=" ",
    )

    assert identity.display_name is None
    assert identity.email is None


@pytest.mark.parametrize(
    ("subject", "username", "message"),
    [
        ("", "alice", "subject 不能为空"),
        ("usr_test", "", "username 不能为空"),
    ],
)
def test_provider_identity_validates_required_fields(
        subject: str,
        username: str,
        message: str,
) -> None:
    """验证认证身份拒绝空必填字段"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        ProviderIdentity(
            subject=subject,
            username=username,
        )


def test_provider_identity_copies_and_protects_claims() -> None:
    """验证认证声明为只读快照"""
    claims = {
        "status": "active",
    }
    identity = ProviderIdentity(
        subject="usr_test",
        username="alice",
        claims=claims,
    )
    claims["status"] = "disabled"

    assert identity.claims["status"] == "active"

    with pytest.raises(TypeError):
        identity.claims["status"] = "locked"  # type: ignore[index]


def test_base_auth_provider_is_abstract() -> None:
    """验证认证提供方基类不能直接实例化"""
    with pytest.raises(TypeError):
        BaseAuthProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_base_auth_provider_contract() -> None:
    """验证实现类遵循认证接口"""
    expected = ProviderIdentity(
        subject="usr_test",
        username="alice",
    )

    class Provider(BaseAuthProvider):
        async def authenticate(
                self,
                credentials: PasswordCredentials,
                *,
                current_time: datetime | None = None,
        ) -> ProviderIdentity:
            assert credentials.username == "alice"
            assert current_time is None
            return expected

    result = await Provider().authenticate(
        PasswordCredentials(
            username="alice",
            password="password",
        )
    )

    assert result is expected
