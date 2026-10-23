"""运行时预测处理测试.

验证单条与批量预测、记录持久化和影子执行行为。

核心功能：
  - test_predict_timeout_records_failure:
    验证请求预算覆盖各阶段，取消后不会继续成功流程
  - test_batch_timeout_isolated_per_item:
    验证单条预测超时不终止整个批次
  - test_failure_finalization_is_bounded:
    验证失败记录阻塞时结束等待并记录异常
  - test_predict_batch_records_each_request_and_decision:
    验证批量预测记录每项请求和决策
  - test_execute_routed_batch_groups_deployments_and_restores_order:
    验证批量预测按路由部署分组执行并恢复请求顺序
  - test_predict_records_successful_decision:
    验证单条预测创建请求并记录成功决策
  - test_predict_returns_error_and_marks_request_failed:
    验证预测失败时返回标准错误并标记请求
  - test_predict_returns_error_for_unknown_model_name:
    验证模型名称不存在时保留失败请求记录
  - test_predict_batch_allows_partial_success:
    验证单条失败不回滚已经成功的批次条目
  - test_predict_batch_handles_invalid_feature_type:
    验证批量预测将非法特征类型作为请求错误处理
  - test_prepare_batch_request_records:
    验证批量请求记录包含批次索引和调用上下文
  - test_prepare_batch_request_records_reuses_failed_requests:
    验证批次重试复用原请求 ID
  - test_record_batch_success_creates_decisions:
    验证批量成功处理更新请求并创建决策
  - test_record_batch_success_requires_request_record:
    验证批量成功处理要求原始请求记录存在
  - test_record_batch_item_failure_creates_failed_execution:
    验证路由后的批次失败记录决策和主执行
  - test_record_batch_item_failure_without_route_updates_request_only:
    验证路由前的批次失败只更新请求记录
  - test_mark_batch_failed_updates_existing_records:
    验证批量失败处理只更新存在的请求记录
  - test_create_and_mark_single_request_record:
    验证创建请求记录并更新失败状态
  - test_record_prediction_success_creates_decision:
    验证单条预测成功时更新请求并创建决策
  - test_record_prediction_success_requires_request_record:
    验证单条成功处理要求请求记录存在
  - test_record_shadow_success_updates_execution:
    验证影子预测成功后更新对应执行记录
  - test_execute_shadow_records_success_without_response:
    验证影子预测成功时只更新影子执行记录
  - test_execute_shadow_isolates_failure_and_writes_audit:
    验证影子预测失败不向主调用方传播
  - test_execute_shadow_isolates_audit_error:
    验证影子预测失败不受审计写入异常影响
  - test_mark_prediction_failed_handles_persistence_error:
    验证记录预测失败异常不会覆盖原始错误
  - test_prediction_payload_and_optional_values:
    验证决策负载过滤和可选值安全转换
  - test_resolve_model_id_uses_model_name:
    验证运行时按公开模型名称解析内部模型 ID
  - test_submit_batch_persists_before_publishing:
    测试异步批次先持久化再发布轻量级引用消息
  - test_submit_batch_rejects_unknown_model_before_persisting:
    测试批量提交在模型不存在时返回请求错误且不创建批次
  - test_get_batch_status_returns_persisted_result:
    测试批次状态查询以 PostgreSQL 记录为准
  - test_cancel_batch_records_request_and_revokes_task:
    测试取消同时更新业务状态并撤销 Celery 任务
  - test_cancel_batch_keeps_persisted_state_when_revoke_fails:
    测试 Broker 不可用时仍返回已经持久化的取消状态
  - test_retry_batch_uses_new_celery_task_id:
    测试业务重试不会复用可能已被撤销的 Celery 任务 ID
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from datamind.audit.errors import AuditWriteError
from datamind.models.enums import (
    DecisionStrategy,
    ExecutionStatus,
    ExecutionType,
)
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.executor import ExecutionPlan, ExecutionResult
from datamind.runtime.routing import RouteResult, RoutingPlan
from datamind.runtime.server.schemas import (
    BatchPredictRequest,
    PredictRequest,
    PredictionInstance,
)
from datamind.runtime.shadow import ShadowTask
from datamind.runtime.task_queue import TaskDispatchError


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["routing", "prediction", "persistence"])
async def test_predict_timeout_records_failure(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        stage: str,
) -> None:
    """测试请求预算覆盖各阶段，取消后不会继续成功流程."""
    service_module = runtime_server.load_service_module(monkeypatch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module, "service_config",
        service_module.service_config.model_copy(update={"timeout": 0.1}),
    )
    service = runtime_server.create_service(service_module)
    service._create_request_record = AsyncMock()
    service._mark_prediction_failed = AsyncMock()
    service._record_prediction_success = AsyncMock()
    service._submit_shadow_predictions = AsyncMock()
    service.executor.execute.return_value = SimpleNamespace(prediction={"score": 1})

    async def wait_for_cancellation(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.Event().wait()

    blocked = {
        "routing": service.router.resolve,
        "prediction": service.executor.execute,
        "persistence": service._record_prediction_success,
    }[stage]
    blocked.side_effect = wait_for_cancellation
    response = await service._predict(
        request=PredictRequest(
            model_name="scorecard", features={"age": 35},
        ),
        request_id="req_timeout",
    )
    assert response["success"] is False
    assert response["error_type"] == "RequestTimeoutError"
    assert stage in response["error"]
    ctx = SimpleNamespace(response=SimpleNamespace(status_code=200))
    service._apply_response_status(ctx=ctx, response=response)
    assert ctx.response.status_code == 504
    service._mark_prediction_failed.assert_awaited_once()
    failure_call = service._mark_prediction_failed.await_args
    assert failure_call is not None
    assert failure_call.kwargs["response"] == response
    service._submit_shadow_predictions.assert_not_awaited()
    if stage != "persistence":
        service._record_prediction_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_timeout_isolated_per_item(runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测超时只标记当前条目并继续执行批次."""
    service_module = runtime_server.load_service_module(monkeypatch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module, "service_config",
        service_module.service_config.model_copy(update={"timeout": 0.1}),
    )
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(return_value=MagicMock())
    service.router.resolve.return_value = SimpleNamespace(
        primary=RouteResult(
            model_id="mdl_test",
            version_id="ver_test",
            deployment_id="dep_test",
            framework="sklearn",
            environment="testing",
            source="deployment",
            strategy="fallback",
        ),
        shadows=(),
    )
    service._prepare_batch_request_records = AsyncMock(
        return_value=["req_1", "req_2"]
    )
    service._mark_batch_failed = AsyncMock()
    service._record_batch_success = AsyncMock()
    service._record_batch_item_failure = AsyncMock()

    async def wait_for_cancellation(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(
        "datamind.runtime.server.prediction.asyncio.to_thread",
        wait_for_cancellation,
    )
    response = await service.execute_batch_task(
        request=BatchPredictRequest(
            model_name="scorecard",
            instances=[
                PredictionInstance(
                    features={"age": 35},
                ),
                PredictionInstance(
                    features={"age": 45},
                ),
            ],
        ),
        batch_id="req_batch",
    )
    assert response["success"] is False
    assert response["succeeded_count"] == 0
    assert response["failed_count"] == 2
    assert all(
        item["error_type"] == "RequestTimeoutError"
        for item in response["predictions"]
    )
    assert service._record_batch_item_failure.await_count == 2
    service._mark_batch_failed.assert_not_awaited()
    service._record_batch_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_finalization_is_bounded(runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试失败记录阻塞时结束等待并记录异常."""
    service_module = runtime_server.load_service_module(monkeypatch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "REQUEST_TIMEOUT_GRACE_SECONDS",
        0.01,
    )
    service = runtime_server.create_service(service_module)

    async def wait_for_cancellation(**_kwargs: Any) -> None:
        await asyncio.Event().wait()

    service._mark_request_failed = AsyncMock(side_effect=wait_for_cancellation)
    await asyncio.wait_for(service._mark_prediction_failed(
        request_id="req_timeout", model_id=None, request_record_created=True,
        error="timeout", response={"success": False}, latency_ms=10,
    ), timeout=1)
    service._logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_predict_batch_records_each_request_and_decision(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测记录每项请求和决策."""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    service = runtime_server.create_service(
        service_module
    )
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        predict=MagicMock(side_effect=[
            {
                "task_type": "scoring",
                "score": 680.0,
                **runtime_server.create_score_details(680.0),
            },
            {
                "task_type": "scoring",
                "score": 720.0,
                **runtime_server.create_score_details(720.0),
            },
        ]),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(
        return_value=runtime_service
    )
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="experiment",
        strategy="hash",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
        subject_key="customer_1",
        subject_type="customer",
        group="treatment",
    )
    service.router.resolve.return_value = SimpleNamespace(
        primary=route,
        shadows=(),
    )
    service._prepare_batch_request_records = AsyncMock(
        return_value=["req_1", "req_2"]
    )
    service._record_batch_success = AsyncMock(return_value=())
    service._mark_batch_failed = AsyncMock()
    identifiers = iter((
        "dcs_1",
        "dcs_2",
    ))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service.execute_batch_task(
        request=BatchPredictRequest(
            model_name="scorecard",
            instances=[
                PredictionInstance(
                    subject_key="customer_1",
                    subject_type="customer",
                    features={"age": 35},
                ),
                PredictionInstance(
                    subject_key="customer_2",
                    subject_type="customer",
                    features={"age": 45},
                ),
            ],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is True
    assert list(result) == [
        "success", "task_type", "count", "succeeded_count",
        "failed_count", "predictions", "batch_id",
    ]
    assert result["task_type"] == "scoring"
    assert list(result["predictions"][0]) == [
        "success", "task_type", "score", "score_intercept", "features",
        "request_id",
    ]
    assert result["batch_id"] == "batch_test"
    assert service.router.resolve.await_count == 2
    assert [
        route_call.kwargs["subject_key"]
        for route_call in service.router.resolve.await_args_list
    ] == ["customer_1", "customer_2"]
    assert [
        route_call.kwargs["payload"]
        for route_call in service.router.resolve.await_args_list
    ] == [{"age": 35}, {"age": 45}]
    service._prepare_batch_request_records.assert_awaited_once()
    assert service._record_batch_success.await_count == 2
    assert result["predictions"] == [
        {"success": True, "task_type": "scoring", "score": 680.0, **runtime_server.create_score_details(680.0), "request_id": "req_1"},
        {"success": True, "task_type": "scoring", "score": 720.0, **runtime_server.create_score_details(720.0), "request_id": "req_2"},
    ]
    assert [
        item.kwargs["request_ids"]
        for item in service._record_batch_success.await_args_list
    ] == [["req_1"], ["req_2"]]
    assert [
        item.kwargs["batch_indices"]
        for item in service._record_batch_success.await_args_list
    ] == [[0], [1]]


@pytest.mark.asyncio
async def test_execute_routed_batch_groups_deployments_and_restores_order(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测按路由部署分组执行并恢复请求顺序."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    routes = [
        RouteResult(
            model_id="mdl_test",
            version_id=f"ver_{index}",
            deployment_id=deployment_id,
            framework="sklearn",
            environment="testing",
            source="routing",
            strategy="weighted",
        )
        for index, deployment_id in enumerate((
            "dep_a",
            "dep_b",
            "dep_a",
        ))
    ]
    routing_plans = [
        RoutingPlan(primary=route)
        for route in routes
    ]
    instances = [
        PredictionInstance(features={"value": value})
        for value in (10, 20, 30)
    ]
    service_a = SimpleNamespace(
        predict_batch=MagicMock(return_value={
            "task_type": "classification",
            "predictions": [
                {"prediction": 0},
                {"prediction": 1},
            ],
        })
    )
    service_b = SimpleNamespace(
        predict_batch=MagicMock(return_value={
            "task_type": "classification",
            "predictions": [
                {"prediction": 1},
            ],
        })
    )
    services = {
        "dep_a": service_a,
        "dep_b": service_b,
    }
    service._get_service = AsyncMock(
        side_effect=lambda deployment_id: services[deployment_id]
    )

    results, task_type = await service._execute_routed_batch(
        routing_plans=routing_plans,
        instances=instances,
    )

    assert task_type == "classification"
    assert [result.prediction for result in results] == [
        {"prediction": 0},
        {"prediction": 1},
        {"prediction": 1},
    ]
    assert [result.route for result in results] == routes
    service_a.predict_batch.assert_called_once_with([
        {"value": 10},
        {"value": 30},
    ])
    service_b.predict_batch.assert_called_once_with([
        {"value": 20},
    ])




@pytest.mark.asyncio
async def test_predict_records_successful_decision(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测创建请求并记录成功决策."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="deployment",
        strategy="fallback",
    )
    shadow_route = RouteResult(
        model_id="mdl_test",
        version_id="ver_shadow",
        deployment_id="dep_shadow",
        framework="sklearn",
        environment="testing",
        source="shadow",
        strategy="weighted",
        routing_id="rtn_shadow",
    )
    service._create_request_record = AsyncMock()
    routing_plan = SimpleNamespace(
        primary=route,
        shadows=(shadow_route,),
    )
    service.router.resolve.return_value = routing_plan
    execution_plan = ExecutionPlan(
        route=route,
        execution_type=(
            ExecutionType.PRIMARY
        ),
    )
    service.executor.execute.return_value = (
        ExecutionResult(
            plan=execution_plan,
            prediction={
                "score": 720.0,
                "probability": 0.8,
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "deployment_id": "dep_test",
                "framework": "sklearn",
                "service_type": "scoring",
                **runtime_server.create_score_details(720.0),
            },
            latency_ms=8.5,
        )
    )
    shadow_task = ShadowTask(
        execution_id="exe_shadow",
        request_id="req_test",
        decision_id="dcs_test",
        plan=ExecutionPlan(
            route=shadow_route,
            execution_type=(
                ExecutionType.SHADOW
            ),
            timeout=5.0,
        ),
        features={"age": 35},
    )
    service._record_prediction_success = AsyncMock(
        return_value=(shadow_task,)
    )
    service._mark_prediction_failed = AsyncMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: "dcs_test",
    )
    request = PredictRequest(
        model_name="scorecard",
        features={"age": 35},
    )

    result = await service._predict(
        request=request,
        request_id="req_test",
    )

    assert result["success"] is True
    assert result["request_id"] == "req_test"
    assert result["score"] == 720.0
    assert list(result) == [
        "success", "task_type", "score", "probability", "score_intercept", "features",
        "request_id",
    ]
    for key, value in runtime_server.create_score_details(720.0).items():
        assert result[key] == value
    service._create_request_record.assert_awaited_once()
    service._resolve_model_id.assert_awaited_once_with(
        model_name="scorecard"
    )
    assert (
        service.router.resolve.await_args.kwargs["model_id"]
        == "mdl_test"
    )
    service._record_prediction_success.assert_awaited_once()
    recorded_call = service._record_prediction_success.await_args
    assert recorded_call is not None
    recorded = recorded_call.kwargs
    assert list(recorded["response"]) == list(result)
    assert recorded["decision_id"] == "dcs_test"
    assert recorded["result"].route is route
    assert recorded["result"].prediction["model_id"] == "mdl_test"
    assert recorded["result"].prediction["service_type"] == "scoring"
    for key, value in runtime_server.create_score_details(720.0).items():
        assert recorded["response"][key] == value
        assert recorded["result"].prediction[key] == value
    service._mark_prediction_failed.assert_not_awaited()
    service.executor.execute.assert_awaited_once_with(
        plan=execution_plan,
        features={"age": 35},
    )
    service.task_publisher.submit_shadow.assert_called_once_with(
        execution_id=shadow_task.execution_id,
        task_id="dcs_test",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_source", "error"),
    [
        ("route", RuntimeRouteError("没有可用部署")),
        ("prediction", TypeError("特征 annual_income 必须是数值")),
        ("prediction", OSError("model unavailable")),
    ],
)
async def test_predict_returns_error_and_marks_request_failed(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        failure_source: str,
        error: Exception,
) -> None:
    """测试预测失败时返回标准错误并标记请求."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._create_request_record = AsyncMock()
    service._mark_prediction_failed = AsyncMock()
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="deployment",
        strategy="fallback",
    )

    if failure_source == "route":
        service.router.resolve.side_effect = error
    else:
        service.router.resolve.return_value = SimpleNamespace(
            primary=route,
            shadows=(),
        )
        service.executor.execute.side_effect = error

    result = await service._predict(
        request=PredictRequest(
            model_name="scorecard",
            features={"age": 35},
        ),
        request_id="req_test",
    )

    assert result["success"] is False
    assert list(result) == ["success", "error", "error_type", "request_id"]
    assert result["error_type"] == error.__class__.__name__
    service._mark_prediction_failed.assert_awaited_once()

    if isinstance(error, TypeError):
        service._logger.warning.assert_called_once()
        service._logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_predict_returns_error_for_unknown_model_name(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型名称不存在时保留失败请求记录."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._resolve_model_id.side_effect = ValueError(
        "模型不存在: missing-model"
    )
    service._create_request_record = AsyncMock()
    service._mark_prediction_failed = AsyncMock()

    result = await service._predict(
        request=PredictRequest(
            model_name="missing-model",
            features={"age": 35},
        ),
        request_id="req_test",
    )

    assert result["success"] is False
    assert result["error_type"] == "ValueError"
    service._create_request_record.assert_awaited_once_with(
        request_id="req_test",
        model_id=None,
        model_name="missing-model",
        payload={
            "model_name": "missing-model",
            "environment": "testing",
            "deployment_id": None,
            "subject_key": None,
            "subject_type": None,
            "features": {"age": 35},
        },
    )
    service._mark_prediction_failed.assert_awaited_once()
    failure_call = (
        service._mark_prediction_failed.await_args
    )
    assert failure_call is not None
    failure_kwargs = failure_call.kwargs
    assert failure_kwargs["model_id"] is None
    assert failure_kwargs["request_record_created"] is True
    assert failure_kwargs["error"] == (
        "模型不存在: missing-model"
    )


@pytest.mark.asyncio
async def test_predict_batch_allows_partial_success(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条失败不回滚已经成功的批次条目."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        predict=MagicMock(side_effect=[
            {"task_type": "scoring", "score": 680.0},
            TypeError("特征 annual_income 必须是数值"),
        ]),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(
        return_value=runtime_service
    )
    service.router.resolve.return_value = SimpleNamespace(
        primary=RouteResult(
            model_id="mdl_test",
            version_id="ver_test",
            deployment_id="dep_test",
            framework="sklearn",
            environment="testing",
            source="deployment",
            strategy="fallback",
        ),
        shadows=(),
    )
    service._prepare_batch_request_records = AsyncMock(
        return_value=["req_1", "req_2"]
    )
    service._record_batch_success = AsyncMock(return_value=())
    service._record_batch_item_failure = AsyncMock()
    service._mark_batch_failed = AsyncMock()
    identifiers = iter(("dcs_1",))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service.execute_batch_task(
        request=BatchPredictRequest(
            model_name="scorecard",
            instances=[
                PredictionInstance(features={"age": 35}),
                PredictionInstance(features={"annual_income": "invalid"}),
            ],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is False
    assert result["succeeded_count"] == 1
    assert result["failed_count"] == 1
    assert result["predictions"][0]["success"] is True
    assert result["predictions"][1]["error_type"] == "TypeError"
    service._record_batch_success.assert_awaited_once()
    service._record_batch_item_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_predict_batch_handles_invalid_feature_type(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测将非法特征类型作为请求错误处理."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        predict=MagicMock(side_effect=TypeError(
            "特征 annual_income 必须是数值"
        )),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(return_value=runtime_service)
    service.router.resolve.return_value = SimpleNamespace(
        primary=RouteResult(
            model_id="mdl_test",
            version_id="ver_test",
            deployment_id="dep_test",
            framework="sklearn",
            environment="testing",
            source="deployment",
            strategy="fallback",
        ),
        shadows=(),
    )
    service._prepare_batch_request_records = AsyncMock(
        return_value=["req_1"]
    )
    service._mark_batch_failed = AsyncMock()
    service._record_batch_item_failure = AsyncMock()
    service._record_batch_success = AsyncMock(return_value=())
    identifiers = iter(("req_1", "dcs_1"))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service.execute_batch_task(
        request=BatchPredictRequest(
            model_name="scorecard",
            instances=[PredictionInstance(
                features={
                    "annual_income": "not-a-number",
                },
            )],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is False
    assert result["succeeded_count"] == 0
    assert result["failed_count"] == 1
    assert result["predictions"][0]["error_type"] == "TypeError"
    service._record_batch_item_failure.assert_awaited_once()
    service._record_batch_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_batch_request_records(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量请求记录包含批次索引和调用上下文."""
    service_module = runtime_server.load_service_module(monkeypatch)
    request_repo, _, _, _ = runtime_server.install_repositories(
        service_module,
        monkeypatch,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "get_context",
        lambda: {
            "user": "alice",
            "ip": "127.0.0.1",
        },
    )
    identifiers = iter(("req_1", "req_2"))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    request_ids = await service_module.DatamindRuntimeService.inner._prepare_batch_request_records(
        batch_id="batch_test",
        model_id=None,
        model_name="scorecard",
        deployment_id=None,
        instances=[
            PredictionInstance(
                subject_key="customer_1",
                subject_type="customer",
                features={"age": 35},
            ),
            PredictionInstance(
                subject_key="customer_2",
                subject_type="customer",
                features={"age": 45},
            ),
        ],
    )

    assert request_ids == ["req_1", "req_2"]
    assert request_repo.create_request.call_count == 2
    assert request_repo.create_request.call_args_list[0].kwargs == {
        "request_id": "req_1",
        "batch_id": "batch_test",
        "batch_index": 0,
        "model_id": None,
        "model_name": "scorecard",
        "payload": {
            "model_name": "scorecard",
            "deployment_id": None,
            "subject_key": "customer_1",
            "subject_type": "customer",
            "features": {"age": 35},
        },
        "source": "http",
        "user": "alice",
        "ip": "127.0.0.1",
    }


@pytest.mark.asyncio
async def test_prepare_batch_request_records_reuses_failed_requests(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批次重试跳过成功记录并复用失败请求 ID."""
    service_module = runtime_server.load_service_module(monkeypatch)
    request_repo, _, _, _ = runtime_server.install_repositories(
        service_module,
        monkeypatch,
    )
    requests = [
        SimpleNamespace(
            request_id="req_1",
            batch_index=0,
            status="success",
        ),
        SimpleNamespace(
            request_id="req_2",
            batch_index=1,
            status="failed",
        ),
    ]
    request_repo.list_batch_requests = AsyncMock(
        return_value=requests
    )

    request_ids = await service_module.DatamindRuntimeService.inner._prepare_batch_request_records(
        batch_id="batch_test",
        model_id=None,
        model_name="scorecard",
        deployment_id=None,
        instances=[
            PredictionInstance(features={"age": 35}),
            PredictionInstance(features={"age": 45}),
        ],
    )

    assert request_ids == ["req_1", "req_2"]
    assert request_repo.reset_for_retry.call_args_list == [
        call(requests[1]),
    ]
    request_repo.create_request.assert_not_called()


@pytest.mark.asyncio
async def test_record_batch_success_creates_decisions(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理更新请求并创建决策."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    decision_repo = MagicMock()
    execution_repo = MagicMock()
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
        decision_repo=decision_repo,
        execution_repo=execution_repo,
    )
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="experiment",
        strategy="hash",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
        subject_key="customer_1",
        subject_type="customer",
        group="treatment",
    )
    shadow_route = RouteResult(
        model_id="mdl_test",
        version_id="ver_shadow",
        deployment_id="dep_shadow",
        framework="sklearn",
        environment="testing",
        source="shadow",
        strategy="weighted",
        routing_id="rtn_shadow",
    )
    prediction = {
        "score": 720,
        "probability": "0.8",
        "decision": "approved",
        **runtime_server.create_score_details(720.0),
    }
    response = {
        "success": True,
        **prediction,
        "request_id": "req_1",
    }

    shadow_tasks = await service._record_batch_success(
        batch_id="batch_test",
        request_ids=["req_1"],
        decision_ids=["dcs_1"],
        results=[ExecutionResult(
            plan=ExecutionPlan(
                route=route,
                execution_type=ExecutionType.PRIMARY,
            ),
            prediction=prediction,
            latency_ms=4.0,
        )],
        routing_plans=[RoutingPlan(
            primary=route,
            shadows=(shadow_route,),
        )],
        instances=[PredictionInstance(
            subject_key="customer_1",
            subject_type="customer",
            features={"age": 35},
        )],
        responses=[response],
        latency_ms=10.0,
    )

    request_repo.mark_success.assert_called_once_with(
        request_record,
        model_id="mdl_test",
        decision_id="dcs_1",
        response=response,
        latency_ms=10.0,
    )
    assert len(shadow_tasks) == 1
    assert shadow_tasks[0].request_id == "req_1"
    assert shadow_tasks[0].plan.route is shadow_route
    assert shadow_tasks[0].features == {"age": 35}
    assert decision_repo.create_decision.call_args.kwargs[
        "decision"
    ] == "approved"
    decision = decision_repo.create_decision.call_args.kwargs
    assert decision["source"] == DecisionStrategy.EXPERIMENT
    assert decision["experiment_id"] == "exp_test"
    assert decision["variant_id"] == "var_test"
    assert decision["assignment_id"] == "asn_test"
    recorded_call = request_repo.mark_success.call_args
    assert recorded_call is not None
    assert list(recorded_call.kwargs["response"]) == [
        "success", "score", "probability", "decision", "score_intercept",
        "features", "request_id",
    ]
    execution = execution_repo.create_execution.call_args_list[0].kwargs
    assert execution["decision_id"] == "dcs_1"
    assert execution["model_id"] == "mdl_test"
    assert execution["version_id"] == "ver_test"
    assert execution["deployment_id"] == "dep_test"
    assert execution["context"]["worker_id"] == "worker_test"
    assert execution["context"]["batch_id"] == "batch_test"
    assert execution["context"]["batch_index"] == 0
    assert execution["execution_type"] == (
        ExecutionType.PRIMARY
    )
    assert execution["status"] == (
        ExecutionStatus.SUCCESS
    )
    assert execution["latency_ms"] == 4.0
    assert execution["probability"] == 0.8
    assert execution["score"] == 720.0
    for key, value in runtime_server.create_score_details(720.0).items():
        assert execution["prediction"][key] == value
    shadow_execution = execution_repo.create_execution.call_args_list[1].kwargs
    assert shadow_execution["execution_type"] == ExecutionType.SHADOW
    assert shadow_execution["status"] == ExecutionStatus.QUEUED
    assert shadow_execution["deployment_id"] == "dep_shadow"


@pytest.mark.asyncio
async def test_record_batch_success_requires_request_record(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理要求原始请求记录存在."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(return_value=None)
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
    )

    with pytest.raises(
            RuntimeError,
            match="批量请求记录不存在",
    ):
        await service._record_batch_success(
            batch_id="batch_test",
            request_ids=["req_1"],
            decision_ids=["dcs_1"],
            results=[ExecutionResult(
                plan=ExecutionPlan(
                    route=RouteResult(
                        model_id="mdl_test",
                        version_id="ver_test",
                        deployment_id="dep_test",
                        framework="sklearn",
                        environment="testing",
                        source="deployment",
                        strategy="fallback",
                    ),
                    execution_type=ExecutionType.PRIMARY,
                ),
                prediction={},
                latency_ms=4.0,
            )],
            routing_plans=[RoutingPlan(primary=RouteResult(
                model_id="mdl_test",
                version_id="ver_test",
                deployment_id="dep_test",
                framework="sklearn",
                environment="testing",
                source="deployment",
                strategy="fallback",
            ))],
            instances=[PredictionInstance(
                features={"age": 35},
            )],
            responses=[{
                "success": True,
                "request_id": "req_1",
            }],
            latency_ms=10.0,
        )


@pytest.mark.asyncio
async def test_record_batch_item_failure_creates_failed_execution(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由后的批次失败记录决策和主执行."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    request_record = SimpleNamespace(status="received")
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(return_value=request_record)
    decision_repo = MagicMock()
    execution_repo = MagicMock()
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
        decision_repo=decision_repo,
        execution_repo=execution_repo,
    )
    identifiers = iter(("dcs_failed", "exe_failed"))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="deployment",
        strategy="fallback",
    )
    response = {
        "success": False,
        "error": "invalid feature",
        "error_type": "TypeError",
        "request_id": "req_1",
    }

    await service._record_batch_item_failure(
        request_id="req_1",
        batch_id="batch_test",
        batch_index=1,
        model_id="mdl_test",
        route=route,
        error=TypeError("invalid feature"),
        response=response,
        latency_ms=8.5,
    )

    request_repo.mark_failed.assert_called_once_with(
        request_record,
        error="invalid feature",
        model_id="mdl_test",
        decision_id="dcs_failed",
        response=response,
        latency_ms=8.5,
    )
    decision = decision_repo.create_decision.call_args.kwargs
    assert decision["decision_id"] == "dcs_failed"
    assert decision["request_id"] == "req_1"
    assert decision["context"]["batch_id"] == "batch_test"
    assert decision["context"]["batch_index"] == 1
    execution = execution_repo.create_execution.call_args.kwargs
    assert execution["execution_id"] == "exe_failed"
    assert execution["decision_id"] == "dcs_failed"
    assert execution["execution_type"] == ExecutionType.PRIMARY
    assert execution["status"] == ExecutionStatus.FAILED
    assert execution["error_type"] == "TypeError"
    assert execution["error"] == "invalid feature"


@pytest.mark.asyncio
async def test_record_batch_item_failure_without_route_updates_request_only(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由前的批次失败只更新请求记录."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._mark_request_failed = AsyncMock()

    await service._record_batch_item_failure(
        request_id="req_1",
        batch_id="batch_test",
        batch_index=0,
        model_id="mdl_test",
        route=None,
        error=RuntimeRouteError("route not found"),
        response={"success": False},
        latency_ms=3.0,
    )

    service._mark_request_failed.assert_awaited_once_with(
        request_id="req_1",
        model_id="mdl_test",
        error="route not found",
        response={"success": False},
        latency_ms=3.0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("record_status", ["pending", "success"])
async def test_mark_batch_failed_updates_existing_records(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        record_status: str,
) -> None:
    """测试批量失败处理只更新存在的请求记录."""
    service_module = runtime_server.load_service_module(monkeypatch)
    request_record = SimpleNamespace(status=record_status)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        side_effect=[request_record, None]
    )
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
    )

    await service_module.DatamindRuntimeService.inner._mark_batch_failed(
        request_ids=["req_1", "req_2"],
        records_created=True,
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )

    if record_status == "success":
        request_repo.mark_failed.assert_not_called()
        return

    request_repo.mark_failed.assert_called_once_with(
        request_record,
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
            "request_id": "req_1",
        },
        latency_ms=10.0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("record_status", ["pending", "success"])
async def test_create_and_mark_single_request_record(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        record_status: str,
) -> None:
    """测试创建请求记录并更新失败状态."""
    service_module = runtime_server.load_service_module(monkeypatch)
    request_record = SimpleNamespace(status=record_status)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "get_context",
        lambda: {
            "user": "alice",
            "ip": "127.0.0.1",
        },
    )
    service_class = service_module.DatamindRuntimeService.inner

    await service_class._create_request_record(
        request_id="req_test",
        model_id=None,
        model_name="scorecard",
        payload={
            "model_name": "scorecard",
            "features": {"age": 35},
        },
    )
    await service_class._mark_request_failed(
        request_id="req_test",
        model_id="mdl_test",
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )

    request_repo.create_request.assert_called_once()
    if record_status == "success":
        request_repo.mark_failed.assert_not_called()
        return

    request_repo.mark_failed.assert_called_once_with(
        request_record,
        error="prediction failed",
        model_id="mdl_test",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )


@pytest.mark.asyncio
async def test_record_prediction_success_creates_decision(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测成功时更新请求并创建决策."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    decision_repo = MagicMock()
    execution_repo = MagicMock()
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
        decision_repo=decision_repo,
        execution_repo=execution_repo,
    )
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="experiment",
        strategy="hash",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
        subject_key="customer_10001",
    )
    shadow_route = RouteResult(
        model_id="mdl_test",
        version_id="ver_shadow",
        deployment_id="dep_shadow",
        framework="sklearn",
        environment="testing",
        source="shadow",
        strategy="weighted",
        routing_id="rtn_shadow",
    )
    execution_ids = iter([
        "exe_primary",
        "exe_shadow",
    ])
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(execution_ids),
    )

    tasks = await service._record_prediction_success(
        request_id="req_test",
        decision_id="dcs_test",
        result=ExecutionResult(
            plan=ExecutionPlan(
                route=route,
                execution_type=(
                    ExecutionType.PRIMARY
                ),
            ),
            prediction={
                "deployment_id": "dep_test",
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "framework": "sklearn",
                "service_type": "scoring",
                "probability": "0.8",
                "score": 720,
                "decision": "approved",
                **runtime_server.create_score_details(720.0),
            },
            latency_ms=8.5,
        ),
        shadow_routes=(shadow_route,),
        features={"age": 35},
        response={
            "success": True,
            "request_id": "req_test",
            "score": 720,
        },
        latency_ms=10.0,
    )

    request_repo.mark_success.assert_called_once_with(
        request_record,
        model_id="mdl_test",
        decision_id="dcs_test",
        response={
            "success": True,
            "request_id": "req_test",
            "score": 720,
        },
        latency_ms=10.0,
    )
    decision = decision_repo.create_decision.call_args.kwargs
    assert decision["decision"] == "approved"
    for key in ("model_id", "version_id", "deployment_id", "experiment_id", "variant_id", "assignment_id"):
        assert decision[key] == getattr(route, key)
    assert decision["request_id"] == "req_test"
    assert decision["decision_id"] == "dcs_test"
    assert decision["context"] == {
        "framework": "sklearn",
        "environment": "testing",
        "worker_id": "worker_test",
    }
    executions = [
        execution_call.kwargs
        for execution_call in execution_repo.create_execution.call_args_list
    ]
    assert executions[0]["execution_id"] == "exe_primary"
    assert executions[0]["execution_type"] == (
        ExecutionType.PRIMARY
    )
    assert executions[0]["status"] == (
        ExecutionStatus.SUCCESS
    )
    assert executions[0]["prediction"] == {
        "service_type": "scoring",
        "probability": "0.8",
        "score": 720,
        "decision": "approved",
        **runtime_server.create_score_details(720.0),
    }
    assert executions[0]["probability"] == 0.8
    assert executions[0]["score"] == 720.0
    assert executions[0]["latency_ms"] == 8.5
    assert executions[1]["execution_id"] == "exe_shadow"
    assert executions[1]["execution_type"] == (
        ExecutionType.SHADOW
    )
    assert executions[1]["status"] == (
        ExecutionStatus.QUEUED
    )
    assert tasks == (
        ShadowTask(
            execution_id="exe_shadow",
            request_id="req_test",
            decision_id="dcs_test",
            plan=ExecutionPlan(
                route=shadow_route,
                execution_type=(
                    ExecutionType.SHADOW
                ),
                timeout=(
                    service_module
                    .runtime_config
                    .shadow_timeout
                ),
            ),
            features={"age": 35},
        ),
    )


@pytest.mark.asyncio
async def test_record_prediction_success_requires_request_record(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条成功处理要求请求记录存在."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(return_value=None)
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
    )

    with pytest.raises(
            RuntimeError,
            match="请求记录不存在",
    ):
        await service._record_prediction_success(
            request_id="req_test",
            decision_id="dcs_test",
            result=ExecutionResult(
                plan=ExecutionPlan(
                    route=RouteResult(
                        model_id="mdl_test",
                        version_id="ver_test",
                        deployment_id="dep_test",
                        framework="sklearn",
                        environment="testing",
                        source="deployment",
                        strategy="fallback",
                    ),
                    execution_type=(
                        ExecutionType.PRIMARY
                    ),
                ),
                prediction={},
                latency_ms=8.5,
            ),
            shadow_routes=(),
            features={"age": 35},
            response={
                "success": True,
            },
            latency_ms=10.0,
        )


@pytest.mark.asyncio
async def test_record_shadow_success_updates_execution(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试影子预测成功后更新对应执行记录."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    execution = MagicMock()
    execution_repo = MagicMock()
    execution_repo.get_execution = AsyncMock(
        return_value=execution
    )
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        execution_repo=execution_repo,
    )
    task = ShadowTask(
        execution_id="exe_shadow",
        request_id="req_test",
        decision_id="dcs_primary",
        plan=ExecutionPlan(
            route=RouteResult(
                model_id="mdl_test",
                version_id="ver_shadow",
                deployment_id="dep_shadow",
                framework="sklearn",
                environment="testing",
                source="shadow",
                strategy="weighted",
                routing_id="rtn_shadow",
                subject_key="customer_10001",
                weight=0.25,
            ),
            execution_type=(
                ExecutionType.SHADOW
            ),
        ),
        features={"age": 35},
    )

    await service._record_shadow_success(
        task=task,
        result=ExecutionResult(
            plan=task.plan,
            prediction={
                "score": 710,
                "probability": 0.7,
                "service_type": "scoring",
                **runtime_server.create_score_details(710.0),
            },
            latency_ms=8.5,
        ),
    )

    execution_repo.get_execution.assert_awaited_once_with(
        "exe_shadow"
    )
    updated = execution_repo.mark_success.call_args.kwargs
    assert updated["prediction"] == {
        "score": 710,
        "probability": 0.7,
        "service_type": "scoring",
        **runtime_server.create_score_details(710.0),
    }
    assert updated["probability"] == 0.7
    assert updated["score"] == 710.0
    assert updated["latency_ms"] == 8.5


@pytest.mark.asyncio
async def test_execute_shadow_records_success_without_response(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试影子预测成功时只更新影子执行记录."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._record_shadow_success = AsyncMock()
    service._record_shadow_running = AsyncMock()
    route = RouteResult(
        model_id="mdl_test",
        version_id="ver_shadow",
        deployment_id="dep_shadow",
        framework="sklearn",
        environment="testing",
        source="shadow",
        strategy="weighted",
    )
    plan = ExecutionPlan(
        route=route,
        execution_type=(
            ExecutionType.SHADOW
        ),
        timeout=5.0,
    )
    result = ExecutionResult(
        plan=plan,
        prediction={
            "score": 710.0,
        },
        latency_ms=8.5,
    )
    service.executor.execute.return_value = result
    task = ShadowTask(
        execution_id="exe_shadow",
        request_id="req_test",
        decision_id="dcs_primary",
        plan=plan,
        features={"age": 35},
    )

    await service.execute_shadow_task(
        task
    )

    service._record_shadow_running.assert_awaited_once_with(
        task
    )
    service.executor.execute.assert_awaited_once_with(
        plan=plan,
        features={"age": 35},
    )
    service._record_shadow_success.assert_awaited_once_with(
        task=task,
        result=result,
    )


@pytest.mark.asyncio
async def test_execute_shadow_isolates_failure_and_writes_audit(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试影子预测失败不向主调用方传播."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.executor.execute.side_effect = RuntimeError(
        "shadow unavailable"
    )
    service._record_shadow_success = AsyncMock()
    service._record_shadow_running = AsyncMock()
    service._record_shadow_failure = AsyncMock()
    task = ShadowTask(
        execution_id="exe_shadow",
        request_id="req_test",
        decision_id="dcs_primary",
        plan=ExecutionPlan(
            route=RouteResult(
                model_id="mdl_test",
                version_id="ver_shadow",
                deployment_id="dep_shadow",
                framework="sklearn",
                environment="testing",
                source="shadow",
                strategy="weighted",
                routing_id="rtn_shadow",
            ),
            execution_type=(
                ExecutionType.SHADOW
            ),
            timeout=5.0,
        ),
        features={"age": 35},
    )

    await service.execute_shadow_task(
        task
    )

    service._record_shadow_success.assert_not_awaited()
    failure = service._record_shadow_failure.await_args
    assert failure is not None
    assert failure.kwargs["task"] is task
    assert failure.kwargs["status"] == (
        ExecutionStatus.FAILED
    )
    assert failure.kwargs["error"] == "shadow unavailable"
    audit = runtime_server.get_audit_recorder(service)
    audit.record.assert_awaited_once_with(
        action="prediction.shadow",
        target_type="deployment",
        target_id="dep_shadow",
        status="failed",
        error="shadow unavailable",
        context={
            "request_id": "req_test",
            "decision_id": "dcs_primary",
            "execution_id": "exe_shadow",
            "routing_id": "rtn_shadow",
        },
    )


@pytest.mark.asyncio
async def test_execute_shadow_isolates_audit_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试影子预测失败不受审计写入异常影响."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.executor.execute.side_effect = RuntimeError(
        "shadow unavailable"
    )
    service._record_shadow_running = AsyncMock()
    service._record_shadow_failure = AsyncMock()
    audit = runtime_server.get_audit_recorder(service)
    audit.record.side_effect = AuditWriteError()
    task = ShadowTask(
        execution_id="exe_shadow",
        request_id="req_test",
        decision_id="dcs_primary",
        plan=ExecutionPlan(
            route=RouteResult(
                model_id="mdl_test",
                version_id="ver_shadow",
                deployment_id="dep_shadow",
                framework="sklearn",
                environment="testing",
                source="shadow",
                strategy="weighted",
            ),
            execution_type=(
                ExecutionType.SHADOW
            ),
        ),
        features={"age": 35},
    )

    await service.execute_shadow_task(
        task
    )

    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_prediction_failed_handles_persistence_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录预测失败异常不会覆盖原始错误."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._mark_request_failed = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )

    await service._mark_prediction_failed(
        request_id="req_test",
        model_id="mdl_test",
        request_record_created=False,
        error="prediction failed",
        response={
            "success": False,
        },
        latency_ms=10.0,
    )
    service._mark_request_failed.assert_not_awaited()

    await service._mark_prediction_failed(
        request_id="req_test",
        model_id="mdl_test",
        request_record_created=True,
        error="prediction failed",
        response={
            "success": False,
        },
        latency_ms=10.0,
    )
    service._mark_request_failed.assert_awaited_once()


def test_prediction_payload_and_optional_values(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试决策负载过滤和可选值安全转换."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service_class = service_module.DatamindRuntimeService.inner
    request = PredictRequest(
        model_name="scorecard",
        deployment_id="dep_test",
        subject_key="customer_10001",
        subject_type="customer",
        features={"age": 35},
    )

    assert service_class._build_request_payload(request) == {
        "model_name": "scorecard",
        "environment": "testing",
        "deployment_id": "dep_test",
        "subject_key": "customer_10001",
        "subject_type": "customer",
        "features": {"age": 35},
    }
    assert service_class._build_prediction_payload({
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "score": 720.0,
    }) == {
        "score": 720.0,
    }

    assert service_class._optional_float("0.8") == 0.8
    assert service_class._optional_float(None) is None
    assert service_class._optional_float(True) is None
    assert service_class._optional_float("invalid") is None
    assert service_class._optional_float(object()) is None
    assert service_class._optional_string("approved") == "approved"
    assert service_class._optional_string(None) is None
    assert service_class._optional_string(1) is None


@pytest.mark.asyncio
async def test_resolve_model_id_uses_model_name(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行时按公开模型名称解析内部模型 ID."""
    service_module = runtime_server.load_service_module(monkeypatch)
    repo = MagicMock()
    repo.get_model = AsyncMock(
        return_value=SimpleNamespace(
            model_id="mdl_test"
        )
    )
    repository_factory = MagicMock(
        return_value=repo
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "UnitOfWork",
        runtime_server.FakeUnitOfWork,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "MetadataRepository",
        repository_factory,
    )

    model_id = await (
        service_module.DatamindRuntimeService.inner
        ._resolve_model_id(
            model_name="scorecard"
        )
    )

    assert model_id == "mdl_test"
    repo.get_model.assert_awaited_once_with(
        name="scorecard"
    )


@pytest.mark.asyncio
async def test_submit_batch_persists_before_publishing(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试异步批次先持久化再发布轻量级引用消息."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    repository = MagicMock()
    attempt_repository = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        lambda _session: repository,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "AttemptRepository",
        lambda _session: attempt_repository,
    )
    request = BatchPredictRequest(
        model_name="scorecard",
        instances=[
            PredictionInstance(features={"age": 35}),
            PredictionInstance(features={"age": 45}),
        ],
    )

    result = await service._submit_batch(
        request=request,
        batch_id="bat_test",
    )

    assert result == {
        "success": True,
        "batch_id": "bat_test",
        "status": "queued",
        "submitted_count": 2,
        "status_url": "/predict/batch/status",
    }
    created = repository.create_batch.call_args.kwargs
    assert created["batch_id"] == "bat_test"
    assert created["model_id"] == "mdl_test"
    assert created["total_count"] == 2
    assert created["payload"] == request.model_dump(mode="json")
    attempt_repository.create_attempt.assert_called_once_with(
        batch_id="bat_test",
        task_id=created["task_id"],
        attempt_number=1,
    )
    service._resolve_model_id.assert_awaited_once_with(
        model_name="scorecard",
    )
    service.task_publisher.submit_batch.assert_called_once_with(
        batch_id="bat_test",
        task_id=created["task_id"],
    )


@pytest.mark.asyncio
async def test_submit_batch_rejects_unknown_model_before_persisting(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量提交在模型不存在时返回请求错误且不创建批次."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    repository_factory = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        repository_factory,
    )
    service._resolve_model_id.side_effect = ValueError(
        "模型不存在: missing-model"
    )

    result = await service._submit_batch(
        request=BatchPredictRequest(
            model_name="missing-model",
            instances=[
                PredictionInstance(features={"age": 35}),
            ],
        ),
        batch_id="bat_test",
    )

    assert result == {
        "success": False,
        "batch_id": "bat_test",
        "error": "模型不存在: missing-model",
        "error_type": "ValueError",
    }
    ctx = SimpleNamespace(response=SimpleNamespace(status_code=200))
    service._apply_response_status(ctx=ctx, response=result)
    assert ctx.response.status_code == 400
    repository_factory.assert_not_called()
    service.task_publisher.submit_batch.assert_not_called()


@pytest.mark.asyncio
async def test_get_batch_status_returns_persisted_result(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批次状态查询以 PostgreSQL 记录为准."""
    service_module = runtime_server.load_service_module(monkeypatch)
    batch = SimpleNamespace(
        batch_id="bat_test",
        status="succeeded",
        total_count=2,
        completed_count=2,
        succeeded_count=2,
        failed_count=0,
        attempt_count=1,
        created_at=None,
        started_at=None,
        finished_at=None,
        error=None,
        result={"predictions": [{"request_id": "req_test"}]},
    )
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        lambda _session: repository,
    )

    result = await service_module.PredictionMixin._get_batch_status(
        "bat_test"
    )

    assert result["status"] == "succeeded"
    assert result["result"] == batch.result


@pytest.mark.asyncio
async def test_cancel_batch_records_request_and_revokes_task(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试取消同时更新业务状态并撤销 Celery 任务."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    batch = SimpleNamespace(
        batch_id="bat_test",
        task_id="tsk_test",
        status="cancelled",
        total_count=2,
        completed_count=0,
        succeeded_count=0,
        failed_count=0,
        attempt_count=0,
        created_at=None,
        started_at=None,
        finished_at=None,
        error=None,
        result=None,
    )
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.request_cancel = AsyncMock(return_value=batch)
    attempt_repository = MagicMock()
    attempt_repository.mark_finished = AsyncMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        lambda _session: repository,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "AttemptRepository",
        lambda _session: attempt_repository,
    )

    result = await service._cancel_batch("bat_test")

    assert result["status"] == "cancelled"
    repository.request_cancel.assert_awaited_once_with("bat_test")
    attempt_repository.mark_finished.assert_awaited_once_with(
        batch_id="bat_test",
        status="cancelled",
    )
    service.task_publisher.revoke.assert_called_once_with("tsk_test")


@pytest.mark.asyncio
async def test_cancel_batch_keeps_persisted_state_when_revoke_fails(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Broker 不可用时仍返回已经持久化的取消状态."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    batch = SimpleNamespace(
        batch_id="bat_test",
        task_id="tsk_test",
        status="cancelling",
        total_count=2,
        completed_count=0,
        succeeded_count=0,
        failed_count=0,
        attempt_count=1,
        created_at=None,
        started_at=None,
        finished_at=None,
        error=None,
        result=None,
    )
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    repository.request_cancel = AsyncMock(return_value=batch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        lambda _session: repository,
    )
    service.task_publisher.revoke.side_effect = TaskDispatchError(
        "broker unavailable"
    )

    result = await service._cancel_batch("bat_test")

    assert result["success"] is True
    assert result["status"] == "cancelling"
    repository.request_cancel.assert_awaited_once_with("bat_test")
    service.task_publisher.revoke.assert_called_once_with("tsk_test")


@pytest.mark.asyncio
async def test_retry_batch_uses_new_celery_task_id(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试业务重试不会复用可能已被撤销的 Celery 任务 ID."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    batch = SimpleNamespace(
        batch_id="bat_test",
        task_id="tsk_old",
        status="queued",
        total_count=2,
        completed_count=0,
        succeeded_count=0,
        failed_count=0,
        attempt_count=1,
        created_at=None,
        started_at=None,
        finished_at=None,
        error=None,
        result=None,
    )
    repository = MagicMock()
    repository.get_batch = AsyncMock(return_value=batch)
    attempt_repository = MagicMock()
    attempt_repository.create_next_attempt = AsyncMock()

    async def retry(
            _batch_id: str,
            *,
            task_id: str,
    ) -> Any:
        batch.task_id = task_id
        return batch

    repository.retry = AsyncMock(side_effect=retry)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "BatchRepository",
        lambda _session: repository,
    )
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "AttemptRepository",
        lambda _session: attempt_repository,
    )

    result = await service._retry_batch("bat_test")

    assert result["status"] == "queued"
    assert batch.task_id != "tsk_old"
    attempt_repository.create_next_attempt.assert_awaited_once_with(
        batch_id="bat_test",
        task_id=batch.task_id,
    )
    service.task_publisher.submit_batch.assert_called_once_with(
        batch_id="bat_test",
        task_id=batch.task_id,
    )
