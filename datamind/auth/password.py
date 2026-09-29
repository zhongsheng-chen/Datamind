"""密码工具.

提供密码哈希、密码校验和密码重哈希判断能力。

核心功能：
  - hash_password: 生成密码哈希
  - verify_password: 校验密码
  - needs_rehash: 判断密码哈希是否需要更新

使用示例：
  from datamind.auth.password import (
      hash_password,
      needs_rehash,
      verify_password,
  )

  # 对原始密码进行哈希处理，数据库中仅保存密码哈希
  password_hash = hash_password(
      "P@ssw1rd"
  )

  # 校验用户输入的密码是否与数据库中的密码哈希匹配
  verified = verify_password(
      password="P@ssw1rd",
      password_hash=password_hash,
  )

  # 检查现有密码哈希是否需要根据当前参数重新计算
  rehash_required = needs_rehash(
      password_hash
  )
"""

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
)


_PASSWORD_HASHER = PasswordHasher()


def hash_password(
        password: str,
) -> str:
    """生成密码哈希.

    参数：
        password: 明文密码

    返回：
        Argon2id 密码哈希

    异常：
        ValueError: password 为空
    """
    if password == "":
        raise ValueError(
            "password 不能为空"
        )

    return _PASSWORD_HASHER.hash(
        password
    )


def verify_password(
        *,
        password: str,
        password_hash: str,
) -> bool:
    """校验密码.

    参数：
        password: 明文密码
        password_hash: 密码哈希

    返回：
        True 表示密码匹配，False 表示密码不匹配或哈希无效
    """
    if password == "" or password_hash == "":
        return False

    try:
        return _PASSWORD_HASHER.verify(
            password_hash,
            password,
        )

    except (
        VerificationError,
        InvalidHashError,
    ):
        return False


def needs_rehash(
        password_hash: str,
) -> bool:
    """判断密码哈希是否需要更新.

    参数：
        password_hash: 密码哈希

    返回：
        True 表示需要重新生成密码哈希

    异常：
        ValueError: password_hash 为空或格式无效
    """
    if password_hash == "":
        raise ValueError(
            "password_hash 不能为空"
        )

    try:
        return _PASSWORD_HASHER.check_needs_rehash(
            password_hash
        )

    except InvalidHashError as exc:
        raise ValueError(
            "password_hash 格式无效"
        ) from exc
