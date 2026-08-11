# datamind/db/repositories/runtime.py

"""模型运行仓储

提供模型运行状态的查询与管理能力。

核心功能：
  - get_runtime: 获取运行记录
  - get_deployment_runtime: 获取部署对应的运行记录
  - list_runtimes: 获取运行记录列表
  - list_running_runtimes: 获取运行中实例
  - mark_stale_runtimes_failed: 收敛失联的活动实例
  - create_runtime: 创建运行记录
  - update_runtime: 更新运行记录
  - set_applied_generation: 更新已应用控制版本号
  - mark_starting: 标记启动中
  - mark_running: 标记运行中
  - mark_stopping: 标记停止中
  - mark_stopped: 标记已停止
  - mark_failed: 标记加载失败
  - heartbeat: 更新运行心跳

使用示例：
  from datamind.constants import Framework
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.runtime import (
      RuntimePatch,
      RuntimeRepository,
  )

  async with UnitOfWork() as uow:
      repo = RuntimeRepository(
          uow.session
      )

      runtime = repo.create_runtime(
          runtime_id="rtm_0123456789abcdef",
          deployment_id="dep_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          version_id="ver_0123456789abcdef",
          framework=Framework.SKLEARN,
          worker_id="worker-1",
          started_by="admin",
      )
"""

from dataclasses import (
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    and_,
    func,
    or_,
    select,
)

from datamind.constants import Framework
from datamind.constants.runtime_status import ACTIVE_RUNTIME_STATUSES
from datamind.db.models import Deployment
from datamind.db.models.runtimes import Runtime
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class RuntimePatch:
    """运行更新结构

    注意：
        不允许通过 patch 修改 status 和生命周期时间字段，
        运行状态由生命周期方法控制。

    属性：
        framework: 框架类型
        worker_id: Worker 标识
        applied_generation: 已应用控制版本号
        error: 错误信息
        context: 运行上下文
    """

    framework: Framework | None = None
    worker_id: str | None = None
    applied_generation: int | None = None
    error: str | None = None
    context: dict | None = None


class RuntimeRepository(BaseRepository):
    """模型运行仓储"""

    async def get_runtime(
            self,
            runtime_id: str,
    ) -> Runtime | None:
        """获取运行记录

        参数：
            runtime_id: 运行 ID

        返回：
            运行记录对象，不存在时返回 None
        """
        stmt = select(
            Runtime
        ).where(
            Runtime.runtime_id
            == runtime_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_deployment_runtime(
            self,
            deployment_id: str,
            *,
            worker_id: str = "default",
    ) -> Runtime | None:
        """获取部署对应的运行记录

        参数：
            deployment_id: 部署 ID
            worker_id: Worker 标识，默认 default

        返回：
            运行记录对象，不存在时返回 None
        """
        stmt = select(
            Runtime
        ).where(
            Runtime.deployment_id
            == deployment_id,
            Runtime.worker_id
            == worker_id,
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_runtimes(
            self,
            *,
            runtime_id: str | None = None,
            deployment_id: str | None = None,
            model_id: str | None = None,
            version_id: str | None = None,
            framework: Framework | None = None,
            status: str | None = None,
            worker_id: str | None = None,
            started_by: str | None = None,
            stopped_by: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Runtime]:
        """获取运行记录列表

        参数：
            runtime_id: 运行 ID（可选）
            deployment_id: 部署 ID（可选）
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            framework: 框架类型（可选）
            status: 运行状态（可选）
            worker_id: Worker 标识（可选）
            started_by: 加载操作人（可选）
            stopped_by: 卸载操作人（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            运行记录列表，按更新时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
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

        stmt = select(
            Runtime
        )

        if runtime_id is not None:
            stmt = stmt.where(
                Runtime.runtime_id
                == runtime_id
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Runtime.deployment_id
                == deployment_id
            )

        if model_id is not None:
            stmt = stmt.where(
                Runtime.model_id
                == model_id
            )

        if version_id is not None:
            stmt = stmt.where(
                Runtime.version_id
                == version_id
            )

        if framework is not None:
            stmt = stmt.where(
                Runtime.framework
                == str(
                    framework
                )
            )

        if status is not None:
            stmt = stmt.where(
                Runtime.status
                == status
            )

        if worker_id is not None:
            stmt = stmt.where(
                Runtime.worker_id
                == worker_id
            )

        if started_by is not None:
            stmt = stmt.where(
                Runtime.started_by
                == started_by
            )

        if stopped_by is not None:
            stmt = stmt.where(
                Runtime.stopped_by
                == stopped_by
            )

        stmt = stmt.order_by(
            Runtime.updated_at.desc(),
            Runtime.created_at.desc(),
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

    async def list_running_runtimes(
            self,
            *,
            model_id: str | None = None,
            version_id: str | None = None,
            framework: Framework | None = None,
            worker_id: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Runtime]:
        """获取运行中实例

        参数：
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            framework: 框架类型（可选）
            worker_id: Worker 标识（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            运行中实例列表
        """
        return await self.list_runtimes(
            model_id=model_id,
            version_id=version_id,
            framework=framework,
            status="running",
            worker_id=worker_id,
            limit=limit,
            offset=offset,
        )

    async def mark_stale_runtimes_failed(
            self,
            *,
            environment: str,
            stale_before: datetime,
            exclude_worker_id: str | None = None,
    ) -> list[str]:
        """将指定环境中失联的活动实例标记为失败。"""
        if not environment:
            raise ValueError(
                "environment 不能为空"
            )

        stale = or_(
            and_(
                Runtime.status.in_(("starting", "stopping")),
                Runtime.updated_at < stale_before,
            ),
            and_(
                Runtime.status == "running",
                func.coalesce(
                    Runtime.last_heartbeat_at,
                    Runtime.updated_at,
                ) < stale_before,
            ),
        )
        stmt = (
            select(Runtime)
            .join(
                Deployment,
                Deployment.deployment_id
                == Runtime.deployment_id,
            )
            .where(
                Deployment.environment == environment,
                Runtime.status.in_(ACTIVE_RUNTIME_STATUSES),
                stale,
            )
        )

        if exclude_worker_id is not None:
            stmt = stmt.where(
                Runtime.worker_id != exclude_worker_id
            )

        result = await self.session.execute(stmt)
        runtimes = list(result.scalars().all())

        for runtime in runtimes:
            self.mark_failed(
                runtime,
                error="运行实例心跳超时，Worker 已失联",
            )

        return [
            runtime.runtime_id
            for runtime in runtimes
        ]

    def create_runtime(
            self,
            *,
            runtime_id: str,
            deployment_id: str,
            model_id: str,
            version_id: str,
            framework: Framework,
            worker_id: str = "default",
            loaded_at: datetime | None = None,
            unloaded_at: datetime | None = None,
            started_by: str | None = None,
            stopped_by: str | None = None,
            last_heartbeat_at: datetime | None = None,
            applied_generation: int | None = None,
            error: str | None = None,
            context: dict | None = None,
    ) -> Runtime:
        """创建运行记录

        新建运行记录默认处于 stopped 状态。

        参数：
            runtime_id: 运行 ID
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 框架类型
            worker_id: Worker 标识，默认 default
            loaded_at: 加载时间（可选）
            unloaded_at: 卸载时间（可选）
            started_by: 加载操作人（可选）
            stopped_by: 卸载操作人（可选）
            last_heartbeat_at: 最后心跳时间（可选）
            applied_generation: 已应用控制版本号（可选）
            error: 错误信息（可选）
            context: 运行上下文（可选）

        返回：
            创建后的运行记录对象
        """
        new_runtime = Runtime(
            runtime_id=runtime_id,
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=str(
                framework
            ),
            status="stopped",
            worker_id=worker_id,
            context=context,
        )

        if loaded_at is not None:
            new_runtime.loaded_at = loaded_at

        if unloaded_at is not None:
            new_runtime.unloaded_at = unloaded_at

        if started_by is not None:
            new_runtime.started_by = started_by

        if stopped_by is not None:
            new_runtime.stopped_by = stopped_by

        if last_heartbeat_at is not None:
            new_runtime.last_heartbeat_at = (
                last_heartbeat_at
            )

        if applied_generation is not None:
            new_runtime.applied_generation = (
                applied_generation
            )

        if error is not None:
            new_runtime.error = error

        self.add(
            new_runtime
        )

        return new_runtime

    def update_runtime(
            self,
            runtime: Runtime,
            patch: RuntimePatch,
    ) -> Runtime:
        """更新运行记录

        参数：
            runtime: 运行记录对象
            patch: 更新内容

        返回：
            更新后的运行记录对象
        """
        for field in fields(
                RuntimePatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    Framework,
            ):
                value = str(
                    value
                )

            setattr(
                runtime,
                field.name,
                value,
            )

        return runtime

    async def set_applied_generation(
            self,
            *,
            deployment_id: str,
            worker_id: str,
            generation: int,
    ) -> Runtime | None:
        """更新部署运行记录已应用的控制版本号

        参数：
            deployment_id: 部署 ID
            worker_id: Worker 标识
            generation: 已应用控制版本号

        返回：
            更新后的运行记录对象，不存在时返回 None
        """
        runtime = await self.get_deployment_runtime(
            deployment_id=deployment_id,
            worker_id=worker_id,
        )

        if runtime is None:
            return None

        runtime.applied_generation = generation

        return runtime

    def mark_starting(
            self,
            runtime: Runtime,
            *,
            started_by: str | None = None,
            context: dict | None = None,
    ) -> Runtime:
        """标记运行实例为启动中

        参数：
            runtime: 运行记录对象
            started_by: 加载操作人（可选）
            context: 运行上下文（可选）

        返回：
            更新后的运行记录对象
        """
        runtime.status = "starting"
        runtime.error = None
        runtime.unloaded_at = None

        if started_by is not None:
            runtime.started_by = started_by

        if context is not None:
            runtime.context = context

        return runtime

    def mark_running(
            self,
            runtime: Runtime,
            *,
            started_by: str | None = None,
            context: dict | None = None,
            loaded_at: datetime | None = None,
            applied_generation: int | None = None,
    ) -> Runtime:
        """标记运行实例为运行中

        参数：
            runtime: 运行记录对象
            started_by: 加载操作人（可选）
            context: 运行上下文（可选）
            loaded_at: 加载时间（可选）
            applied_generation: 已应用控制版本号（可选）

        返回：
            更新后的运行记录对象
        """
        timestamp = (
            loaded_at
            or datetime.now(
                timezone.utc
            )
        )

        runtime.status = "running"
        runtime.loaded_at = timestamp
        runtime.unloaded_at = None
        runtime.error = None
        runtime.last_heartbeat_at = timestamp

        if started_by is not None:
            runtime.started_by = started_by

        if context is not None:
            runtime.context = context

        if applied_generation is not None:
            runtime.applied_generation = (
                applied_generation
            )

        return runtime

    def mark_stopping(
            self,
            runtime: Runtime,
            *,
            stopped_by: str | None = None,
    ) -> Runtime:
        """标记运行实例为停止中"""
        runtime.status = "stopping"
        runtime.error = None

        if stopped_by is not None:
            runtime.stopped_by = stopped_by

        return runtime

    def mark_stopped(
            self,
            runtime: Runtime,
            *,
            stopped_by: str | None = None,
            context: dict | None = None,
            unloaded_at: datetime | None = None,
            applied_generation: int | None = None,
    ) -> Runtime:
        """标记运行实例为已停止

        参数：
            runtime: 运行记录对象
            stopped_by: 卸载操作人（可选）
            context: 运行上下文（可选）
            unloaded_at: 卸载时间（可选）
            applied_generation: 已应用控制版本号（可选）

        返回：
            更新后的运行记录对象
        """
        runtime.status = "stopped"
        runtime.unloaded_at = (
            unloaded_at
            or datetime.now(
                timezone.utc
            )
        )

        if stopped_by is not None:
            runtime.stopped_by = stopped_by

        if context is not None:
            runtime.context = context

        if applied_generation is not None:
            runtime.applied_generation = (
                applied_generation
            )

        return runtime

    def mark_failed(
            self,
            runtime: Runtime,
            *,
            error: str,
            started_by: str | None = None,
            context: dict | None = None,
    ) -> Runtime:
        """标记运行记录为失败

        参数：
            runtime: 运行记录对象
            error: 错误信息
            started_by: 加载操作人（可选）
            context: 运行上下文（可选）

        返回：
            更新后的运行记录对象
        """
        runtime.status = "failed"
        runtime.error = error

        if started_by is not None:
            runtime.started_by = started_by

        if context is not None:
            runtime.context = context

        return runtime

    def heartbeat(
            self,
            runtime: Runtime,
            *,
            heartbeat_at: datetime | None = None,
    ) -> Runtime:
        """更新运行心跳

        参数：
            runtime: 运行记录对象
            heartbeat_at: 心跳时间（可选）

        返回：
            更新后的运行记录对象
        """
        runtime.last_heartbeat_at = (
            heartbeat_at
            or datetime.now(
                timezone.utc
            )
        )

        return runtime
