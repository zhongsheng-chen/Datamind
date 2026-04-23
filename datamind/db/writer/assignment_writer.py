# datamind/db/writer/assignment_writer.py

"""分配记录写入器

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。

使用示例：
    writer = AssignmentWriter(session)
    writer.write(
        request_id="req-001",
        model_id="scorecard_v2",
        version="2.0.0",
        source="experiment",
        context={"experiment_id": "exp_001", "group": "B"},
    )
"""

from datetime import datetime

from datamind.db.models.assignments import Assignment
from datamind.db.writer.base_writer import BaseWriter


class AssignmentWriter(BaseWriter):
    """分配记录写入器"""

    def write(
        self,
        *,
        request_id: str,
        user_id: str = None,
        model_id: str,
        version: str,
        source: str,
        strategy: str = None,
        context: dict = None,
        routed_at: datetime = None,
    ) -> Assignment:
        """写入分配记录

        参数：
            request_id: 请求ID
            user_id: 用户ID
            model_id: 被分配的模型ID
            version: 被分配的版本
            source: 分配来源（routing/experiment/deployment）
            strategy: 分配策略
            context: 分配上下文
            routed_at: 分配时间

        返回：
            分配记录对象
        """
        obj = Assignment(
            request_id=request_id,
            user_id=user_id,
            model_id=model_id,
            version=version,
            source=source,
            strategy=strategy,
            context=context,
            routed_at=routed_at or datetime.utcnow(),
        )
        self.add(obj)
        return obj