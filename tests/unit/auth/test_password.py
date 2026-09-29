"""密码工具测试.

验证 Argon2id 密码哈希、密码校验和密码重哈希判断能力。

核心功能：
  - test_hash_password_creates_argon2id_hash:
    验证生成 Argon2id 密码哈希
  - test_hash_password_uses_random_salt:
    验证相同密码生成不同哈希
  - test_hash_password_rejects_empty_password:
    验证拒绝空密码
  - test_verify_password_accepts_matching_password:
    验证正确密码校验成功
  - test_verify_password_rejects_incorrect_password:
    验证错误密码校验失败
  - test_verify_password_rejects_empty_values:
    验证空密码或空哈希校验失败
  - test_verify_password_rejects_invalid_hash:
    验证无效哈希校验失败
  - test_needs_rehash_accepts_current_parameters:
    验证当前 Argon2 参数不需要重新哈希
  - test_needs_rehash_detects_outdated_parameters:
    验证旧 Argon2 参数需要重新哈希
  - test_needs_rehash_rejects_empty_hash:
    验证拒绝空密码哈希
  - test_needs_rehash_rejects_invalid_hash:
    验证拒绝格式无效的密码哈希
"""

from argon2 import PasswordHasher
import pytest

from datamind.auth.password import (
    hash_password,
    needs_rehash,
    verify_password,
)


PASSWORD = "Datamind@123"


def test_hash_password_creates_argon2id_hash() -> None:
    """测试生成 Argon2id 密码哈希."""
    password_hash = hash_password(
        PASSWORD
    )

    assert password_hash.startswith(
        "$argon2id$"
    )
    assert PASSWORD not in password_hash


def test_hash_password_uses_random_salt() -> None:
    """测试相同密码生成不同哈希."""
    first_hash = hash_password(
        PASSWORD
    )
    second_hash = hash_password(
        PASSWORD
    )

    assert first_hash != second_hash
    assert verify_password(
        password=PASSWORD,
        password_hash=first_hash,
    )
    assert verify_password(
        password=PASSWORD,
        password_hash=second_hash,
    )


def test_hash_password_rejects_empty_password() -> None:
    """测试拒绝空密码."""
    with pytest.raises(
            ValueError,
            match="password 不能为空",
    ):
        hash_password(
            ""
        )


def test_verify_password_accepts_matching_password() -> None:
    """测试正确密码校验成功."""
    password_hash = hash_password(
        PASSWORD
    )

    result = verify_password(
        password=PASSWORD,
        password_hash=password_hash,
    )

    assert result is True


def test_verify_password_rejects_incorrect_password() -> None:
    """测试错误密码校验失败."""
    password_hash = hash_password(
        PASSWORD
    )

    result = verify_password(
        password="IncorrectPassword",
        password_hash=password_hash,
    )

    assert result is False


@pytest.mark.parametrize(
    (
        "password",
        "password_hash",
    ),
    [
        (
            "",
            "$argon2id$invalid",
        ),
        (
            PASSWORD,
            "",
        ),
        (
            "",
            "",
        ),
    ],
)
def test_verify_password_rejects_empty_values(
        password: str,
        password_hash: str,
) -> None:
    """测试空密码或空哈希校验失败."""
    result = verify_password(
        password=password,
        password_hash=password_hash,
    )

    assert result is False


@pytest.mark.parametrize(
    "password_hash",
    [
        "invalid-password-hash",
        "$argon2id$invalid",
        "$2b$12$not-an-argon2-hash",
    ],
)
def test_verify_password_rejects_invalid_hash(
        password_hash: str,
) -> None:
    """测试无效哈希校验失败."""
    result = verify_password(
        password=PASSWORD,
        password_hash=password_hash,
    )

    assert result is False


def test_needs_rehash_accepts_current_parameters() -> None:
    """测试当前 Argon2 参数不需要重新哈希."""
    password_hash = hash_password(
        PASSWORD
    )

    result = needs_rehash(
        password_hash
    )

    assert result is False


def test_needs_rehash_detects_outdated_parameters() -> None:
    """测试旧 Argon2 参数需要重新哈希."""
    outdated_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )
    password_hash = outdated_hasher.hash(
        PASSWORD
    )

    result = needs_rehash(
        password_hash
    )

    assert result is True


def test_needs_rehash_rejects_empty_hash() -> None:
    """测试拒绝空密码哈希."""
    with pytest.raises(
            ValueError,
            match="password_hash 不能为空",
    ):
        needs_rehash(
            ""
        )


@pytest.mark.parametrize(
    "password_hash",
    [
        "invalid-password-hash",
        "$argon2id$invalid",
        "$2b$12$not-an-argon2-hash",
    ],
)
def test_needs_rehash_rejects_invalid_hash(
        password_hash: str,
) -> None:
    """测试拒绝格式无效的密码哈希."""
    with pytest.raises(
            ValueError,
            match="password_hash 格式无效",
    ):
        needs_rehash(
            password_hash
        )
