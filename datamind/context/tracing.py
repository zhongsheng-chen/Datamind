"""链路追踪 ID 工具.

提供链路追踪 ID 的生成与校验能力，
用于请求上下文、日志关联和审计追踪。

核心功能：
  - generate_trace_id: 生成标准链路追踪 ID
  - is_valid_trace_id: 校验链路追踪 ID

使用示例：
  from datamind.context.tracing import (
      generate_trace_id,
      is_valid_trace_id,
  )

  trace_id = generate_trace_id()

  if is_valid_trace_id(
      trace_id
  ):
      print(
          trace_id
      )
"""

import secrets
from typing import Final


TRACE_ID_LENGTH: Final[int] = 32

_HEX_CHARACTERS: Final[frozenset[str]] = frozenset(
    "0123456789abcdef"
)
_INVALID_TRACE_ID: Final[str] = "0" * TRACE_ID_LENGTH


def generate_trace_id() -> str:
    """生成链路追踪 ID.

    生成不带前缀的 32 位小写十六进制字符串，
    并排除全零值。

    返回：
        32 位小写十六进制链路追踪 ID
    """
    while True:
        trace_id = secrets.token_hex(
            TRACE_ID_LENGTH // 2
        )

        if trace_id != _INVALID_TRACE_ID:
            return trace_id


def is_valid_trace_id(
        trace_id: str | None,
) -> bool:
    """校验链路追踪 ID.

    合法值必须是 32 位小写十六进制字符串，
    且不能全为零。

    参数：
        trace_id: 待校验的链路追踪 ID

    返回：
        合法返回 True，否则返回 False
    """
    value = trace_id or ""

    if len(
            value
    ) != TRACE_ID_LENGTH:
        return False

    if value == _INVALID_TRACE_ID:
        return False

    return all(
        character in _HEX_CHARACTERS
        for character in value
    )
