# datamind/db/writer/routing_writer.py

"""路由规则写入器

定义模型版本的流量分配规则，支持多种路由策略。

使用示例：
    writer = RoutingWriter(session)
    writer.write(
        model_id="mdl_001",
        strategy="WEIGHTED",
        config={"versions": {"1.0.0": 80, "2.0.0": 20}}
    )
"""

from datamind.db.models.routing import Routing
from datamind.db.writer.base_writer import BaseWriter


class RoutingWriter(BaseWriter):
    """路由规则写入器"""

    def write(
        self,
        *,
        model_id: str,
        strategy: str,
        config: dict,
        enabled: bool = True,
    ) -> Routing:
        """写入路由规则

        参数：
            model_id: 模型ID
            strategy: 路由策略
            config: 策略配置
            enabled: 是否启用

        返回：
            路由规则对象
        """
        obj = Routing(
            model_id=model_id,
            strategy=strategy,
            config=config,
            enabled=enabled,
        )
        self.add(obj)
        return obj