# datamind/utils/generator.py

"""ID 生成工具

提供统一的 ID 生成能力，支持确定性 ID 与随机 ID 两种模式。

核心功能：
  - generate_id: 基于前缀和键值生成确定性 ID，用于实体对象
  - generate_random_id: 生成随机 ID，用于事件类对象

使用示例：
  from datamind.utils.generator import (
      generate_id,
      generate_random_id,
  )

  # 生成模型 ID
  model_id = generate_id(
      prefix="mdl",
      keys=(name,),
  )

  # 生成版本 ID
  version_id = generate_id(
      prefix="ver",
      keys=(model_id, version),
  )

  # 生成部署 ID
  deployment_id = generate_random_id(
      prefix="dep"
  )
"""

import hashlib
import uuid


def generate_id(
        *,
        prefix: str,
        keys: tuple[str, ...],
) -> str:
    """生成唯一 ID

    基于 prefix 和 keys 计算 MD5 哈希生成稳定 ID，
    相同输入始终生成相同 ID。

    参数：
        prefix: ID 前缀
        keys: 用于生成哈希的键值列表

    返回：
        格式为 {prefix}_{8位MD5哈希} 的 ID
    """
    raw = ":".join(keys)

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

    return f"{prefix}_{digest}"


def generate_random_id(
        *,
        prefix: str,
) -> str:
    """生成随机 ID

    使用 UUID4 生成随机唯一 ID。

    参数：
        prefix: ID 前缀

    返回：
        格式为 {prefix}_{12位uuid} 的 ID
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
