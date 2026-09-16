"""运行时预测处理

负责业务结果回流、单条与批量预测、记录持久化、
影子预测调度以及 Worker 本地服务缓存。

核心功能：
  - PredictionMixin: 提供预测相关的 BentoML 接口与处理流程

使用示例：
  from datamind.runtime.server.prediction import PredictionMixin

  class RuntimeService(PredictionMixin):
      pass
"""

import asyncio
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from collections.abc import Awaitable, Callable
from typing import Any

import bentoml
import structlog
from structlog.typing import FilteringBoundLogger

from datamind.audit import AuditRecorder
from datamind.audit.errors import AuditError
from datamind.config import get_settings
from datamind.context import get_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DecisionRepository,
    DeploymentRepository,
    ExecutionRepository,
    MetadataRepository,
    RequestRepository,
)
from datamind.models.enums import (
    DecisionStrategy,
    DeploymentStatus,
    ExecutionStatus,
    ExecutionType,
)
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.executor import (
    ExecutionPlan,
    ExecutionResult,
    PredictionExecutor,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.reconciler import RuntimeReconciler
from datamind.runtime.responses import build_prediction_response
from datamind.runtime.routing import (
    RouteResult,
    RoutingPlan,
    RuntimeRouter,
)
from datamind.runtime.server.cache import ServiceCacheEntry
from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.server.schemas import (
    BatchPredictRequest,
    OutcomeFeedbackRequest,
    PredictRequest,
    PredictionInstance,
)
from datamind.runtime.server.timeout import (
    RequestTimeoutError,
    REQUEST_TIMEOUT_GRACE_SECONDS,
    request_budget,
)
from datamind.runtime.shadow import ShadowDispatcher, ShadowTask
from datamind.runtime.serving.base import BaseRuntimeService
from datamind.runtime.serving.factory import RuntimeServiceFactory
from datamind.services import OutcomeService
from datamind.utils.datetime import format_iso_utc
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)
service_config = get_settings().service
runtime_config = get_settings().runtime


class PredictionMixin:
    """运行时预测处理能力"""

    executor: PredictionExecutor
    manager: RuntimeManager
    reconciler: RuntimeReconciler
    router: RuntimeRouter
    shadow_dispatcher: ShadowDispatcher
    _audit_recorder: AuditRecorder
    _logger: FilteringBoundLogger
    _service_cache: dict[str, ServiceCacheEntry]
    _service_lock: asyncio.Lock
    _execute_secured: Callable[..., Awaitable[dict[str, Any]]]

    @bentoml.api(
        route="/feedback/outcomes",
    )
    async def submit_outcome(
            self,
            request: OutcomeFeedbackRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的延迟业务结果"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="outcome.write",
            request_id=request_id,
            handler=lambda _identity: self._submit_outcome(
                request=request,
                request_id=request_id,
            ),
            audit_action="outcome.submit",
            target_type="outcome",
            target_id=request.outcome_id,
        )

    @staticmethod
    async def _submit_outcome(
            *,
            request: OutcomeFeedbackRequest,
            request_id: str,
    ) -> dict[str, Any]:
        """提交延迟业务结果"""
        result = await OutcomeService().submit(
            outcome_id=request.outcome_id,
            subject_key=request.subject_key,
            decision_id=request.decision_id,
            request_id=request.request_id,
            subject_type=request.subject_type,
            approved=request.approved,
            converted=request.converted,
            defaulted=request.defaulted,
            overdue_days=request.overdue_days,
            amount=request.amount,
            label=request.label,
            context=request.context,
            outcome_time=request.outcome_time,
        )
        outcome = result["outcome"]

        for field in (
                "outcome_time",
                "created_at",
                "updated_at",
        ):
            outcome[field] = format_iso_utc(
                outcome[field]
            )

        return {
            "success": True,
            "request_id": request_id,
            **result,
        }

    @bentoml.api(
        route="/predict",
    )
    async def predict(
            self,
            request: PredictRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """执行已认证的单条模型预测"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="prediction.invoke",
            request_id=request_id,
            handler=lambda _identity: self._predict(
                request=request,
                request_id=request_id,
            ),
        )

    async def _predict(
            self,
            *,
            request: PredictRequest,
            request_id: str,
    ) -> dict[str, Any]:
        """执行单条模型预测

        处理流程：
          - 创建请求记录
          - 为请求解析运行时路由
          - 执行模型预测
          - 更新请求状态并创建决策记录
          - 返回预测结果和请求 ID

        参数：
            request: 单条预测请求
            request_id: 请求 ID

        返回：
            单条预测结果
        """
        started_at = time.perf_counter()

        request_record_created = False
        model_id: str | None = None

        try:
            async with request_budget(service_config.timeout) as budget:
                budget.enter_stage("request_record")
                payload = self._build_request_payload(
                    request
                )

                await self._create_request_record(
                    request_id=request_id,
                    model_id=None,
                    model_name=request.model_name,
                    payload=payload,
                )

                request_record_created = True

                budget.enter_stage("model")
                resolved_model_id = await self._resolve_model_id(
                    model_name=request.model_name,
                )
                model_id = resolved_model_id

                if not request.features:
                    raise ValueError(
                        "features 不能为空"
                    )

                budget.enter_stage("routing")
                routing_plan = await self.router.resolve(
                    model_id=resolved_model_id,
                    environment=(
                        service_config.environment
                    ),
                    subject_key=request.subject_key,
                    subject_type=request.subject_type,
                    payload=request.features,
                    deployment_id=request.deployment_id,
                    include_shadows=(
                        runtime_config.shadow_enabled
                    ),
                )
                plan = ExecutionPlan(
                    route=routing_plan.primary,
                    execution_type=ExecutionType.PRIMARY,
                )
                budget.enter_stage("prediction")
                result = await self.executor.execute(
                    plan=plan,
                    features=request.features,
                )
                prediction = result.prediction

                latency_ms = (
                                     time.perf_counter() - started_at
                             ) * 1000

                decision_id = generate_random_id(
                    prefix="dcs"
                )

                response = build_prediction_response(
                    prediction,
                    request_id=request_id,
                )

                budget.enter_stage("persistence")
                shadow_tasks = await self._record_prediction_success(
                    request_id=request_id,
                    decision_id=decision_id,
                    result=result,
                    shadow_routes=routing_plan.shadows,
                    features=request.features,
                    response=response,
                    latency_ms=latency_ms,
                )

                budget.enter_stage("shadow_dispatch")
                await self._submit_shadow_predictions(
                    shadow_tasks
                )

                return response

        except (
                RuntimeRouteError,
                RuntimeError,
                TypeError,
                ValueError,
        ) as exc:
            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000
            response = build_prediction_response(
                self._build_error_response(request_id=request_id, error=exc),
                request_id=request_id,
            )

            await self._mark_prediction_failed(
                request_id=request_id,
                model_id=model_id,
                request_record_created=(
                    request_record_created or isinstance(exc, RequestTimeoutError)
                ),
                error=str(exc),
                response=response,
                latency_ms=latency_ms,
            )

            self._logger.warning(
                "预测请求处理失败",
                request_id=request_id,
                model_name=request.model_name,
                model_id=model_id,
                deployment_id=request.deployment_id,
                subject_key=request.subject_key,
                subject_type=request.subject_type,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                **(
                    {"timeout_seconds": exc.seconds, "timeout_stage": exc.stage}
                    if isinstance(exc, RequestTimeoutError)
                    else {}
                ),
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return response

        except Exception as exc:
            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000
            response = build_prediction_response(
                self._build_error_response(request_id=request_id, error=exc),
                request_id=request_id,
            )

            await self._mark_prediction_failed(
                request_id=request_id,
                model_id=model_id,
                request_record_created=request_record_created,
                error=str(exc),
                response=response,
                latency_ms=latency_ms,
            )

            self._logger.exception(
                "预测请求处理异常",
                request_id=request_id,
                model_name=request.model_name,
                model_id=model_id,
                deployment_id=request.deployment_id,
                subject_key=request.subject_key,
                subject_type=request.subject_type,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return response

    @bentoml.api(
        route="/predict/batch",
    )
    async def predict_batch(
            self,
            request: BatchPredictRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """执行已认证的批量模型预测"""
        batch_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="prediction.invoke",
            request_id=batch_id,
            handler=lambda _identity: self._predict_batch(
                request=request,
                batch_id=batch_id,
            ),
        )

    async def _predict_batch(
            self,
            *,
            request: BatchPredictRequest,
            batch_id: str,
    ) -> dict[str, Any]:
        """执行批量模型预测

        处理流程：
          - 创建每条请求的记录
          - 为每条请求解析运行时路由
          - 按主部署分组执行模型预测
          - 按原始顺序整理预测结果
          - 更新请求状态并创建决策记录
          - 返回预测结果和请求 ID

        参数：
            request: 批量预测请求
            batch_id: 批次请求 ID

        返回：
            批量预测结果
        """
        request_ids: list[str] = []
        records_created = False
        started_at = time.perf_counter()

        try:
            async with request_budget(service_config.timeout) as budget:
                request_ids = [
                    generate_random_id(
                        prefix="req"
                    )
                    for _ in request.instances
                ]
                decision_ids = [
                    generate_random_id(
                        prefix="dcs"
                    )
                    for _ in request.instances
                ]

                budget.enter_stage("request_record")
                await self._create_batch_request_records(
                    batch_id=batch_id,
                    request_ids=request_ids,
                    model_id=None,
                    model_name=request.model_name,
                    deployment_id=request.deployment_id,
                    instances=request.instances,
                )
                records_created = True

                budget.enter_stage("model")
                model_id = await self._resolve_model_id(
                    model_name=request.model_name,
                )

                budget.enter_stage("routing")
                routing_plans = []

                for instance in request.instances:
                    routing_plans.append(
                        await self.router.resolve(
                            model_id=model_id,
                            environment=(
                                service_config.environment
                            ),
                            subject_key=instance.subject_key,
                            subject_type=instance.subject_type,
                            payload=instance.features,
                            deployment_id=request.deployment_id,
                            include_shadows=(
                                runtime_config.shadow_enabled
                            ),
                        )
                    )

                budget.enter_stage("prediction")
                results, task_type = await self._execute_routed_batch(
                    routing_plans=routing_plans,
                    instances=request.instances,
                )
                predictions = [
                    result.prediction
                    for result in results
                ]

                responses = [
                    build_prediction_response(prediction, request_id=request_id)
                    for request_id, prediction in zip(request_ids, predictions, strict=True)
                ]

                latency_ms = (
                                     time.perf_counter()
                                     - started_at
                             ) * 1000

                budget.enter_stage("persistence")
                shadow_tasks = await self._record_batch_success(
                    batch_id=batch_id,
                    request_ids=request_ids,
                    decision_ids=decision_ids,
                    results=results,
                    routing_plans=routing_plans,
                    instances=request.instances,
                    responses=responses,
                    latency_ms=latency_ms,
                )

                budget.enter_stage("shadow_dispatch")
                await self._submit_shadow_predictions(
                    shadow_tasks
                )

                return {
                    "success": True,
                    "task_type": task_type,
                    "count": len(responses),
                    "predictions": responses,
                    "request_id": batch_id,
                }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                TypeError,
                ValueError,
        ) as exc:
            response = build_prediction_response(
                self._build_error_response(request_id=batch_id, error=exc),
                request_id=batch_id,
            )

            await self._mark_batch_failed(
                request_ids=request_ids,
                records_created=(
                    records_created or isinstance(exc, RequestTimeoutError)
                ),
                error=str(exc),
                response=response,
                latency_ms=(
                                   time.perf_counter()
                                   - started_at
                           ) * 1000,
            )

            self._logger.warning(
                "批量预测请求处理失败",
                request_id=batch_id,
                model_name=request.model_name,
                deployment_id=request.deployment_id,
                batch_size=len(request.instances),
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                **(
                    {"timeout_seconds": exc.seconds, "timeout_stage": exc.stage}
                    if isinstance(exc, RequestTimeoutError)
                    else {}
                ),
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return response

        except Exception as exc:
            response = build_prediction_response(
                self._build_error_response(request_id=batch_id, error=exc),
                request_id=batch_id,
            )

            await self._mark_batch_failed(
                request_ids=request_ids,
                records_created=records_created,
                error=str(exc),
                response=response,
                latency_ms=(
                                   time.perf_counter()
                                   - started_at
                           ) * 1000,
            )

            self._logger.exception(
                "批量预测请求处理异常",
                request_id=batch_id,
                model_name=request.model_name,
                deployment_id=request.deployment_id,
                batch_size=len(request.instances),
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return response

    async def _execute_routed_batch(
            self,
            *,
            routing_plans: list[RoutingPlan],
            instances: list[PredictionInstance],
    ) -> tuple[list[ExecutionResult], str | None]:
        """按主部署分组执行批量预测并恢复请求顺序。"""
        indices_by_deployment: dict[str, list[int]] = {}

        for index, routing_plan in enumerate(routing_plans):
            indices_by_deployment.setdefault(
                routing_plan.primary.deployment_id,
                [],
            ).append(index)

        results_by_index: dict[int, ExecutionResult] = {}
        task_type: str | None = None

        for deployment_id, indices in indices_by_deployment.items():
            service = await self._get_service(
                deployment_id
            )
            features_list = [
                instances[index].features
                for index in indices
            ]
            started_at = time.perf_counter()
            batch_result = await asyncio.to_thread(
                service.predict_batch,
                features_list,
            )
            latency_ms = (
                                 time.perf_counter()
                                 - started_at
                         ) * 1000
            predictions = batch_result.get(
                "predictions"
            )

            if (
                    not isinstance(predictions, list)
                    or len(predictions) != len(indices)
            ):
                raise RuntimeError(
                    "批量预测结果数量与请求数量不一致"
                )

            resolved_task_type = batch_result.get(
                "task_type",
                batch_result.get("service_type"),
            )

            if resolved_task_type is not None:
                current_task_type = str(resolved_task_type)

                if (
                        task_type is not None
                        and task_type != current_task_type
                ):
                    raise RuntimeError(
                        "同一模型的批量预测返回了不同任务类型"
                    )

                task_type = current_task_type

            for index, prediction in zip(
                    indices,
                    predictions,
                    strict=True,
            ):
                results_by_index[index] = ExecutionResult(
                    plan=ExecutionPlan(
                        route=routing_plans[index].primary,
                        execution_type=ExecutionType.PRIMARY,
                    ),
                    prediction=prediction,
                    latency_ms=latency_ms,
                )

        return (
            [
                results_by_index[index]
                for index in range(len(instances))
            ],
            task_type,
        )

    @staticmethod
    async def _create_batch_request_records(
            *,
            batch_id: str,
            request_ids: list[str],
            model_id: str | None,
            model_name: str,
            deployment_id: str | None,
            instances: list[PredictionInstance],
    ) -> None:
        """在同一事务中创建批量请求记录"""
        request_context = get_context()

        async with UnitOfWork() as uow:
            repository = RequestRepository(
                uow.session
            )

            for index, (request_id, instance) in enumerate(
                    zip(
                        request_ids,
                        instances,
                    )
            ):
                repository.create_request(
                    request_id=request_id,
                    model_id=model_id,
                    model_name=model_name,
                    payload={
                        "batch_id": batch_id,
                        "batch_index": index,
                        "model_name": model_name,
                        "deployment_id": deployment_id,
                        "subject_key": instance.subject_key,
                        "subject_type": instance.subject_type,
                        "features": instance.features,
                    },
                    source="http",
                    user=request_context.get(
                        "user"
                    ),
                    ip=request_context.get(
                        "ip"
                    ),
                )

    async def _record_batch_success(
            self,
            *,
            batch_id: str,
            request_ids: list[str],
            decision_ids: list[str],
            results: list[ExecutionResult],
            routing_plans: list[RoutingPlan],
            instances: list[PredictionInstance],
            responses: list[dict[str, Any]],
            latency_ms: float,
    ) -> tuple[ShadowTask, ...]:
        """在同一事务中记录批量请求和决策结果"""
        shadow_tasks: list[ShadowTask] = []

        async with UnitOfWork() as uow:
            request_repo = RequestRepository(
                uow.session
            )
            decision_repo = DecisionRepository(
                uow.session
            )
            execution_repo = ExecutionRepository(
                uow.session
            )
            finished_at = datetime.now(
                timezone.utc
            )

            for index, (
                    request_id,
                    decision_id,
                    result,
                    routing_plan,
                    instance,
                    response,
            ) in enumerate(
                zip(
                    request_ids,
                    decision_ids,
                    results,
                    routing_plans,
                    instances,
                    responses,
                    strict=True,
                )
            ):
                route = result.route
                prediction = result.prediction
                started_at = finished_at - timedelta(
                    milliseconds=result.latency_ms
                )
                request_record = await request_repo.get_request(
                    request_id
                )

                if request_record is None:
                    raise RuntimeError(
                        f"批量请求记录不存在: {request_id}"
                    )

                request_repo.mark_success(
                    request_record,
                    model_id=route.model_id,
                    response=response,
                    latency_ms=latency_ms,
                )
                decision_repo.create_decision(
                    decision_id=decision_id,
                    request_id=request_id,
                    model_id=route.model_id,
                    version_id=route.version_id,
                    source=DecisionStrategy(
                        route.source
                    ),
                    deployment_id=route.deployment_id,
                    experiment_id=route.experiment_id,
                    variant_id=route.variant_id,
                    assignment_id=route.assignment_id,
                    subject_key=route.subject_key,
                    subject_type=route.subject_type,
                    strategy=route.strategy,
                    bucket=route.bucket,
                    group=route.group,
                    weight=route.weight,
                    decision=self._optional_string(
                        prediction.get("decision")
                    ),
                    context=self._build_decision_context(
                        route,
                        batch_id=batch_id,
                        batch_index=index,
                    ),
                )
                execution_repo.create_execution(
                    execution_id=generate_random_id(
                        prefix="exe"
                    ),
                    decision_id=decision_id,
                    execution_type=(
                        result.plan.execution_type
                    ),
                    status=ExecutionStatus.SUCCESS,
                    model_id=route.model_id,
                    version_id=route.version_id,
                    deployment_id=route.deployment_id,
                    routing_id=route.routing_id,
                    prediction=(
                        self._build_prediction_payload(
                            prediction
                        )
                    ),
                    probability=self._optional_float(
                        prediction.get(
                            "probability"
                        )
                    ),
                    score=self._optional_float(
                        prediction.get(
                            "score"
                        )
                    ),
                    latency_ms=result.latency_ms,
                    context=self._build_decision_context(
                        route,
                        batch_id=batch_id,
                        batch_index=index,
                    ),
                    started_at=started_at,
                    finished_at=finished_at,
                )

                for shadow_route in routing_plan.shadows:
                    execution_id = generate_random_id(
                        prefix="exe"
                    )
                    shadow_plan = ExecutionPlan(
                        route=shadow_route,
                        execution_type=ExecutionType.SHADOW,
                        timeout=runtime_config.shadow_timeout,
                    )
                    execution_repo.create_execution(
                        execution_id=execution_id,
                        decision_id=decision_id,
                        execution_type=(
                            shadow_plan.execution_type
                        ),
                        status=ExecutionStatus.QUEUED,
                        model_id=shadow_route.model_id,
                        version_id=shadow_route.version_id,
                        deployment_id=(
                            shadow_route.deployment_id
                        ),
                        routing_id=shadow_route.routing_id,
                        context=self._build_decision_context(
                            shadow_route,
                            batch_id=batch_id,
                            batch_index=index,
                        ),
                    )
                    shadow_tasks.append(
                        ShadowTask(
                            execution_id=execution_id,
                            request_id=request_id,
                            decision_id=decision_id,
                            plan=shadow_plan,
                            features=deepcopy(instance.features),
                        )
                    )

        return tuple(shadow_tasks)

    @staticmethod
    async def _mark_batch_failed(
            *,
            request_ids: list[str],
            records_created: bool,
            error: str,
            response: dict[str, Any] | None = None,
            latency_ms: float,
    ) -> None:
        """标记已经创建的批量请求为失败"""
        if not records_created:
            return

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_GRACE_SECONDS):
                async with UnitOfWork() as uow:
                    repository = RequestRepository(
                        uow.session
                    )

                    for request_id in request_ids:
                        request_record = await repository.get_request(
                            request_id
                        )

                        if (
                                request_record is not None
                                and request_record.status != "success"
                        ):
                            repository.mark_failed(
                                request_record,
                                error=error,
                                response=(
                                    build_prediction_response(response, request_id=request_id)
                                    if response is not None else None
                                ),
                                latency_ms=latency_ms,
                            )

        except Exception as exc:
            logger.exception(
                "记录批量失败请求状态失败",
                request_ids=request_ids,
                error=str(exc),
            )

    def _build_error_response(
            self,
            *,
            request_id: str,
            error: Exception,
    ) -> dict[str, Any]:
        """构造接口错误响应

        参数：
            request_id: 请求追踪 ID
            error: 异常对象

        返回：
            错误响应字典
        """
        return {
            "success": False,
            "request_id": request_id,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "environment": service_config.environment,
            "worker_id": self.manager.worker_id,
        }

    async def _mark_prediction_failed(
            self,
            *,
            request_id: str,
            model_id: str | None,
            request_record_created: bool,
            error: str,
            response: dict[str, Any],
            latency_ms: float,
    ) -> None:
        """标记预测请求失败

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            request_record_created: 请求记录是否已创建
            error: 错误信息
            response: 返回给调用方的错误响应
            latency_ms: 处理耗时
        """
        if not request_record_created:
            return

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_GRACE_SECONDS):
                await self._mark_request_failed(
                    request_id=request_id,
                    model_id=model_id,
                    error=error,
                    response=response,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            self._logger.exception(
                "记录失败请求状态失败",
                request_id=request_id,
                model_id=model_id,
                error=str(exc),
            )

    @staticmethod
    async def _resolve_model_id(
            *,
            model_name: str,
    ) -> str:
        """将公开模型名称解析为内部模型 ID

        参数：
            model_name: 全局唯一模型名称

        返回：
            内部模型 ID

        异常：
            ValueError: 模型不存在
        """
        async with UnitOfWork() as uow:
            repo = MetadataRepository(
                uow.session
            )
            model = await repo.get_model(
                name=model_name,
            )

        if model is None:
            raise ValueError(
                f"模型不存在: {model_name}"
            )

        return str(model.model_id)

    @staticmethod
    def _build_request_payload(
            request: PredictRequest,
    ) -> dict[str, Any]:
        """构造请求负载

        参数：
            request: 单条预测请求

        返回：
            请求负载字典
        """
        return {
            "model_name": request.model_name,
            "environment": service_config.environment,
            "deployment_id": request.deployment_id,
            "subject_key": request.subject_key,
            "subject_type": request.subject_type,
            "features": request.features,
        }

    @staticmethod
    async def _create_request_record(
            *,
            request_id: str,
            model_id: str | None,
            model_name: str | None,
            payload: dict[str, Any],
    ) -> None:
        """创建原始请求记录

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            model_name: 模型名称
            payload: 请求负载
        """
        request_context = get_context()

        async with UnitOfWork() as uow:
            repo = RequestRepository(
                uow.session
            )

            repo.create_request(
                request_id=request_id,
                model_id=model_id,
                model_name=model_name,
                payload=payload,
                source="http",
                user=request_context.get(
                    "user"
                ),
                ip=request_context.get(
                    "ip"
                ),
            )

    async def _record_prediction_success(
            self,
            *,
            request_id: str,
            decision_id: str,
            result: ExecutionResult,
            shadow_routes: tuple[RouteResult, ...],
            features: dict[str, Any],
            response: dict[str, Any],
            latency_ms: float,
    ) -> tuple[ShadowTask, ...]:
        """记录成功请求、最终决策和模型执行

        Request 状态更新、Decision 创建和 Execution 创建
        在同一个事务中完成。

        参数：
            request_id: 请求 ID
            decision_id: 决策 ID
            result: 主模型执行结果
            shadow_routes: 命中的影子路由
            features: 模型输入特征
            response: 返回给调用方的业务响应
            latency_ms: 处理耗时
        """
        route = result.route
        prediction = result.prediction

        async with UnitOfWork() as uow:
            request_repo = RequestRepository(
                uow.session
            )

            decision_repo = DecisionRepository(
                uow.session
            )
            execution_repo = ExecutionRepository(
                uow.session
            )
            request_record = await request_repo.get_request(
                request_id
            )

            if request_record is None:
                raise RuntimeError(
                    f"请求记录不存在: {request_id}"
                )

            request_repo.mark_success(
                request_record,
                model_id=route.model_id,
                response=response,
                latency_ms=latency_ms,
            )

            decision_repo.create_decision(
                decision_id=decision_id,
                request_id=request_id,
                model_id=route.model_id,
                version_id=route.version_id,
                source=DecisionStrategy(
                    route.source
                ),
                deployment_id=route.deployment_id,
                experiment_id=route.experiment_id,
                variant_id=route.variant_id,
                assignment_id=route.assignment_id,
                subject_key=route.subject_key,
                subject_type=route.subject_type,
                strategy=route.strategy,
                bucket=route.bucket,
                group=route.group,
                weight=route.weight,
                decision=self._optional_string(
                    prediction.get(
                        "decision"
                    )
                ),
                context=self._build_decision_context(
                    route
                ),
            )

            finished_at = datetime.now(
                timezone.utc
            )
            started_at = finished_at - timedelta(
                milliseconds=result.latency_ms
            )
            execution_repo.create_execution(
                execution_id=generate_random_id(
                    prefix="exe"
                ),
                decision_id=decision_id,
                execution_type=(
                    result.plan.execution_type
                ),
                status=ExecutionStatus.SUCCESS,
                model_id=route.model_id,
                version_id=route.version_id,
                deployment_id=route.deployment_id,
                routing_id=route.routing_id,
                prediction=(
                    self._build_prediction_payload(
                        prediction
                    )
                ),
                probability=self._optional_float(
                    prediction.get(
                        "probability"
                    )
                ),
                score=self._optional_float(
                    prediction.get(
                        "score"
                    )
                ),
                latency_ms=result.latency_ms,
                context=self._build_decision_context(
                    route
                ),
                started_at=started_at,
                finished_at=finished_at,
            )

            shadow_tasks: list[ShadowTask] = []

            for shadow_route in shadow_routes:
                execution_id = generate_random_id(
                    prefix="exe"
                )
                shadow_plan = ExecutionPlan(
                    route=shadow_route,
                    execution_type=(
                        ExecutionType.SHADOW
                    ),
                    timeout=(
                        runtime_config.shadow_timeout
                    ),
                )
                execution_repo.create_execution(
                    execution_id=execution_id,
                    decision_id=decision_id,
                    execution_type=(
                        shadow_plan.execution_type
                    ),
                    status=ExecutionStatus.QUEUED,
                    model_id=shadow_route.model_id,
                    version_id=shadow_route.version_id,
                    deployment_id=(
                        shadow_route.deployment_id
                    ),
                    routing_id=shadow_route.routing_id,
                    context=self._build_decision_context(
                        shadow_route
                    ),
                )
                shadow_tasks.append(
                    ShadowTask(
                        execution_id=execution_id,
                        request_id=request_id,
                        decision_id=decision_id,
                        plan=shadow_plan,
                        features=deepcopy(features),
                    )
                )

        return tuple(
            shadow_tasks
        )

    async def _submit_shadow_predictions(
            self,
            tasks: tuple[ShadowTask, ...],
    ) -> None:
        """提交本次请求命中的影子预测"""
        for task in tasks:
            accepted = self.shadow_dispatcher.submit(
                task
            )

            if not accepted:
                self._logger.warning(
                    "影子预测任务未进入执行队列",
                    execution_id=task.execution_id,
                    request_id=task.request_id,
                    decision_id=task.decision_id,
                    deployment_id=(
                        task.plan.route.deployment_id
                    ),
                    routing_id=(
                        task.plan.route.routing_id
                    ),
                )
                await self._record_shadow_failure(
                    task=task,
                    status=ExecutionStatus.REJECTED,
                    error="影子预测执行队列不可用或已满",
                    error_type="ShadowQueueRejected",
                    latency_ms=0.0,
                )

    async def _execute_shadow(
            self,
            task: ShadowTask,
    ) -> None:
        """执行并记录单个影子预测"""
        started_at = time.perf_counter()

        try:
            await self._record_shadow_running(
                task
            )

            result = await self.executor.execute(
                plan=task.plan,
                features=task.features,
            )
            await self._record_shadow_success(
                task=task,
                result=result,
            )

            self._logger.info(
                "影子预测执行完成",
                execution_id=task.execution_id,
                request_id=task.request_id,
                decision_id=task.decision_id,
                deployment_id=(
                    task.plan.route.deployment_id
                ),
                routing_id=(
                    task.plan.route.routing_id
                ),
                latency_ms=result.latency_ms,
            )
        except asyncio.CancelledError:
            latency_ms = (
                                 time.perf_counter()
                                 - started_at
                         ) * 1000
            await asyncio.shield(
                self._record_shadow_failure(
                    task=task,
                    status=ExecutionStatus.CANCELLED,
                    error="影子预测执行已取消",
                    error_type="CancelledError",
                    latency_ms=latency_ms,
                )
            )
            raise
        except Exception as exc:
            latency_ms = (
                                 time.perf_counter()
                                 - started_at
                         ) * 1000
            error = (
                str(exc)
                or exc.__class__.__name__
            )
            status = (
                ExecutionStatus.TIMEOUT
                if isinstance(
                    exc,
                    TimeoutError,
                )
                else ExecutionStatus.FAILED
            )
            await self._record_shadow_failure(
                task=task,
                status=status,
                error=error,
                error_type=exc.__class__.__name__,
                latency_ms=latency_ms,
            )
            self._logger.warning(
                "影子预测执行失败",
                execution_id=task.execution_id,
                request_id=task.request_id,
                decision_id=task.decision_id,
                deployment_id=(
                    task.plan.route.deployment_id
                ),
                routing_id=(
                    task.plan.route.routing_id
                ),
                error=error,
            )

            try:
                await self._audit_recorder.record(
                    action="prediction.shadow",
                    target_type="deployment",
                    target_id=(
                        task.plan.route.deployment_id
                    ),
                    status="failed",
                    error=error,
                    context={
                        "request_id": task.request_id,
                        "decision_id": task.decision_id,
                        "execution_id": task.execution_id,
                        "routing_id": (
                            task.plan.route.routing_id
                        ),
                    },
                )
            except AuditError:
                self._logger.exception(
                    "影子预测失败审计记录写入失败",
                    request_id=task.request_id,
                    deployment_id=(
                        task.plan.route.deployment_id
                    ),
                )

    async def _record_shadow_success(
            self,
            *,
            task: ShadowTask,
            result: ExecutionResult,
    ) -> None:
        """记录成功的影子模型执行"""
        async with UnitOfWork() as uow:
            repo = ExecutionRepository(
                uow.session
            )
            execution = await repo.get_execution(
                task.execution_id
            )

            if execution is None:
                raise RuntimeError(
                    "影子模型执行记录不存在: "
                    f"{task.execution_id}"
                )

            repo.mark_success(
                execution,
                prediction=(
                    self._build_prediction_payload(
                        result.prediction
                    )
                ),
                probability=self._optional_float(
                    result.prediction.get(
                        "probability"
                    )
                ),
                score=self._optional_float(
                    result.prediction.get(
                        "score"
                    )
                ),
                latency_ms=result.latency_ms,
            )

    @staticmethod
    async def _record_shadow_running(
            task: ShadowTask,
    ) -> None:
        """标记影子模型执行开始"""
        async with UnitOfWork() as uow:
            repo = ExecutionRepository(
                uow.session
            )
            execution = await repo.get_execution(
                task.execution_id
            )

            if execution is None:
                raise RuntimeError(
                    "影子模型执行记录不存在: "
                    f"{task.execution_id}"
                )

            repo.mark_running(
                execution
            )

    @staticmethod
    async def _record_shadow_failure(
            *,
            task: ShadowTask,
            status: ExecutionStatus,
            error: str,
            error_type: str,
            latency_ms: float,
    ) -> None:
        """记录未成功的影子模型执行"""
        try:
            async with UnitOfWork() as uow:
                repo = ExecutionRepository(
                    uow.session
                )
                execution = await repo.get_execution(
                    task.execution_id
                )

                if execution is None:
                    logger.warning(
                        "影子模型执行记录不存在",
                        execution_id=task.execution_id,
                        decision_id=task.decision_id,
                    )
                    return

                repo.mark_failed(
                    execution,
                    status=status,
                    error=error,
                    error_type=error_type,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            logger.exception(
                "影子模型执行失败状态写入失败",
                execution_id=task.execution_id,
                decision_id=task.decision_id,
                error=str(exc),
            )

    @staticmethod
    async def _mark_request_failed(
            *,
            request_id: str,
            model_id: str | None,
            error: str,
            response: dict[str, Any],
            latency_ms: float,
    ) -> None:
        """标记请求处理失败

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            error: 错误信息
            response: 返回给调用方的错误响应
            latency_ms: 处理耗时
        """
        async with UnitOfWork() as uow:
            repo = RequestRepository(
                uow.session
            )

            request_record = await repo.get_request(
                request_id
            )

            if request_record is None:
                logger.warning(
                    "失败请求记录不存在",
                    request_id=request_id,
                )
                return

            if request_record.status == "success":
                return

            repo.mark_failed(
                request_record,
                error=error,
                model_id=model_id,
                response=response,
                latency_ms=latency_ms,
            )

    def _build_decision_context(
            self,
            route: RouteResult,
            *,
            batch_id: str | None = None,
            batch_index: int | None = None,
    ) -> dict[str, Any]:
        """构造不重复结构化决策字段的诊断上下文"""
        duplicate_fields = {
            "assignment_id",
            "bucket",
            "deployment_id",
            "environment",
            "experiment_id",
            "model_id",
            "strategy",
            "subject_key",
            "subject_type",
            "variant_id",
            "variant_name",
            "variant_weight",
            "version_id",
        }
        context = {
            key: value
            for key, value in route.context.items()
            if key not in duplicate_fields
        }
        assignment_source = context.pop(
            "source",
            None,
        )

        if assignment_source in {
            "existing_assignment",
            "new_assignment",
        }:
            context[
                "assignment_source"
            ] = assignment_source

        if route.routing_id is not None:
            context[
                "routing_id"
            ] = route.routing_id

        context.update({
            "framework": route.framework,
            "environment": route.environment,
            "worker_id": self.manager.worker_id,
        })

        if batch_id is not None:
            context["batch_id"] = batch_id

        if batch_index is not None:
            context["batch_index"] = batch_index

        return context

    @staticmethod
    def _build_prediction_payload(
            result: dict[str, Any],
    ) -> dict[str, Any]:
        """构造执行表中的模型预测结果

        去除模型和部署标识字段，
        保留服务类型和实际预测输出。

        参数：
            result: RuntimeService 预测结果

        返回：
            模型预测结果
        """
        identity_fields = {
            "deployment_id",
            "model_id",
            "version_id",
            "framework",
        }

        return {
            key: value
            for key, value in result.items()
            if key not in identity_fields
        }

    @staticmethod
    def _optional_float(
            value: Any,
    ) -> float | None:
        """安全转换可选浮点数"""
        if (
                value is None
                or isinstance(
            value,
            bool,
        )
        ):
            return None

        try:
            return float(
                value
            )

        except (
                TypeError,
                ValueError,
        ):
            return None

    @staticmethod
    def _optional_string(
            value: Any,
    ) -> str | None:
        """安全转换可选字符串"""
        if value is None:
            return None

        if not isinstance(
                value,
                str,
        ):
            return None

        return value

    async def _get_service(
            self,
            deployment_id: str,
    ) -> BaseRuntimeService:
        """获取当前 Worker 的 RuntimeService

        当本地模型尚未加载时，
        主动执行一次 reconcile_once，
        加速当前 Worker 所属环境的状态收敛。

        参数：
            deployment_id: 部署 ID

        返回：
            RuntimeService

        异常：
            RuntimeError:
                当前 Worker 无法提供该部署服务
        """
        runtime_model = self.manager.registry.get(
            deployment_id,
            touch=False,
        )

        if runtime_model is None:
            await self.reconciler.reconcile_once()

            runtime_model = self.manager.registry.get(
                deployment_id,
                touch=False,
            )

        if runtime_model is None:
            self._service_cache.pop(
                deployment_id,
                None,
            )

            raise RuntimeError(
                "当前 Worker 尚未加载部署模型: "
                f"{deployment_id}"
            )

        generation = (
            self.reconciler.get_applied_generation(
                deployment_id
            )
        )

        runtime_identity = id(
            runtime_model
        )

        cached = self._service_cache.get(
            deployment_id
        )

        if (
                cached is not None
                and cached.generation == generation
                and cached.runtime_identity
                == runtime_identity
        ):
            return cached.service

        async with self._service_lock:
            cached = self._service_cache.get(
                deployment_id
            )

            if (
                    cached is not None
                    and cached.generation == generation
                    and cached.runtime_identity
                    == runtime_identity
            ):
                return cached.service

            service = RuntimeServiceFactory.create(
                runtime_model=runtime_model,
            )

            self._service_cache[
                deployment_id
            ] = ServiceCacheEntry(
                service=service,
                generation=generation,
                runtime_identity=runtime_identity,
            )

            self._logger.info(
                "创建 Worker RuntimeService",
                worker_id=self.manager.worker_id,
                environment=(
                    service_config.environment
                ),
                deployment_id=deployment_id,
                service_type=(
                    service.SERVICE_TYPE
                ),
                generation=generation,
            )

            return service

    @staticmethod
    async def _validate_service_environment(
            *,
            deployment_id: str,
    ) -> None:
        """校验 Deployment 是否属于当前 Service 环境

        参数：
            deployment_id:
                部署 ID

        异常：
            ServiceDeploymentNotFoundError:
                部署不存在

            ServiceEnvironmentMismatchError:
                Deployment 环境与当前 Service
                环境不一致
        """
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(
                uow.session
            )

            deployment = (
                await repo.get_deployment(
                    deployment_id
                )
            )

            if deployment is None:
                raise ServiceDeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if (
                    deployment.environment
                    != service_config.environment
            ):
                raise ServiceEnvironmentMismatchError(
                    "部署环境与当前服务环境不一致: "
                    f"deployment_id={deployment_id}, "
                    f"deployment_environment="
                    f"{deployment.environment}, "
                    f"service_environment="
                    f"{service_config.environment}"
                )

            if deployment.status != str(DeploymentStatus.ACTIVE):
                raise RuntimeRouteError(
                    f"部署不可用: {deployment_id}"
                )

    @staticmethod
    def _build_service_info(
            service: BaseRuntimeService,
    ) -> dict[str, Any]:
        """构造 RuntimeService 信息

        参数：
            service: RuntimeService

        返回：
            RuntimeService 信息
        """
        return {
            "deployment_id": (
                service.deployment_id
            ),
            "model_id": service.model_id,
            "version_id": service.version_id,
            "framework": service.framework,
            "service_type": (
                service.SERVICE_TYPE
            ),
            "capabilities": (
                service.get_capability_names()
            ),
        }
