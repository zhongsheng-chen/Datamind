"""服务变更结果

定义携带响应数据和审计快照的服务变更结果。

核心功能：
  - MutationResult: 携带审计快照的服务变更结果

使用示例：
  from datamind.services.mutation import MutationResult

  result = MutationResult.changed(
      {"routing_id": "rtn_0123456789abcdef", "enabled": True},
      before={"enabled": False},
      after={"enabled": True},
  )
"""

from typing import Any


class MutationResult(dict[str, Any]):
    """携带响应数据和审计快照的服务变更结果"""

    def __init__(
            self,
            data: dict[str, Any],
            *,
            before: dict[str, Any] | None = None,
            after: dict[str, Any] | None = None,
    ) -> None:
        """初始化服务变更结果

        参数：
            data: 返回给调用方的响应数据
            before: 变更前的审计快照
            after: 变更后的审计快照
        """
        super().__init__(data)
        self.before = before
        self.after = after

    @classmethod
    def changed(
            cls,
            data: dict[str, Any],
            *,
            before: dict[str, Any],
            after: dict[str, Any],
    ) -> "MutationResult":
        """创建仅包含实际差异的服务变更结果

        参数：
            data: 返回给调用方的响应数据
            before: 变更前的完整数据
            after: 变更后的完整数据

        返回：
            仅保留变化字段的服务变更结果
        """
        keys = before.keys() | after.keys()
        changed_keys = {
            key for key in keys
            if before.get(key) != after.get(key)
        }
        return cls(
            data,
            before={key: before.get(key) for key in changed_keys},
            after={key: after.get(key) for key in changed_keys},
        )
