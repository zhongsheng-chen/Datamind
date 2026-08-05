# datamind/db/repositories/request.py

"""请求仓储

提供请求及处理结果的查询与写入能力，
用于调用追踪、异常排查和性能分析。

核心功能：
  - get_request: 获取请求记录
  - list_requests: 获取请求记录列表
  - list_recent_requests: 获取最近请求列表
  - list_model_requests: 获取模型请求列表
  - create_request: 创建请求记录
  - mark_success: 标记请求处理成功
  - mark_failed: 标记请求处理失败

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.request import RequestRepository

  async with UnitOfWork() as uow:
      repo = RequestRepository(
          uow.session
      )

      request = repo.create_request(
          request_id="req_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          payload={
              "features": {
                  "age": 35,
                  "annual_income": 120000,
                  "debt_to_income_ratio": 0.32,
                  "credit_utilization_ratio": 0.45,
                  "delinquency_count": 0,
              },
          },
          source="http",
          user="system",
          ip="127.0.0.1",
      )

      repo.mark_success(
          request,
          response={
              "success": True,
              "request_id": request.request_id,
              "score": 680,
          },
          latency_ms=125.5,
      )
"""

from sqlalchemy import select

from datamind.db.models.requests import Request
from datamind.db.repositories.base import BaseRepository


class RequestRepository(BaseRepository):
    """请求仓储"""

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数"""
        if (
                limit is not None
                and limit < 0
        ):
            raise ValueError(
                "limit 不能小于 0"
            )

        if (
                offset is not None
                and offset < 0
        ):
            raise ValueError(
                "offset 不能小于 0"
            )

    @staticmethod
    def _validate_latency_ms(
            latency_ms: float | None,
    ) -> None:
        """校验处理耗时"""
        if (
                latency_ms is not None
                and latency_ms < 0
        ):
            raise ValueError(
                "latency_ms 不能小于 0"
            )

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
        stmt = select(
            Request
        ).where(
            Request.request_id
            == request_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_requests(
            self,
            *,
            request_id: str | None = None,
            model_id: str | None = None,
            source: str | None = None,
            status: str | None = None,
            user: str | None = None,
            ip: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Request]:
        """获取请求记录列表

        参数：
            request_id: 请求 ID（可选）
            model_id: 模型 ID（可选）
            source: 请求来源（可选）
            status: 请求状态（可选）
            user: 用户标识（可选）
            ip: 客户端 IP 地址（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            请求记录列表，按创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Request
        )

        if request_id is not None:
            stmt = stmt.where(
                Request.request_id
                == request_id
            )

        if model_id is not None:
            stmt = stmt.where(
                Request.model_id
                == model_id
            )

        if source is not None:
            stmt = stmt.where(
                Request.source
                == source
            )

        if status is not None:
            stmt = stmt.where(
                Request.status
                == status
            )

        if user is not None:
            stmt = stmt.where(
                Request.user
                == user
            )

        if ip is not None:
            stmt = stmt.where(
                Request.ip
                == ip
            )

        stmt = stmt.order_by(
            Request.created_at.desc()
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def list_recent_requests(
            self,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Request]:
        """获取最近请求列表

        参数：
            limit: 返回数量限制，默认 100
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
            limit: 返回数量限制，默认 100
            offset: 分页偏移（可选）

        返回：
            请求记录列表，按创建时间倒序排列
        """
        return await self.list_requests(
            model_id=model_id,
            limit=limit,
            offset=offset,
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

        新建请求固定处于 received 状态。

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

        异常：
            ValueError: latency_ms 小于 0
        """
        self._validate_latency_ms(
            latency_ms
        )

        new_request = Request(
            request_id=request_id,
            model_id=model_id,
            payload=payload,
            status="received",
        )

        if source is not None:
            new_request.source = source

        if latency_ms is not None:
            new_request.latency_ms = latency_ms

        if user is not None:
            new_request.user = user

        if ip is not None:
            new_request.ip = ip

        self.add(
            new_request
        )

        return new_request

    def mark_success(
            self,
            request: Request,
            *,
            response: dict | None = None,
            latency_ms: float | None = None,
    ) -> Request:
        """标记请求处理成功

        参数：
            request: 请求记录对象
            response: 请求处理结果（可选）
            latency_ms: 处理耗时（可选）

        返回：
            更新后的请求记录对象

        异常：
            ValueError: latency_ms 小于 0
        """
        self._validate_latency_ms(
            latency_ms
        )

        request.status = "success"
        request.error = None

        if response is not None:
            request.response = response

        if latency_ms is not None:
            request.latency_ms = latency_ms

        return request

    def mark_failed(
            self,
            request: Request,
            *,
            error: str,
            response: dict | None = None,
            latency_ms: float | None = None,
    ) -> Request:
        """标记请求处理失败

        参数：
            request: 请求记录对象
            error: 错误信息
            response: 请求处理结果（可选）
            latency_ms: 处理耗时（可选）

        返回：
            更新后的请求记录对象

        异常：
            ValueError: latency_ms 小于 0
        """
        self._validate_latency_ms(
            latency_ms
        )

        request.status = "failed"
        request.error = error

        if response is not None:
            request.response = response

        if latency_ms is not None:
            request.latency_ms = latency_ms

        return request
