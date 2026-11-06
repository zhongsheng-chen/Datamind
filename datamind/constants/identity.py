"""身份管理常量.

定义内置角色及其固定权限。

核心功能：
  - SYSTEM_BOOTSTRAP_ACTOR: 系统初始化操作人
  - ADMINISTRATOR_DISPLAY_NAME: 管理员默认显示名称
  - ADMINISTRATOR_ROLE_NAME: 管理员角色名称
  - EDITOR_ROLE_NAME: 编辑者角色名称
  - VIEWER_ROLE_NAME: 查看者角色名称
  - INVOKER_ROLE_NAME: 调用者角色名称
  - AUDITOR_ROLE_NAME: 审计员角色名称
  - BUILTIN_ROLE_PERMISSIONS: 内置角色的固定权限
  - BUILTIN_ROLE_DESCRIPTIONS: 内置角色的用途说明
  - BUILTIN_ROLE_NAMES: 内置角色名称集合

使用示例：
  from datamind.constants.identity import BUILTIN_ROLE_NAMES

  if role_name in BUILTIN_ROLE_NAMES:
      protect_builtin_role()
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import (
    Final,
    FrozenSet,
)


SYSTEM_BOOTSTRAP_ACTOR: Final[str] = "system:bootstrap"
ADMINISTRATOR_DISPLAY_NAME: Final[str] = "Administrator"
ADMINISTRATOR_ROLE_NAME: Final[str] = "administrator"
EDITOR_ROLE_NAME: Final[str] = "editor"
VIEWER_ROLE_NAME: Final[str] = "viewer"
INVOKER_ROLE_NAME: Final[str] = "invoker"
AUDITOR_ROLE_NAME: Final[str] = "auditor"
BUILTIN_ROLE_PERMISSIONS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType({
    ADMINISTRATOR_ROLE_NAME: ("*",),
    EDITOR_ROLE_NAME: (
        "model.read",
        "model.write",
        "deployment.read",
        "deployment.write",
        "experiment.read",
        "experiment.write",
        "routing.read",
        "routing.write",
        "runtime.read",
        "runtime.manage",
        "prediction.invoke",
    ),
    VIEWER_ROLE_NAME: (
        "model.read",
        "deployment.read",
        "experiment.read",
        "routing.read",
        "runtime.read",
    ),
    INVOKER_ROLE_NAME: (
        "prediction.invoke",
    ),
    AUDITOR_ROLE_NAME: (
        "audit.read",
        "request.read",
        "identity.read",
    ),
})
BUILTIN_ROLE_DESCRIPTIONS: Final[Mapping[str, str]] = MappingProxyType({
    ADMINISTRATOR_ROLE_NAME: "管理全部资源、用户和角色",
    EDITOR_ROLE_NAME: "创建和修改业务资源，管理模型运行并调用预测服务",
    VIEWER_ROLE_NAME: "查看模型、部署、实验、路由及其运行状态",
    INVOKER_ROLE_NAME: "调用预测服务，提交和管理批量预测任务",
    AUDITOR_ROLE_NAME: "查看审计记录、请求记录，以及用户、角色等身份信息",
})
BUILTIN_ROLE_NAMES: FrozenSet[str] = frozenset(BUILTIN_ROLE_PERMISSIONS)
