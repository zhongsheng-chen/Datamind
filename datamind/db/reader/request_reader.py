# datamind/db/reader/request_reader.py

"""请求读取器

用于查询系统原始请求记录，支持请求链路追踪与性能分析。

使用示例：
    reader = RequestReader(session)

    request = await reader.get_request("req_a1b2c3d4")
    recent = await reader.list_recent_requests(limit=50)
"""

from sqlalchemy import select

from datamind.db.models.requests import Request
from datamind.db.reader.base_reader import BaseReader


class RequestReader(BaseReader):
    """请求读取器"""

    async def get_request(self, request_id: str) -> Request | None:
        """获取单个请求记录

        参数：
            request_id: 请求唯一标识

        返回：
            请求对象，不存在时返回 None
        """
        stmt = select(Request).where(Request.request_id == request_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent_requests(
        self,
        limit: int = 100,
    ) -> list[Request]:
        """获取最近请求记录

        参数：
            limit: 返回记录数量上限，默认为 100

        返回：
            请求记录列表，按创建时间倒序排列
        """
        stmt = select(Request).order_by(Request.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_model_requests(
        self,
        model_id: str,
        limit: int = 100,
    ) -> list[Request]:
        """获取某个模型的请求记录

        参数：
            model_id: 模型 ID
            limit: 返回记录数量上限，默认为 100

        返回：
            请求记录列表，按创建时间倒序排列
        """
        stmt = (
            select(Request)
            .where(Request.model_id == model_id)
            .order_by(Request.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())