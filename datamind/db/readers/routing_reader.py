# datamind/db/reader/routing_reader.py

"""路由规则读取器

用于查询模型版本的流量分发规则。

使用示例：
    reader = RoutingReader(session)

    routing = await reader.get_routing_policy("mdl_a1b2c3d4")
"""

from sqlalchemy import select

from datamind.db.models.routing import Routing
from datamind.db.readers.base_reader import BaseReader


class RoutingReader(BaseReader):
    """路由规则读取器"""

    async def get_routing_policy(self, model_id: str) -> Routing | None:
        """获取启用的路由策略

        参数：
            model_id: 模型 ID

        返回：
            路由规则对象，不存在时返回 None
        """
        stmt = select(Routing).where(
            Routing.model_id == model_id,
            Routing.enabled == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()