"""模型名称格式

定义模型机器名称使用的格式约束。
"""

SUPPORTED_MODEL_NAME_PATTERN = (
    r"^[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?$"
)
