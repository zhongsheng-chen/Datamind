# datamind/db/writer/audit_writer.py

"""审计日志写入器

记录系统所有变更行为，满足金融级审计要求。

使用示例：
    writer = AuditWriter(session)
    writer.write(
        user_id="admin",
        action="deployment.deploy",
        target_type="deployment",
        target_id="dep_001",
        after={"status": "active"}
    )
"""

from datetime import datetime

from datamind.db.models.audit import Audit
from datamind.db.writer.base_writer import BaseWriter


class AuditWriter(BaseWriter):
    """审计日志写入器"""

    def write(
        self,
        *,
        user_id: str = None,
        ip: str = None,
        action: str,
        target_type: str,
        target_id: str,
        before: dict = None,
        after: dict = None,
        context: dict = None,
        occurred_at: datetime = None,
    ) -> Audit:
        """写入审计日志

        参数：
            user_id: 操作者ID
            ip: 操作者IP
            action: 操作类型（resource.verb 格式）
            target_type: 目标类型
            target_id: 目标ID
            before: 变更前数据
            after: 变更后数据
            context: 操作上下文
            occurred_at: 操作时间

        返回：
            审计日志对象
        """
        obj = Audit(
            user_id=user_id,
            ip=ip,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            context=context,
            occurred_at=occurred_at or datetime.utcnow(),
        )
        self.add(obj)
        return obj