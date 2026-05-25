# datamind/utils/id.py

"""ID 生成工具

提供统一的 ID 生成函数。

核心功能：
  - generate_id: 基于前缀和键值生成唯一 ID

使用示例：
  from datamind.utils.generator import generate_id

  # 生成模型 ID
  model_id = generate_id(
      prefix="mdl",
      keys=(name,),
  )

  # 生成版本 ID
  version_id = generate_id(
      prefix="ver",
      keys=(
          model_id,
          version,
      ),
  )

"""

import hashlib


def generate_id(
    *,
    prefix: str,
    keys: tuple[str, ...],
) -> str:
    """生成唯一 ID

    参数：
        prefix: ID 前缀
        keys: 用于生成哈希的键值列表

    返回：
        格式为 {prefix}_{8位MD5哈希} 的 ID
    """
    raw = ":".join(keys)

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

    return f"{prefix}_{digest}"