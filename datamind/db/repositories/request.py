# datamind/db/repositories/request.py

"""请求仓储

提供系统原始请求记录的查询与写入能力，用于请求追踪与性能分析。

核心功能：
  - get_request: 获取请求记录
  - list_requests: 获取请求记录列表
  - list_recent_requests: 获取最近请求列表
  - list_model_requests: 获取模型请求列表
  - create_request: 创建请求记录

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import RequestRepository

  async with UnitOfWork() as uow:
      repo = RequestRepository(uow.session)

      request = repo.create_request(
          request_id="req_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          payload={"features": {"age": 35}},
          source="api",
          latency_ms=125.5,
          user="tom",
          ip="127.0.0.1"
      )
"""

from sqlalchemy import select

from datamind.db.models.requests import Request
from datamind.db.repositories.base import BaseRepository


class RequestRepository(BaseRepository):
    """请求仓储"""

    async def get_request(
        self,
        request_id: str,
    ) -> Request | None:
        """获取请求记录

        参数：
            request_id: 请求 ID

        返回：
            请求记录对象，不存在时返回 None
        """
        stmt = select(Request).where(Request.request_id == request_id)
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def list_requests(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        **filters,
    ) -> list[Request]:
        """获取请求记录列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            **filters: 过滤条件
                支持字段：
                    model_id
                    source
                    user
                    ip

        返回：
            请求记录列表，按创建时间倒序排列
        """
        stmt = select(Request)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(Request.created_at.desc())

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_recent_requests(
        self,
        *,
        limit: int | None = 100,
        offset: int | None = None,
    ) -> list[Request]:
        """获取最近请求列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            请求记录列表，按创建时间倒序排列
        """
        return await self.list_requests(
            limit=limit,
            offset=offset,
        )

    async def list_model_requests(
        self,
        model_id: str,
        *,
        limit: int | None = 100,
        offset: int | None = None,
    ) -> list[Request]:
        """获取模型请求列表

        参数：
            model_id: 模型 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            请求记录列表，按创建时间倒序排列
        """
        filters = {
            "model_id": model_id,
        }

        return await self.list_requests(
            limit=limit,
            offset=offset,
            **filters,
        )

    def create_request(
        self,
        *,
        request_id: str,
        model_id: str,
        payload: dict | None = None,
        source: str | None = None,
        latency_ms: float | None = None,
        user: str | None = None,
        ip: str | None = None,
    ) -> Request:
        """创建请求记录

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            payload: 请求输入数据（可选）
            source: 请求来源（可选）
            latency_ms: 处理耗时（可选）
            user: 用户标识（可选）
            ip: 客户端 IP 地址（可选）

        返回：
            创建后的请求记录对象
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