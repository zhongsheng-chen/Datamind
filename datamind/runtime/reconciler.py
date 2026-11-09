"""运行时状态协调器.

负责根据运行控制状态，
协调当前 Worker 的模型加载、重载与卸载。

核心功能：
  - start: 启动后台协调循环
  - stop: 停止后台协调循环
  - reconcile_once: 执行一次状态协调
  - get_applied_generation: 获取本 Worker 已应用版本
  - get_applied_generations: 获取全部已应用版本
  - is_running: 判断协调器是否正在运行

使用示例：
  from datamind.runtime.manager import RuntimeManager
  from datamind.runtime.reconciler import RuntimeReconciler

  manager = RuntimeManager(
      worker_id="worker-1"
  )

  reconciler = RuntimeReconciler(
      manager=manager,
      environment="production",
      interval_seconds=2.0,
      heartbeat_interval_seconds=30.0,
  )

  await reconciler.start()

  result = await reconciler.reconcile_once()

  print(result.to_dict())

  await reconciler.stop()
"""

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

import structlog
from sqlalchemy.exc import SQLAlchemyError

from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    ControlRepository,
    RuntimeRepository,
)
from datamind.models.enums import RuntimeControlStatus
from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    RuntimeRouteError,
    VersionNotFoundError,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.presence import RuntimePresence

logger = structlog.get_logger(__name__)

DEFAULT_INTERVAL_SECONDS = 2.0

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0

_HEARTBEAT_FAILURE_LOG_INTERVAL_SECONDS = 60.0

DEFAULT_OPERATOR = "system"


@dataclass(frozen=True, slots=True)
class ControlSnapshot:
    """运行控制状态快照.

    属性：
        deployment_id: 部署 ID
        environment: 运行环境
        desired_status: 期望运行状态
        generation: 控制版本号
        updated_by: 最近更新人
    """

    deployment_id: str

    environment: str

    desired_status: RuntimeControlStatus

    generation: int

    updated_by: str | None = None


@dataclass(slots=True)
class ReconcileResult:
    """单次协调结果.

    属性：
        checked: 检查数量
        loaded: 加载数量
        unloaded: 卸载数量
        reloaded: 重新加载数量
        unchanged: 无需处理数量
        failed: 失败数量
    """

    checked: int = 0

    loaded: int = 0

    unloaded: int = 0

    reloaded: int = 0

    unchanged: int = 0

    failed: int = 0

    def record(
            self,
            action: str,
    ) -> None:
        """记录协调动作.

        参数：
            action: 动作名称

        异常：
            ValueError: 未知协调动作
        """
        if action == "loaded":
            self.loaded += 1
            return

        if action == "unloaded":
            self.unloaded += 1
            return

        if action == "reloaded":
            self.reloaded += 1
            return

        if action == "unchanged":
            self.unchanged += 1
            return

        raise ValueError(
            f"未知协调动作: {action}",
        )

    def to_dict(
            self,
    ) -> dict[str, int]:
        """转换为字典."""
        return {
            "checked": self.checked,
            "loaded": self.loaded,
            "unloaded": self.unloaded,
            "reloaded": self.reloaded,
            "unchanged": self.unchanged,
            "failed": self.failed,
        }


class RuntimeReconciler:
    """运行时状态协调器.

    每个 Worker 使用独立实例，定期读取当前环境的运行控制状态。
    根据期望状态协调模型加载、重载与卸载。
    """

    def __init__(
            self,
            *,
            manager: RuntimeManager,
            environment: str,
            interval_seconds: float = (
                DEFAULT_INTERVAL_SECONDS
            ),
            heartbeat_interval_seconds: float = (
                DEFAULT_HEARTBEAT_INTERVAL_SECONDS
            ),
            operator: str = DEFAULT_OPERATOR,
            service_id: str | None = None,
    ):
        """初始化运行时状态协调器.

        参数：
            manager:
                当前 Worker 的 RuntimeManager

            environment:
                当前 Worker 所属运行环境

            interval_seconds:
                状态协调间隔，单位秒，默认值为 2

            heartbeat_interval_seconds:
                运行时心跳更新间隔，单位秒，默认值为 30

            operator:
                系统操作人，默认值为 system

            service_id:
                所属服务实例 ID（可选）

        异常：
            ValueError: 参数配置无效
        """
        if not environment:
            raise ValueError(
                "environment 不能为空",
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds 必须大于 0",
            )

        if heartbeat_interval_seconds <= 0:
            raise ValueError(
                "heartbeat_interval_seconds "
                "必须大于 0",
            )

        if not operator:
            raise ValueError(
                "operator 不能为空",
            )

        self.manager = manager
        self.service_id = service_id
        self._logger = logger.bind(
            worker_id=manager.worker_id,
            pid=os.getpid(),
        )
        if service_id is not None:
            self._logger = self._logger.bind(
                service_id=service_id,
            )

        self.environment = environment

        self.interval_seconds = float(
            interval_seconds,
        )

        self.heartbeat_interval_seconds = float(
            heartbeat_interval_seconds,
        )

        self.operator = operator

        self._applied_generations: dict[
            str,
            int,
        ] = {}

        self._task: asyncio.Task[None] | None = None

        self._stop_event = asyncio.Event()

        self._reconcile_lock = asyncio.Lock()

        self._last_heartbeat_at = 0.0
        self._cleanup_not_before = time.monotonic() + 3 * self.heartbeat_interval_seconds
        self._cycle_failure_started_at: float | None = None
        self._cycle_failure_count = 0
        self._cycle_failure_log_at = 0.0
        self._heartbeat_failure_started_at: float | None = None
        self._heartbeat_failure_count = 0
        self._last_heartbeat_failure_log_at = 0.0
        self._last_heartbeat_error: tuple[type[BaseException], str] | None = None

    @property
    def worker_id(
            self,
    ) -> str:
        """获取当前 Worker ID."""
        return self.manager.worker_id

    @property
    def is_running(
            self,
    ) -> bool:
        """判断协调器是否正在运行."""
        return (
            self._task is not None
            and not self._task.done()
        )

    async def start(
            self,
    ) -> None:
        """启动后台协调循环.

        重复调用保持幂等。
        """
        if self.is_running:
            return

        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run_loop(),
            name=(
                "runtime-reconciler-"
                f"{self.worker_id}"
            ),
        )

        self._logger.debug(
            "协调器启动成功",
            worker_id=self.worker_id,
            environment=self.environment,
            interval_seconds=(
                self.interval_seconds
            ),
            heartbeat_interval_seconds=(
                self.heartbeat_interval_seconds
            ),
        )

    async def stop(
            self,
    ) -> None:
        """停止后台协调循环.

        说明：
            stop 只停止协调循环，
            不主动卸载当前 Worker 中已加载模型。

            Worker 关闭时的模型卸载，
            由运行服务生命周期负责。
        """
        task = self._task

        if task is None:
            return

        self._stop_event.set()

        try:
            await task

        finally:
            self._task = None

        self._logger.info(
            "协调器已停止",
            worker_id=self.worker_id,
            environment=self.environment,
        )

    async def reconcile_once(
            self,
    ) -> ReconcileResult:
        """执行一次状态协调.

        返回：
            单次协调结果

        说明：
            只协调当前 environment
            对应的 Control。

            单个 Deployment 协调失败，
            不影响其他 Deployment 的状态协调。
        """
        async with self._reconcile_lock:
            controls = await self._load_controls()

            result = ReconcileResult(
                checked=len(controls),
            )

            for control in controls:
                try:
                    with structlog.contextvars.bound_contextvars(
                            generation=control.generation,
                            environment=self.environment,
                            **(
                                {"service_id": self.service_id}
                                if self.service_id
                                else {}
                            ),
                    ):
                        action = await self._reconcile_control(
                            control,
                        )

                    result.record(
                        action,
                    )

                except asyncio.CancelledError:
                    raise

                except (
                        BackendError,
                        DeploymentNotFoundError,
                        InvalidDeploymentStateError,
                        RuntimeRouteError,
                        VersionNotFoundError,
                        SQLAlchemyError,
                        RuntimeError,
                        ValueError,
                ) as exc:
                    result.failed += 1

                    self._logger.exception(
                        "状态协调失败",
                        worker_id=self.worker_id,
                        environment=self.environment,
                        deployment_id=(
                            control.deployment_id
                        ),
                        control_environment=(
                            control.environment
                        ),
                        desired_status=(
                            str(control.desired_status)
                        ),
                        generation=(
                            control.generation
                        ),
                        error=str(exc),
                    )

            await self._heartbeat_if_due(
                controls,
            )

            if (
                    result.loaded
                    or result.unloaded
                    or result.reloaded
                    or result.failed
            ):
                log_result = (
                    self._logger.warning
                    if result.failed
                    else self._logger.debug
                )
                log_result(
                    "状态协调完成",
                    worker_id=self.worker_id,
                    environment=self.environment,
                    **result.to_dict(),
                )

            return result

    def get_applied_generation(
            self,
            deployment_id: str,
    ) -> int | None:
        """获取本 Worker 已应用的控制版本.

        参数：
            deployment_id: 部署 ID

        返回：
            generation，不存在时返回 None
        """
        return self._applied_generations.get(
            deployment_id,
        )

    def get_applied_generations(
            self,
    ) -> dict[str, int]:
        """获取本 Worker 全部已应用版本.

        返回：
            deployment_id 到 generation 的映射副本
        """
        return dict(
            self._applied_generations,
        )

    async def _run_loop(
            self,
    ) -> None:
        """运行后台协调循环."""
        while not self._stop_event.is_set():
            delay = self.interval_seconds
            try:
                await self.reconcile_once()
                if self._cycle_failure_started_at is not None:
                    now = time.monotonic()
                    self._cleanup_not_before = now + 3 * self.heartbeat_interval_seconds
                    self._logger.info(
                        "状态协调已恢复",
                        failure_count=self._cycle_failure_count,
                        duration_seconds=round(now - self._cycle_failure_started_at, 3),
                        environment=self.environment,
                    )
                    self._cycle_failure_started_at = None
                    self._cycle_failure_count = 0

            except asyncio.CancelledError:
                raise

            except (
                    OSError,
                    SQLAlchemyError,
                    RuntimeError,
                    ValueError,
            ) as exc:
                now = time.monotonic()
                first_failure = (
                    self._cycle_failure_started_at is None
                )

                if first_failure:
                    self._cycle_failure_started_at = now

                self._cycle_failure_count += 1
                self._cleanup_not_before = (
                    now
                    + 3 * self.heartbeat_interval_seconds
                )

                if (
                        first_failure
                        or now - self._cycle_failure_log_at >= 60
                ):
                    log = (
                        self._logger.exception
                        if first_failure
                        else self._logger.error
                    )

                    log(
                        (
                            "状态协调周期执行失败"
                            if first_failure
                            else "状态协调持续失败"
                        ),
                        worker_id=self.worker_id,
                        environment=self.environment,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        failure_count=self._cycle_failure_count,
                    )
                    self._cycle_failure_log_at = now

                delay = max(
                    self.interval_seconds,
                    min(
                        30.0,
                        self.interval_seconds
                        * 2 ** min(self._cycle_failure_count, 10),
                    ),
                )

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=delay,
                )

            except asyncio.TimeoutError:
                continue

    async def _load_controls(
            self,
    ) -> list[ControlSnapshot]:
        """读取当前环境的运行控制状态.

        返回：
            当前 environment 对应的控制状态快照列表
        """
        async with UnitOfWork() as uow:
            repo = ControlRepository(
                uow.session,
            )

            controls = await repo.list_controls(
                environment=Environment(
                    self.environment,
                ),
            )

            snapshots = [
                ControlSnapshot(
                    deployment_id=str(
                        control.deployment_id,
                    ),
                    environment=str(
                        control.environment,
                    ),
                    desired_status=(
                        self._parse_status(
                            control.desired_status,
                        )
                    ),
                    generation=int(
                        control.generation,
                    ),
                    updated_by=(
                        str(control.updated_by)
                        if control.updated_by
                        else None
                    ),
                )
                for control in controls
            ]

        return snapshots

    async def _reconcile_control(
            self,
            control: ControlSnapshot,
    ) -> str:
        """协调单个 Deployment.

        参数：
            control: 控制状态快照

        返回：
            loaded
            unloaded
            reloaded
            unchanged

        异常：
            RuntimeError:
                Control 环境与当前 Reconciler 环境不一致
        """
        if control.environment != self.environment:
            raise RuntimeError(
                "运行控制环境与当前协调器环境不一致: "
                f"deployment_id={control.deployment_id}, "
                f"control_environment={control.environment}, "
                f"reconciler_environment={self.environment}",
            )

        deployment_id = control.deployment_id

        generation = control.generation

        desired_status = (
            control.desired_status
        )

        operator = (
            control.updated_by
            or self.operator
        )

        local_loaded = (
            deployment_id
            in self.manager.registry
        )

        applied_generation = (
            self._applied_generations.get(
                deployment_id,
            )
        )

        if (
                desired_status
                == RuntimeControlStatus.LOADED
        ):
            if not local_loaded:
                await self.manager.load(
                    deployment_id=deployment_id,
                    operator=operator,
                )

                await self._record_applied_generation(
                    deployment_id=deployment_id,
                    generation=generation,
                )

                self._applied_generations[
                    deployment_id
                ] = generation

                self._logger.debug(
                    "模型加载协调完成",
                    worker_id=self.worker_id,
                    environment=self.environment,
                    deployment_id=deployment_id,
                    generation=generation,
                )

                return "loaded"

            if applied_generation is None:
                await self._record_applied_generation(
                    deployment_id=deployment_id,
                    generation=generation,
                )

                self._applied_generations[
                    deployment_id
                ] = generation

                self._logger.debug(
                    "初始化本地控制版本",
                    worker_id=self.worker_id,
                    environment=self.environment,
                    deployment_id=deployment_id,
                    generation=generation,
                )

                return "unchanged"

            if applied_generation != generation:
                await self.manager.reload(
                    deployment_id=deployment_id,
                    operator=operator,
                )

                await self._record_applied_generation(
                    deployment_id=deployment_id,
                    generation=generation,
                )

                self._applied_generations[
                    deployment_id
                ] = generation

                self._logger.debug(
                    "模型重载协调完成",
                    worker_id=self.worker_id,
                    environment=self.environment,
                    deployment_id=deployment_id,
                    previous_generation=(
                        applied_generation
                    ),
                    generation=generation,
                )

                return "reloaded"

            return "unchanged"

        if (
                desired_status
                == RuntimeControlStatus.UNLOADED
        ):
            if local_loaded:
                await self.manager.unload(
                    deployment_id=deployment_id,
                    operator=operator,
                )

                await self._record_applied_generation(
                    deployment_id=deployment_id,
                    generation=generation,
                )

                self._applied_generations[
                    deployment_id
                ] = generation

                self._logger.debug(
                    "模型卸载协调完成",
                    worker_id=self.worker_id,
                    environment=self.environment,
                    deployment_id=deployment_id,
                    generation=generation,
                )

                return "unloaded"

            await self._record_applied_generation(
                deployment_id=deployment_id,
                generation=generation,
            )

            self._applied_generations[
                deployment_id
            ] = generation

            return "unchanged"

        raise ValueError(
            "不支持的运行控制状态: "
            f"{desired_status}",
        )

    async def _record_applied_generation(
            self,
            *,
            deployment_id: str,
            generation: int,
    ) -> None:
        """持久化当前 Worker 已应用的控制版本号."""
        async with UnitOfWork() as uow:
            await RuntimeRepository(
                uow.session,
            ).set_applied_generation(
                deployment_id=deployment_id,
                worker_id=self.worker_id,
                generation=generation,
            )

    async def _heartbeat_if_due(
            self,
            controls: list[ControlSnapshot],
    ) -> None:
        """按间隔更新已加载模型运行心跳.

        参数：
            controls:
                当前环境的运行控制快照列表
        """
        now = time.monotonic()

        elapsed = (
            now
            - self._last_heartbeat_at
        )

        if (
                elapsed
                < self.heartbeat_interval_seconds
        ):
            return

        try:
            await self._heartbeat_loaded_runtimes(
                controls,
            )

            if (
                    self._heartbeat_failure_started_at is not None
                    or self._cycle_failure_started_at is not None
            ):
                self._cleanup_not_before = (
                    now
                    + 3 * self.heartbeat_interval_seconds
                )

            if now >= self._cleanup_not_before:
                await self._mark_stale_runtimes_failed()

            self._last_heartbeat_at = now

            if (
                    self._heartbeat_failure_started_at is not None
            ):
                self._logger.info(
                    "心跳更新已恢复",
                    environment=self.environment,
                    failure_count=self._heartbeat_failure_count,
                    duration_seconds=round(
                        time.monotonic()
                        - self._heartbeat_failure_started_at,
                        3,
                    ),
                )

                self._heartbeat_failure_started_at = None
                self._heartbeat_failure_count = 0
                self._last_heartbeat_failure_log_at = 0.0
                self._last_heartbeat_error = None

        except asyncio.CancelledError:
            raise

        except (
                OSError,
                SQLAlchemyError,
                RuntimeError,
        ) as exc:
            self._record_heartbeat_failure(
                exc,
            )

    def _record_heartbeat_failure(
            self,
            error: Exception,
    ) -> None:
        """记录心跳更新失败."""
        now = time.monotonic()

        self._cleanup_not_before = (
            now
            + 3 * self.heartbeat_interval_seconds
        )
        signature = (
            type(error),
            str(error),
        )

        if self._heartbeat_failure_started_at is None:
            self._heartbeat_failure_started_at = now

        self._heartbeat_failure_count += 1

        fields = {
            "environment": self.environment,
            "error": str(error),
            "error_type": type(error).__name__,
            "failure_count": self._heartbeat_failure_count,
            "duration_seconds": round(
                now - self._heartbeat_failure_started_at,
                3,
            ),
        }

        if signature != self._last_heartbeat_error:
            # 首次失败或错误变化时保留异常堆栈。
            self._logger.exception(
                "心跳更新失败",
                **fields,
            )

        elif (
                now - self._last_heartbeat_failure_log_at
                >= _HEARTBEAT_FAILURE_LOG_INTERVAL_SECONDS
        ):
            # 同类持续故障每分钟汇总一次。
            self._logger.error(
                "心跳更新持续失败",
                **fields,
            )

        else:
            return

        self._last_heartbeat_error = signature
        self._last_heartbeat_failure_log_at = now

    async def _mark_stale_runtimes_failed(
            self,
    ) -> None:
        """将当前环境中已失联的其他 Worker 实例收敛为失败."""
        checked_at = datetime.now(
            timezone.utc,
        )
        presence = RuntimePresence.current(
            current_time=checked_at,
        )
        stale_details: list[dict] = []

        async with UnitOfWork() as uow:
            runtime_ids = await RuntimeRepository(
                uow.session,
            ).mark_stale_runtimes_failed(
                environment=self.environment,
                stale_before=presence.stale_at,
                stale_details=stale_details,
                exclude_worker_id=self.worker_id,
            )

        if runtime_ids:
            self._logger.try_unbind("worker_id").warning(
                "失联运行实例已标记为失败",
                observer_worker_id=self.worker_id,
                environment=self.environment,
                checked_at=checked_at.isoformat(),
                stale_before=presence.stale_at.isoformat(),
                timeout_seconds=(checked_at - presence.stale_at).total_seconds(),
                runtime_ids=runtime_ids[:10],
                stale_runtimes=stale_details,
                count=len(runtime_ids),
                omitted_count=max(
                    0,
                    len(runtime_ids) - 10,
                ),
            )

    async def _heartbeat_loaded_runtimes(
            self,
            controls: list[ControlSnapshot],
    ) -> None:
        """更新当前 Worker 已加载模型心跳.

        参数：
            controls:
                当前环境的运行控制快照列表
        """
        deployment_ids = [
            control.deployment_id
            for control in controls
            if (
                    control.desired_status
                    == RuntimeControlStatus.LOADED
                    and control.deployment_id
                    in self.manager.registry
            )
        ]

        if not deployment_ids:
            return

        async with UnitOfWork() as uow:
            repo = RuntimeRepository(
                uow.session,
            )

            for deployment_id in deployment_ids:
                runtime = (
                    await repo.get_deployment_runtime(
                        deployment_id=deployment_id,
                        worker_id=self.worker_id,
                    )
                )

                if runtime is None:
                    continue

                if runtime.status != "running":
                    continue

                repo.heartbeat(
                    runtime,
                )

    @staticmethod
    def _parse_status(
            value: RuntimeControlStatus | str,
    ) -> RuntimeControlStatus:
        """解析运行控制状态.

        参数：
            value:
                字符串或 RuntimeControlStatus

        返回：
            RuntimeControlStatus

        异常：
            ValueError: 状态值不合法
        """
        if isinstance(
                value,
                RuntimeControlStatus,
        ):
            return value

        return RuntimeControlStatus(
            value,
        )
