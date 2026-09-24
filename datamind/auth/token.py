"""令牌工具.

提供访问令牌生成与解析、刷新令牌生成、哈希和校验能力。

核心功能：
  - create_access_token: 生成 JWT 访问令牌
  - decode_access_token: 解析并校验 JWT 访问令牌
  - generate_refresh_token: 生成刷新令牌
  - hash_refresh_token: 计算刷新令牌哈希
  - verify_refresh_token: 校验刷新令牌

使用示例：
  from datamind.auth.token import (
      create_access_token,
      decode_access_token,
      generate_refresh_token,
      hash_refresh_token,
      verify_refresh_token,
  )

  # 生成 JWT 访问令牌
  access_token = create_access_token(
      user_id="usr_0123456789abcdef",
      secret_key="replace-with-a-secure-secret",
      algorithm="HS256",
      expires_minutes=30,
      extra_claims={
          "username": "admin",
      },
  )

  # 解析并校验访问令牌
  payload = decode_access_token(
      token=access_token,
      secret_key="replace-with-a-secure-secret",
      algorithm="HS256",
  )

  # 生成刷新令牌
  refresh_token = generate_refresh_token()

  # 计算刷新令牌哈希，数据库中仅保存该哈希值
  refresh_token_hash = hash_refresh_token(
      refresh_token
  )

  # 校验客户端提交的刷新令牌是否与数据库中的哈希匹配
  verified = verify_refresh_token(
      refresh_token=refresh_token,
      token_hash=refresh_token_hash,
  )
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Any

import jwt
from jwt import InvalidTokenError


_RESERVED_CLAIMS: frozenset[str] = frozenset(
    {
        "sub",
        "type",
        "iat",
        "exp",
    }
)

_REFRESH_TOKEN_BYTES = 48


def create_access_token(
        *,
        user_id: str,
        secret_key: str,
        algorithm: str = "HS256",
        expires_minutes: int = 30,
        extra_claims: dict[str, Any] | None = None,
        issued_at: datetime | None = None,
) -> str:
    """生成 JWT 访问令牌.

    参数：
        user_id: 用户 ID
        secret_key: JWT 签名密钥
        algorithm: JWT 签名算法
        expires_minutes: 访问令牌有效时间，单位为分钟
        extra_claims: 附加声明（可选）
        issued_at: 签发时间（可选），默认使用当前 UTC 时间

    返回：
        JWT 访问令牌

    异常：
        ValueError: 参数为空、有效时间无效、时间缺少时区，
                    或附加声明覆盖保留声明
    """
    if user_id.strip() == "":
        raise ValueError(
            "user_id 不能为空"
        )

    if secret_key.strip() == "":
        raise ValueError(
            "secret_key 不能为空"
        )

    if algorithm.strip() == "":
        raise ValueError(
            "algorithm 不能为空"
        )

    if expires_minutes <= 0:
        raise ValueError(
            "expires_minutes 必须大于 0"
        )

    claims = dict(
        extra_claims
        or {}
    )

    conflicting_claims = (
        _RESERVED_CLAIMS
        & claims.keys()
    )

    if conflicting_claims:
        names = ", ".join(
            sorted(
                conflicting_claims
            )
        )
        raise ValueError(
            f"extra_claims 不得覆盖保留声明: {names}"
        )

    current_time = _normalize_utc_datetime(
        issued_at
        or datetime.now(
            timezone.utc
        ),
        field_name="issued_at",
    )

    claims.update(
        {
            "sub": user_id,
            "type": "access",
            "iat": current_time,
            "exp": (
                current_time
                + timedelta(
                    minutes=expires_minutes
                )
            ),
        }
    )

    return jwt.encode(
        claims,
        secret_key,
        algorithm=algorithm,
    )


def decode_access_token(
        *,
        token: str,
        secret_key: str,
        algorithm: str = "HS256",
) -> dict[str, Any] | None:
    """解析并校验 JWT 访问令牌.

    参数：
        token: JWT 访问令牌
        secret_key: JWT 签名密钥
        algorithm: JWT 签名算法

    返回：
        校验成功时返回令牌声明；
        令牌无效、过期、签名错误或类型错误时返回 None

    异常：
        ValueError: secret_key 或 algorithm 为空
    """
    if token == "":
        return None

    if secret_key.strip() == "":
        raise ValueError(
            "secret_key 不能为空"
        )

    if algorithm.strip() == "":
        raise ValueError(
            "algorithm 不能为空"
        )

    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=[
                algorithm
            ],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "exp",
                ]
            },
        )

    except InvalidTokenError:
        return None

    user_id = claims.get(
        "sub"
    )

    if (
            not isinstance(
                user_id,
                str,
            )
            or user_id.strip() == ""
    ):
        return None

    if claims.get(
            "type"
    ) != "access":
        return None

    return claims


def generate_refresh_token() -> str:
    """生成刷新令牌.

    返回：
        使用安全随机源生成的 URL 安全刷新令牌
    """
    return token_urlsafe(
        _REFRESH_TOKEN_BYTES
    )


def hash_refresh_token(
        refresh_token: str,
) -> str:
    """计算刷新令牌哈希.

    参数：
        refresh_token: 原始刷新令牌

    返回：
        SHA-256 十六进制哈希

    异常：
        ValueError: refresh_token 为空
    """
    if refresh_token == "":
        raise ValueError(
            "refresh_token 不能为空"
        )

    return sha256(
        refresh_token.encode(
            "utf-8"
        )
    ).hexdigest()


def verify_refresh_token(
        *,
        refresh_token: str,
        token_hash: str,
) -> bool:
    """校验刷新令牌.

    参数：
        refresh_token: 原始刷新令牌
        token_hash: 数据库保存的刷新令牌哈希

    返回：
        True 表示刷新令牌匹配，False 表示不匹配或参数为空
    """
    if (
            refresh_token == ""
            or token_hash == ""
    ):
        return False

    candidate_hash = hash_refresh_token(
        refresh_token
    )

    return compare_digest(
        candidate_hash,
        token_hash,
    )


def _normalize_utc_datetime(
        value: datetime,
        *,
        field_name: str,
) -> datetime:
    """转换为 UTC 时间.

    参数：
        value: 待转换时间
        field_name: 参数名称

    返回：
        UTC 时间

    异常：
        ValueError: 时间缺少时区信息
    """
    if (
            value.tzinfo is None
            or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} 必须包含时区信息"
        )

    return value.astimezone(
        timezone.utc
    )
