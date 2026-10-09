"""令牌工具测试.

验证 JWT 访问令牌的生成、解析和校验，以及刷新令牌的生成、
哈希和匹配能力。

核心功能：
  - test_create_access_token_creates_expected_claims:
    验证访问令牌包含标准声明和附加声明
  - test_create_access_token_normalizes_issued_at_to_utc:
    验证签发时间转换为 UTC
  - test_create_access_token_validates_parameters:
    验证访问令牌生成参数校验
  - test_create_access_token_rejects_reserved_claims:
    验证附加声明不能覆盖保留声明
  - test_create_access_token_rejects_naive_datetime:
    验证拒绝不包含时区的签发时间
  - test_decode_access_token_returns_valid_claims:
    验证正确解析访问令牌
  - test_decode_access_token_rejects_invalid_tokens:
    验证拒绝空令牌、签名错误、过期和格式无效令牌
  - test_decode_access_token_rejects_invalid_claims:
    验证拒绝缺少声明、用户 ID 无效和令牌类型错误
  - test_decode_access_token_validates_parameters:
    验证访问令牌解析参数校验
  - test_generate_refresh_token_creates_unique_urlsafe_tokens:
    验证生成唯一且 URL 安全的刷新令牌
  - test_hash_refresh_token_returns_sha256_hash:
    验证刷新令牌 SHA-256 哈希
  - test_hash_refresh_token_rejects_empty_token:
    验证拒绝空刷新令牌
  - test_verify_refresh_token_accepts_matching_token:
    验证匹配的刷新令牌
  - test_verify_refresh_token_rejects_invalid_values:
    验证拒绝不匹配或参数为空的刷新令牌
  - test_create_access_token_reports_all_reserved_claims:
    测试保留声明冲突信息按名称排序
  - test_decode_access_token_rejects_empty_or_invalid_token:
    测试拒绝空令牌和格式无效令牌
  - test_decode_access_token_rejects_wrong_signature:
    测试拒绝签名密钥错误的令牌
  - test_decode_access_token_rejects_wrong_algorithm:
    测试拒绝签名算法不匹配的令牌
  - test_decode_access_token_rejects_expired_token:
    测试拒绝已过期访问令牌
  - test_decode_access_token_rejects_missing_claims:
    测试拒绝缺少必需声明的令牌
  - test_decode_access_token_rejects_invalid_user_id:
    测试拒绝用户 ID 无效的令牌
  - test_decode_access_token_rejects_invalid_token_type:
    测试拒绝类型错误的令牌
  - test_verify_refresh_token_rejects_non_matching_token:
    测试拒绝不匹配的刷新令牌
  - test_verify_refresh_token_rejects_empty_values:
    测试刷新令牌或哈希为空时校验失败
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from hashlib import sha256
import re
from typing import Any

import jwt
import pytest

from datamind.auth.token import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_refresh_token,
)


SECRET_KEY = (
    "datamind-test-secret-key-for-hs256-and-hs512-"
    "0123456789abcdef0123456789abcdef"
)
ALGORITHM = "HS256"
USER_ID = "usr_0123456789abcdef"


def _encode_token(
        claims: dict[str, Any],
        *,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
) -> str:
    """生成指定声明的测试 JWT."""
    return jwt.encode(
        claims,
        secret_key,
        algorithm=algorithm,
    )


def _current_claims(
        **overrides: Any,
) -> dict[str, Any]:
    """创建当前有效的访问令牌声明."""
    issued_at = datetime.now(
        timezone.utc
    ) - timedelta(
        seconds=1
    )
    claims: dict[str, Any] = {
        "sub": USER_ID,
        "type": "access",
        "iat": issued_at,
        "exp": (
            issued_at
            + timedelta(
                minutes=30
            )
        ),
    }
    claims.update(
        overrides
    )

    return claims


def test_create_access_token_creates_expected_claims() -> None:
    """测试访问令牌包含标准声明和附加声明."""
    issued_at = datetime(
        2026,
        7,
        26,
        8,
        30,
        tzinfo=timezone.utc,
    )

    token = create_access_token(
        user_id=USER_ID,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
        expires_minutes=30,
        extra_claims={
            "username": "admin",
            "roles": [
                "administrator"
            ],
            "permissions": [
                "model.read"
            ],
        },
        issued_at=issued_at,
    )

    claims = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[
            ALGORITHM
        ],
        options={
            "verify_exp": False,
            "verify_iat": False,
        },
    )

    assert claims[
        "sub"
    ] == USER_ID
    assert claims[
        "type"
    ] == "access"
    assert claims[
        "iat"
    ] == int(
        issued_at.timestamp()
    )
    assert claims[
        "exp"
    ] == int(
        (
            issued_at
            + timedelta(
                minutes=30
            )
        ).timestamp()
    )
    assert claims[
        "username"
    ] == "admin"
    assert claims[
        "roles"
    ] == [
        "administrator"
    ]
    assert claims[
        "permissions"
    ] == [
        "model.read"
    ]


def test_create_access_token_normalizes_issued_at_to_utc() -> None:
    """测试签发时间转换为 UTC."""
    local_timezone = timezone(
        timedelta(
            hours=8
        )
    )
    issued_at = datetime(
        2026,
        7,
        26,
        16,
        30,
        tzinfo=local_timezone,
    )

    token = create_access_token(
        user_id=USER_ID,
        secret_key=SECRET_KEY,
        issued_at=issued_at,
    )

    claims = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[
            ALGORITHM
        ],
        options={
            "verify_exp": False,
            "verify_iat": False,
        },
    )

    expected_utc = datetime(
        2026,
        7,
        26,
        8,
        30,
        tzinfo=timezone.utc,
    )

    assert claims[
        "iat"
    ] == int(
        expected_utc.timestamp()
    )


@pytest.mark.parametrize(
    (
        "arguments",
        "expected_message",
    ),
    [
        (
            {
                "user_id": "",
                "secret_key": SECRET_KEY,
            },
            "user_id 不能为空",
        ),
        (
            {
                "user_id": USER_ID,
                "secret_key": "",
            },
            "secret_key 不能为空",
        ),
        (
            {
                "user_id": USER_ID,
                "secret_key": SECRET_KEY,
                "algorithm": "",
            },
            "algorithm 不能为空",
        ),
        (
            {
                "user_id": USER_ID,
                "secret_key": SECRET_KEY,
                "expires_minutes": 0,
            },
            "expires_minutes 必须大于 0",
        ),
        (
            {
                "user_id": USER_ID,
                "secret_key": SECRET_KEY,
                "expires_minutes": -1,
            },
            "expires_minutes 必须大于 0",
        ),
    ],
)
def test_create_access_token_validates_parameters(
        arguments: dict[str, Any],
        expected_message: str,
) -> None:
    """测试访问令牌生成参数校验."""
    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        create_access_token(
            **arguments
        )


@pytest.mark.parametrize(
    "reserved_claim",
    [
        "sub",
        "type",
        "iat",
        "exp",
    ],
)
def test_create_access_token_rejects_reserved_claims(
        reserved_claim: str,
) -> None:
    """测试附加声明不能覆盖保留声明."""
    with pytest.raises(
            ValueError,
            match=(
                "extra_claims 不得覆盖保留声明: "
                f"{reserved_claim}"
            ),
    ):
        create_access_token(
            user_id=USER_ID,
            secret_key=SECRET_KEY,
            extra_claims={
                reserved_claim: "override"
            },
        )


def test_create_access_token_reports_all_reserved_claims() -> None:
    """测试保留声明冲突信息按名称排序."""
    with pytest.raises(
            ValueError,
            match=(
                "extra_claims 不得覆盖保留声明: "
                "exp, sub, type"
            ),
    ):
        create_access_token(
            user_id=USER_ID,
            secret_key=SECRET_KEY,
            extra_claims={
                "type": "refresh",
                "exp": 0,
                "sub": "other-user",
            },
        )


def test_create_access_token_rejects_naive_datetime() -> None:
    """测试拒绝不包含时区的签发时间."""
    with pytest.raises(
            ValueError,
            match="issued_at 必须包含时区信息",
    ):
        create_access_token(
            user_id=USER_ID,
            secret_key=SECRET_KEY,
            issued_at=datetime(
                2026,
                7,
                26,
                8,
                30,
            ),
        )


def test_decode_access_token_returns_valid_claims() -> None:
    """测试正确解析访问令牌."""
    issued_at = datetime.now(
        timezone.utc
    ) - timedelta(
        seconds=1
    )
    token = create_access_token(
        user_id=USER_ID,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
        expires_minutes=30,
        extra_claims={
            "username": "admin"
        },
        issued_at=issued_at,
    )

    claims = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert claims is not None
    assert claims[
        "sub"
    ] == USER_ID
    assert claims[
        "type"
    ] == "access"
    assert claims[
        "username"
    ] == "admin"


@pytest.mark.parametrize(
    "token",
    [
        "",
        "invalid-token",
    ],
)
def test_decode_access_token_rejects_empty_or_invalid_token(
        token: str,
) -> None:
    """测试拒绝空令牌和格式无效令牌."""
    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


def test_decode_access_token_rejects_wrong_signature() -> None:
    """测试拒绝签名密钥错误的令牌."""
    token = _encode_token(
        _current_claims(),
        secret_key=(
            "other-test-secret-key-for-hs256-and-hs512-"
            "fedcba9876543210fedcba9876543210"
        ),
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


def test_decode_access_token_rejects_wrong_algorithm() -> None:
    """测试拒绝签名算法不匹配的令牌."""
    token = _encode_token(
        _current_claims(),
        algorithm="HS512",
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


def test_decode_access_token_rejects_expired_token() -> None:
    """测试拒绝已过期访问令牌."""
    issued_at = datetime.now(
        timezone.utc
    ) - timedelta(
        hours=1
    )
    token = _encode_token(
        {
            "sub": USER_ID,
            "type": "access",
            "iat": issued_at,
            "exp": (
                issued_at
                + timedelta(
                    minutes=30
                )
            ),
        }
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


@pytest.mark.parametrize(
    "missing_claim",
    [
        "sub",
        "type",
        "iat",
        "exp",
    ],
)
def test_decode_access_token_rejects_missing_claims(
        missing_claim: str,
) -> None:
    """测试拒绝缺少必需声明的令牌."""
    claims = _current_claims()
    claims.pop(
        missing_claim
    )
    token = _encode_token(
        claims
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


@pytest.mark.parametrize(
    "user_id",
    [
        "",
        "   ",
        123,
        None,
    ],
)
def test_decode_access_token_rejects_invalid_user_id(
        user_id: Any,
) -> None:
    """测试拒绝用户 ID 无效的令牌."""
    token = _encode_token(
        _current_claims(
            sub=user_id
        )
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


@pytest.mark.parametrize(
    "token_type",
    [
        "refresh",
        "",
        None,
    ],
)
def test_decode_access_token_rejects_invalid_token_type(
        token_type: Any,
) -> None:
    """测试拒绝类型错误的令牌."""
    token = _encode_token(
        _current_claims(
            type=token_type
        )
    )

    result = decode_access_token(
        token=token,
        secret_key=SECRET_KEY,
        algorithm=ALGORITHM,
    )

    assert result is None


@pytest.mark.parametrize(
    (
        "secret_key",
        "algorithm",
        "expected_message",
    ),
    [
        (
            "",
            ALGORITHM,
            "secret_key 不能为空",
        ),
        (
            SECRET_KEY,
            "",
            "algorithm 不能为空",
        ),
    ],
)
def test_decode_access_token_validates_parameters(
        secret_key: str,
        algorithm: str,
        expected_message: str,
) -> None:
    """测试访问令牌解析参数校验."""
    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        decode_access_token(
            token="non-empty-token",
            secret_key=secret_key,
            algorithm=algorithm,
        )


def test_generate_refresh_token_creates_unique_urlsafe_tokens() -> None:
    """测试生成唯一且 URL 安全的刷新令牌."""
    first_token = generate_refresh_token()
    second_token = generate_refresh_token()

    assert first_token != second_token
    assert len(
        first_token
    ) >= 64
    assert len(
        second_token
    ) >= 64
    assert re.fullmatch(
        r"[A-Za-z0-9_-]+",
        first_token,
    )
    assert re.fullmatch(
        r"[A-Za-z0-9_-]+",
        second_token,
    )


def test_hash_refresh_token_returns_sha256_hash() -> None:
    """测试刷新令牌 SHA-256 哈希."""
    refresh_token = "refresh-token-value"

    token_hash = hash_refresh_token(
        refresh_token
    )

    expected_hash = sha256(
        refresh_token.encode(
            "utf-8"
        )
    ).hexdigest()

    assert token_hash == expected_hash
    assert len(
        token_hash
    ) == 64


def test_hash_refresh_token_rejects_empty_token() -> None:
    """测试拒绝空刷新令牌."""
    with pytest.raises(
            ValueError,
            match="refresh_token 不能为空",
    ):
        hash_refresh_token(
            ""
        )


def test_verify_refresh_token_accepts_matching_token() -> None:
    """测试匹配的刷新令牌."""
    refresh_token = "refresh-token-value"
    token_hash = hash_refresh_token(
        refresh_token
    )

    result = verify_refresh_token(
        refresh_token=refresh_token,
        token_hash=token_hash,
    )

    assert result is True


def test_verify_refresh_token_rejects_non_matching_token() -> None:
    """测试拒绝不匹配的刷新令牌."""
    token_hash = hash_refresh_token(
        "expected-refresh-token"
    )

    result = verify_refresh_token(
        refresh_token="other-refresh-token",
        token_hash=token_hash,
    )

    assert result is False


@pytest.mark.parametrize(
    (
        "refresh_token",
        "token_hash",
    ),
    [
        (
            "",
            "token-hash",
        ),
        (
            "refresh-token",
            "",
        ),
        (
            "",
            "",
        ),
    ],
)
def test_verify_refresh_token_rejects_empty_values(
        refresh_token: str,
        token_hash: str,
) -> None:
    """测试刷新令牌或哈希为空时校验失败."""
    result = verify_refresh_token(
        refresh_token=refresh_token,
        token_hash=token_hash,
    )

    assert result is False
