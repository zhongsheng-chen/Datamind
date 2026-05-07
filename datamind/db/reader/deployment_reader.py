# datamind/db/reader/deployment_reader.py

"""部署读取器

用于查询模型版本的部署状态和流量分配。

使用示例：
    reader = DeploymentReader(session)

    active = await reader.get_active_deployments("mdl_a1b2c3d4")
    traffic = await reader.get_traffic_deployments("mdl_a1b2c3d4")
"""

from sqlalchemy import select

from datamind.db.models.deployments import Deployment
from datamind.db.reader.base_reader import BaseReader


class DeploymentReader(BaseReader):
    """部署读取器"""

    async def get_active_deployments(self, model_id: str) -> list[Deployment]:
        """获取当前生效部署

        参数：
            model_id: 模型 ID

        返回：
            生效中的部署列表
        """
        stmt = select(Deployment).where(
            Deployment.model_id == model_id,
            Deployment.status == "active",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_traffic_deployments(self, model_id: str) -> list[Deployment]:
        """获取有流量的部署

        参数：
            model_id: 模型 ID

        返回：
            流量占比大于 0 的部署列表
        """
        stmt = select(Deployment).where(
            Deployment.model_id == model_id,
            Deployment.traffic_ratio > 0,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())