# datamind/core/security/password.py

"""密码安全工具模块

提供密码哈希、验证、生成等功能，使用 bcrypt 算法保证密码安全。
"""

import bcrypt
import secrets
import string
from typing import Optional


def hash_password(password: str, rounds: int = 12) -> str:
    """哈希密码

    使用 bcrypt 算法对密码进行哈希处理。

    参数:
        password: 明文密码
        rounds: bcrypt 加密轮数，默认12（2^12次迭代）

    返回:
        bcrypt 哈希字符串

    示例:
        >>> hashed = hash_password("my_password")
        >>> len(hashed) > 0
        True
    """
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码

    检查明文密码是否与哈希值匹配。

    参数:
        password: 明文密码
        password_hash: bcrypt 哈希字符串

    返回:
        True 如果密码匹配，否则 False

    示例:
        >>> hashed = hash_password("my_password")
        >>> verify_password("my_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    except Exception:
        return False


def generate_random_password(length: int = 16,
                             include_digits: bool = True,
                             include_punctuation: bool = True) -> str:
    """生成随机密码

    生成安全的随机密码，可用于初始密码或重置密码。

    参数:
        length: 密码长度，默认16
        include_digits: 是否包含数字，默认True
        include_punctuation: 是否包含特殊字符，默认True

    返回:
        随机生成的密码字符串

    示例:
        >>> pwd = generate_random_password()
        >>> len(pwd) >= 16
        True
    """
    characters = string.ascii_letters
    if include_digits:
        characters += string.digits
    if include_punctuation:
        characters += "!@#$%^&*"

    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password


def generate_api_key(prefix: str = "dm_", length: int = 32) -> str:
    """生成API密钥

    生成格式化的API密钥，包含前缀和随机字符串。

    参数:
        prefix: 密钥前缀，默认 "dm_"
        length: 随机部分长度，默认32

    返回:
        格式化的API密钥，如 "dm_a1b2c3d4e5f6..."

    示例:
        >>> key = generate_api_key()
        >>> key.startswith("dm_")
        True
        >>> len(key) > 32
        True
    """
    random_part = secrets.token_hex(length // 2)  # hex 每字符代表4位
    return f"{prefix}{random_part}"


def hash_api_key(api_key: str) -> str:
    """哈希API密钥

    用于存储API密钥的哈希值，而不是明文。

    参数:
        api_key: 明文API密钥

    返回:
        API密钥的哈希值

    示例:
        >>> hashed = hash_api_key("dm_abc123")
        >>> len(hashed) > 0
        True
    """
    return bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """验证API密钥

    检查明文API密钥是否与哈希值匹配。

    参数:
        api_key: 明文API密钥
        key_hash: API密钥哈希值

    返回:
        True 如果匹配，否则 False
    """
    try:
        return bcrypt.checkpw(api_key.encode('utf-8'), key_hash.encode('utf-8'))
    except Exception:
        return False