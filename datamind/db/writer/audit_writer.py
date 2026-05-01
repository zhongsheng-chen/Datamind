# datamind/db/writer/audit_writer.py

"""审计日志写入器

写入系统控制平面的操作事件。

使用示例：
    from datamind.db.writer.audit_writer import AuditWriter

    writer = AuditWriter(session)

    await writer.write(
        action="model.register",
        resource="model",
        operation="register",
        target_type="model",
        target_id="mdl_001",
        user="admin",
        after={"name": "scorecard"}
    )
"""

from datetime import datetime, timezone

from datamind.db.models.audit import Audit
from datamind.db.writer.base_writer import BaseWriter


class AuditWriter(BaseWriter):
    """审计日志写入器"""

    async def write(
        self,
        *,
        action: str,
        resource: str,
        operation: str,
        target_type: str,
        target_id: str,
        trace_id: str = None,
        request_id: str = None,
        user: str = None,
        ip: str = None,
        status: str = "success",
        error: str = None,
        before: dict = None,
        after: dict = None,
        context: dict = None,
        occurred_at: datetime = None,
    ) -> Audit:
        """写入审计日志

        参数：
            action: 操作类型，格式为 resource.operation
            resource: 资源类型
            operation: 操作名称
            target_type: 目标类型
            target_id: 目标 ID
            trace_id: 链路追踪 ID
            request_id: 请求 ID
            user: 操作者
            ip: 操作者 IP 地址
            status: 操作状态
            error: 错误信息
            before: 变更前数据
            after: 变更后数据
            context: 操作上下文
            occurred_at: 操作发生时间

        返回：
            审计日志对象
        """
        obj = Audit(
            action=action,
            resource=resource,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            trace_id=trace_id,
            request_id=request_id,
            user=user,
            ip=ip,
            status=status,
            error=error,
            before=before,
            after=after,
            context=context,
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )

        self.add(obj)

        return obj