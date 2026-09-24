"""请求仓储.

提供请求及处理结果的查询与写入能力，
用于调用追踪、异常排查和性能分析。

核心功能：
  - get_request: 获取请求记录
  - list_requests: 获取请求记录列表
  - list_batch_requests: 获取批次请求记录
  - list_recent_requests: 获取最近请求列表
  - list_model_requests: 获取模型请求列表
  - create_request: 创建请求记录
  - mark_success: 标记请求处理成功
  - mark_failed: 标记请求处理失败
  - reset_for_retry: 重置批次请求的失败状态

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
          model_name="scorecard",
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
    """请求仓储."""

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数."""
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
        """校验处理耗时."""
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
        """获取请求记录.

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
            batch_id: str | None = None,
            model_id: str | None = None,
            source: str | None = None,
            status: str | None = None,
            user: str | None = None,
            ip: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Request]:
        """获取请求记录列表.

        参数：
            request_id: 请求 ID（可选）
            batch_id: 批次 ID（可选）
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

        if batch_id is not None:
            stmt = stmt.where(
                Request.batch_id
                == batch_id
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
        """获取最近请求列表.

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

    async def list_batch_requests(
            self,
            batch_id: str,
    ) -> list[Request]:
        """获取批次请求列表.

        参数：
            batch_id: 批次 ID

        返回：
            请求记录列表，按批次位置升序排列
        """
        stmt = (
            select(Request)
            .where(Request.batch_id == batch_id)
            .order_by(Request.batch_index.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_model_requests(
            self,
            model_id: str,
            *,
            limit: int | None = 100,
            offset: int | None = None,
    ) -> list[Request]:
        """获取模型请求列表.

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
            batch_id: str | None = None,
            batch_index: int | None = None,
            model_id: str | None = None,
            model_name: str | None = None,
            payload: dict | None = None,
            source: str | None = None,
            latency_ms: float | None = None,
            user: str | None = None,
            ip: str | None = None,
    ) -> Request:
        """创建请求记录.

        新建请求固定处于 received 状态。

        参数：
            request_id: 请求 ID
            batch_id: 批次 ID（可选）
            batch_index: 请求在批次中的位置（可选）
            model_id: 模型 ID（可选）
            model_name: 模型名称（可选）
            payload: 请求输入数据（可选）
            source: 请求来源（可选）
            latency_ms: 处理耗时（可选）
            user: 用户标识（可选）
            ip: 客户端 IP 地址（可选）

        返回：
            创建后的请求记录对象

        异常：
            ValueError: 批次字段不完整、批次位置小于 0，或 latency_ms 小于 0
        """
        self._validate_latency_ms(
            latency_ms
        )

        if (batch_id is None) != (batch_index is None):
            raise ValueError(
                "batch_id 和 batch_index 必须同时提供"
            )

        if batch_index is not None and batch_index < 0:
            raise ValueError(
                "batch_index 不能小于 0"
            )

        new_request = Request(
            request_id=request_id,
            payload=payload,
            status="received",
        )

        if batch_id is not None and batch_index is not None:
            new_request.batch_id = batch_id
            new_request.batch_index = batch_index

        if model_id is not None:
            new_request.model_id = model_id

        if model_name is not None:
            new_request.model_name = model_name

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
            model_id: str | None = None,
            decision_id: str | None = None,
            response: dict | None = None,
            latency_ms: float | None = None,
    ) -> Request:
        """标记请求处理成功.

        参数：
            request: 请求记录对象
            model_id: 模型 ID（可选）
            decision_id: 最近一次决策 ID（可选）
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

        if model_id is not None:
            request.model_id = model_id

        if decision_id is not None:
            request.latest_decision_id = decision_id

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
            model_id: str | None = None,
            decision_id: str | None = None,
            response: dict | None = None,
            latency_ms: float | None = None,
    ) -> Request:
        """标记请求处理失败.

        参数：
            request: 请求记录对象
            error: 错误信息
            model_id: 模型 ID（可选）
            decision_id: 最近一次决策 ID（可选）
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

        if model_id is not None:
            request.model_id = model_id

        if decision_id is not None:
            request.latest_decision_id = decision_id

        if response is not None:
            request.response = response

        if latency_ms is not None:
            request.latency_ms = latency_ms

        return request

    @staticmethod
    def reset_for_retry(request: Request) -> Request:
        """将未成功的批次请求重置为待处理状态."""
        if request.batch_id is None or request.batch_index is None:
            raise ValueError("只有批次请求可以重置后重试")

        if request.status not in {"received", "failed"}:
            raise ValueError(
                f"状态 {request.status} 的请求不能重试"
            )

        request.status = "received"
        request.response = None
        request.error = None
        request.latency_ms = None
        return request
