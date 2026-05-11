# datamind/db/writer/assignment_writer.py

"""分配记录写入器

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。

使用示例：
    writer = AssignmentWriter(session)

    await writer.write(
        assignment_id="asn_a1b2c3d4",
        request_id="req_a1b2c3d4",
        model_id="mdl_a1b2c3d4",
        version="ver_a1b2c3d4",
        deployment_id="dep_a1b2c3d4",
        experiment_id="exp_a1b2c3d4",
        customer_id="cus_a1b2c3d4",
        source="experiment",
        strategy="consistent",
        bucket="89",
        group="treatment",
        weight=0.1,
        context={"experiment_id": "exp_a1b2c3d4", "group": "treatment"}
    )
"""

from datetime import datetime, timezone

from datamind.db.models.assignments import Assignment
from datamind.db.writers.base_writer import BaseWriter


class AssignmentWriter(BaseWriter):
    """分配记录写入器"""

    async def write(
        self,
        *,
        assignment_id: str,
        request_id: str,
        model_id: str,
        version_id: str,
        deployment_id: str,
        experiment_id: str,
        customer_id: str,
        source: str,
        strategy: str = None,
        bucket: str = None,
        group: str = None,
        weight: float = None,
        context: dict = None,
        routed_at: datetime = None,
    ) -> Assignment:
        """写入分配记录

        参数：
            assignment_id: 分配 ID
            request_id: 请求 ID
            model_id: 被分配的模型 ID
            version_id: 被分配的版本 ID
            deployment_id: 命中的部署 ID
            experiment_id: 命中的实验 ID
            customer_id: 请求主体标识
            source: 路由来源
            strategy: 流量分配策略
            bucket: 分桶标识
            group: 实验分组
            weight: 分配权重
            context: 分配上下文
            routed_at: 路由分配时间

        返回：
            分配记录对象
        """
        obj = Assignment(
            assignment_id=assignment_id,
            request_id=request_id,
            model_id=model_id,
            version_id=version_id,
            deployment_id=deployment_id,
            experiment_id=experiment_id,
            customer_id=customer_id,
            source=source,
            strategy=strategy,
            bucket=bucket,
            group=group,
            weight=weight,
            context=context,
            routed_at=routed_at or datetime.now(timezone.utc),
        )

        self.add(obj)

        return obj