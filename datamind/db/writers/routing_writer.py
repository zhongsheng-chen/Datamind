# datamind/db/writer/routing_writer.py

"""路由规则写入器

用于管理模型版本的流量分发规则，支持多种路由策略。

使用示例：
    writer = RoutingWriter(session)

    await writer.write(
        model_id="mdl_a1b2c3d4",
        strategy="WEIGHTED",
        config={"versions": {"1.0.0": 80, "2.0.0": 20}}
    )
"""

from datamind.db.models.routing import Routing
from datamind.db.writers.base_writer import BaseWriter


class RoutingWriter(BaseWriter):
    """路由规则写入器"""

    async def write(
        self,
        *,
        routing_id: str,
        model_id: str,
        strategy: str,
        config: dict,
        name: str = None,
        enabled: bool = True,
    ) -> Routing:
        """写入路由规则

        参数：
            routing_id: 路由 ID
            model_id: 模型 ID
            strategy: 路由策略
            config: 策略配置
            name: 路由名称
            enabled: 是否启用

        返回：
            路由规则对象
        """
        obj = Routing(
            routing_id=routing_id,
            name=name,
            model_id=model_id,
            strategy=strategy,
            config=config,
            enabled=enabled,
        )

        self.add(obj)

        return obj