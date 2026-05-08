# datamind/db/writer/request_writer.py

"""请求写入器

记录进入系统的原始请求信息，用于请求追踪和性能分析。

使用示例：
    writer = RequestWriter(session)

    await writer.write(
        request_id="req_a1b2c3d4",
        model_id="mdl_a1b2c3d4",
        payload={"features": {"age": 35}},
        latency_ms=125.5
    )
"""

from datamind.db.models.requests import Request
from datamind.db.writers.base_writer import BaseWriter


class RequestWriter(BaseWriter):
    """请求写入器"""

    async def write(
        self,
        *,
        request_id: str,
        model_id: str,
        payload: dict = None,
        source: str = None,
        latency_ms: float = None,
        user: str = None,
        ip: str = None,
    ) -> Request:
        """写入请求记录

        参数：
            request_id: 请求唯一标识
            model_id: 目标模型ID
            payload: 请求负载
            source: 请求来源
            latency_ms: 处理耗时（毫秒）
            user: 用户
            ip: 客户端IP

        返回：
            请求对象
        """
        obj = Request(
            request_id=request_id,
            model_id=model_id,
            payload=payload,
            source=source,
            latency_ms=latency_ms,
            user=user,
            ip=ip,
        )

        self.add(obj)

        return obj