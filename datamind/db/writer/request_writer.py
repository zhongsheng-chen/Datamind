# datamind/db/writer/request_writer.py

"""请求写入器

记录进入系统的原始请求信息，用于请求追踪和性能分析。

使用示例：
    writer = RequestWriter(session)
    writer.write(
        request_id="req-001",
        model_id="scorecard_v1",
        payload={"features": {"age": 35}},
        latency_ms=125.5
    )
"""

from datamind.db.models.requests import Request
from datamind.db.writer.base_writer import BaseWriter


class RequestWriter(BaseWriter):
    """请求写入器"""

    def write(
        self,
        *,
        request_id: str,
        user_id: str = None,
        model_id: str,
        payload: dict = None,
        source: str = None,
        ip: str = None,
        latency_ms: float = None,
    ) -> Request:
        """写入请求记录

        参数：
            request_id: 请求唯一标识
            user_id: 用户标识
            model_id: 目标模型ID
            payload: 请求输入
            source: 请求来源（api/batch/stream）
            ip: 客户端IP
            latency_ms: 处理耗时

        返回：
            请求对象
        """
        obj = Request(
            request_id=request_id,
            user_id=user_id,
            model_id=model_id,
            payload=payload,
            source=source,
            ip=ip,
            latency_ms=latency_ms,
        )
        self.add(obj)
        return obj