# datamind/db/writer/deployment_writer.py

"""部署写入器

记录模型版本在生产环境中的部署状态和流量分配。

使用示例：
    writer = DeploymentWriter(session)

    await writer.write(
        deployment_id="dep_a1b2c3d4",
        model_id="mdl_a1b2c3d4",
        version_id="ver_a1b2c3d4",
        framework="sklearn",
        status="active",
        environment="production",
        rollout_type="full",
        variant="primary"
        traffic_ratio=1.0,
        deployed_by="system"
    )
"""

from datetime import datetime

from datamind.db.models.deployments import Deployment
from datamind.db.writers.base_writer import BaseWriter


class DeploymentWriter(BaseWriter):
    """部署写入器"""

    async def write(
        self,
        *,
        deployment_id: str,
        model_id: str,
        version_id: str,
        framework: str,
        status: str = "active",
        environment: str = "production",
        rollout_type: str = "full",
        variant: str = "primary",
        traffic_ratio: float = 1.0,
        effective_from: datetime = None,
        effective_to: datetime = None,
        deployed_by: str = None,
        description: str = None,
    ) -> Deployment:
        """写入部署记录

        参数：
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 框架类型
            status: 部署状态
            environment: 部署环境
            rollout_type: 发布类型
            variant: 部署角色
            traffic_ratio: 流量占比
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            deployed_by: 部署人
            description: 部署说明

        返回：
            部署对象
        """
        obj = Deployment(
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=framework,
            status=status,
            environment=environment,
            rollout_type=rollout_type,
            variant=variant,
            traffic_ratio=traffic_ratio,
            effective_from=effective_from,
            effective_to=effective_to,
            deployed_by=deployed_by,
            description=description,
        )

        self.add(obj)

        return obj