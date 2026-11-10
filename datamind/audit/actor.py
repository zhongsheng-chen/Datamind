"""审计操作人上下文.

保存当前操作人的身份与组织归属快照，避免将人员资料写入普通日志或 JWT。

核心功能：
  - current_actor: 当前异步上下文中的操作人身份
  - actor_snapshot: 复制当前操作人的身份快照

说明：
  - CLI 作用域进入时设置快照，退出时恢复原值
  - HTTP 审计使用服务端认证结果中的快照
  - 快照记录操作时的名称与组织路径，不随之后的资料修改变化
"""

from contextvars import ContextVar
from copy import deepcopy
from typing import Any


current_actor: ContextVar[dict[str, Any] | None] = ContextVar(
    "audit_actor",
    default=None,
)


def actor_snapshot() -> dict[str, Any] | None:
    """复制当前操作人的身份快照.

    返回：
        独立的身份信息字典，没有已认证操作人时返回 None
    """
    actor = current_actor.get()
    return deepcopy(
        actor
    ) if actor else None
