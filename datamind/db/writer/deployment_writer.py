# datamind/db/writer/deployment_writer.py

"""部署写入器

记录模型版本在生产环境中的部署状态和流量分配。

使用示例：
    writer = DeploymentWriter(session)
    writer.write(
        model_id="mdl_001",
        version="1.0.0",
        status="active",
        traffic_ratio=1.0,
        deployed_by="system"
    )
"""

from datetime import datetime

from datamind.db.models.deployments import Deployment
from datamind.db.writer.base_writer import BaseWriter


class DeploymentWriter(BaseWriter):
    """部署写入器
    """

    def write(
        self,
        *,
        model_id: str,
        version: str,
        framework: str,
        status: str = "active",
        traffic_ratio: float = 1.0,
        effective_from: datetime = None,
        effective_to: datetime = None,
        deployed_by: str = None,
        description: str = None,
    ) -> Deployment:
        """写入部署记录

        参数：
            model_id: 模型ID
            version: 模型版本
            framework: 框架
            status: 部署状态
            traffic_ratio: 流量占比
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            deployed_by: 部署人
            description: 部署说明

        返回：
            部署对象
        """
        obj = Deployment(
            model_id=model_id,
            version=version,
            framework=framework,
            status=status,
            traffic_ratio=traffic_ratio,
            effective_from=effective_from,
            effective_to=effective_to,
            deployed_by=deployed_by,
            description=description,
        )
        self.add(obj)
        return obj