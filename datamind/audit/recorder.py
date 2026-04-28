# datamind/audit/recorder.py

"""审计记录器

统一封装审计日志写入，自动注入上下文信息。

核心功能：
  - AuditRecorder: 审计记录器，自动注入上下文信息

使用示例：
  from datamind.audit.recorder import AuditRecorder

  recorder = AuditRecorder(writer)
  recorder.record(
      action="model.register",
      target_type="model",
      target_id="mdl_001",
      after={"name": "scorecard"}
  )
"""

from typing import Optional, Dict

from datamind.context.core import get_context


class AuditRecorder:
    """审计记录器"""

    def __init__(self, writer):
        """初始化审计记录器

        参数：
            writer: AuditWriter 实例
        """
        self.writer = writer

    def record(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        before: Optional[Dict] = None,
        after: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ):
        """记录审计日志

        参数：
            action: 操作类型
            target_type: 目标类型
            target_id: 目标ID
            before: 变更前数据（可选）
            after: 变更后数据（可选）
            context: 操作上下文（可选）

        返回：
            审计记录对象
        """
        global_context = get_context()

        # 合并上下文
        merged_context = {**global_context, **(context or {})}

        user = merged_context.get("user")
        ip = merged_context.get("ip")

        return self.writer.write(
            user=user,
            ip=ip,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            context=merged_context,
        )