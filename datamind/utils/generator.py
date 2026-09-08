"""ID 生成工具

提供统一的 ID 生成能力，
支持确定性 ID 和随机 ID 两种模式。

核心功能：
  - generate_id: 根据前缀和键值生成稳定、可重复的 ID
  - generate_random_id: 根据前缀生成随机 ID

使用示例：
  from datamind.utils.generator import (
      generate_id,
      generate_random_id,
  )

  # 生成确定性 ID
  entity_id = generate_id(
      prefix="ent",
      keys=(
          "customer",
          "001",
      ),
  )

  # 生成随机 ID
  event_id = generate_random_id(
      prefix="evt"
  )
"""

import hashlib
import json
import uuid
from typing import Final


ID_LENGTH: Final[int] = 16


def generate_id(
        *,
        prefix: str,
        keys: tuple[str, ...],
) -> str:
    """生成确定性 ID

    对 prefix 和 keys 进行无歧义序列化，
    并计算 SHA-256 哈希。
    相同的 prefix 和 keys 始终生成相同 ID，
    keys 的顺序会影响生成结果。

    参数：
        prefix: ID 前缀
        keys: 用于生成哈希的键值元组

    返回：
        格式为 {prefix}_{16 位哈希} 的 ID

    异常：
        ValueError: prefix 或 keys 为空
    """
    normalized_prefix = prefix.strip()

    if not normalized_prefix:
        raise ValueError(
            "prefix 不能为空"
        )

    if not keys:
        raise ValueError(
            "keys 不能为空"
        )

    raw = json.dumps(
        {
            "prefix": normalized_prefix,
            "keys": keys,
        },
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    )

    digest = hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[
        :ID_LENGTH
    ]

    return (
        f"{normalized_prefix}_{digest}"
    )


def generate_random_id(
        *,
        prefix: str,
) -> str:
    """生成随机 ID

    使用 UUID4 生成随机唯一 ID。

    参数：
        prefix: ID 前缀

    返回：
        格式为 {prefix}_{16 位 UUID} 的 ID

    异常：
        ValueError: prefix 为空
    """
    normalized_prefix = prefix.strip()

    if not normalized_prefix:
        raise ValueError(
            "prefix 不能为空"
        )

    random_part = uuid.uuid4().hex[
        :ID_LENGTH
    ]

    return (
        f"{normalized_prefix}_{random_part}"
    )
