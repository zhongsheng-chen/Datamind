# datamind/audit/recorder.py

"""审计记录器

统一封装审计日志写入，自动注入上下文信息。

使用示例：
    recorder = AuditRecorder(session)
    recorder.record(
        action="deployment.deploy",
        target_type="deployment",
        target_id="dep_001",
        after={"status": "active"}
    )
"""

from typing import Dict, Optional, Any
from datetime import datetime

from datamind.db.writer.audit_writer import AuditWriter
from datamind.audit.context import get_context


class AuditRecorder:
    """审计记录器"""

    def __init__(self, session):
        """初始化记录器

        参数：
            session: 数据库会话
        """
        self.writer = AuditWriter(session)

    def record(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        before: Optional[Dict] = None,
        after: Optional[Dict] = None,
        context: Optional[Dict] = None,
        occurred_at: Optional[datetime] = None,
        return_record: bool = False,
    ) -> Optional[Any]:
        """记录审计事件

        参数：
            action: 操作类型（resource.verb 格式）
            target_type: 目标类型
            target_id: 目标ID
            before: 变更前数据（模型对象或字典）
            after: 变更后数据（模型对象或字典）
            context: 操作上下文（会与全局上下文合并）
            occurred_at: 操作时间
            return_record: 是否返回审计记录对象

        返回：
            审计记录对象（return_record=True 时）或 None
        """
        # 获取全局审计上下文
        audit_ctx = get_context()

        # 合并上下文
        final_context = {**audit_ctx, **(context or {})}

        record = self.writer.write(
            user_id=final_context.get("user_id"),
            ip=final_context.get("ip"),
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            context=final_context,
            occurred_at=occurred_at,
        )

        return record if return_record else None