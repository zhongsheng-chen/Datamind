"""运行时预测处理测试

验证结果回流、单条与批量预测、记录持久化和影子执行行为。

核心功能：
  - test_predict_timeout_records_failure:
    请求预算覆盖各阶段，取消后不会继续成功流程
  - test_batch_timeout_uses_one_budget:
    整批执行超时后一次性标记已创建的请求
  - test_failure_finalization_is_bounded:
    失败记录阻塞时结束等待并记录异常
  - test_predict_batch_records_each_request_and_decision:
    验证批量预测记录每项请求和决策
  - test_submit_outcome_calls_feedback_service:
    验证结果回流接口调用业务服务
  - test_predict_records_successful_decision:
    验证单条预测创建请求并记录成功决策
  - test_predict_returns_error_and_marks_request_failed:
    验证预测失败时返回标准错误并标记请求
  - test_predict_returns_error_for_unknown_model_name:
    验证模型名称不存在时保留失败请求记录
  - test_predict_batch_rejects_mismatched_result_count:
    验证批量预测拒绝数量不匹配的结果
  - test_predict_batch_handles_invalid_feature_type:
    验证批量预测将非法特征类型作为请求错误处理
  - test_create_batch_request_records:
    验证批量请求记录包含批次索引和调用上下文
  - test_record_batch_success_creates_decisions:
    验证批量成功处理更新请求并创建决策
  - test_record_batch_success_requires_request_record:
    验证批量成功处理要求原始请求记录存在
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
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.audit.errors import AuditWriteError
from datamind.models.enums import ExecutionStatus, ExecutionType
from datamind.models.errors import RuntimeRouteError
from datamind.runtime.executor import ExecutionPlan, ExecutionResult
from datamind.runtime.routing import RouteResult
from datamind.runtime.server.schemas import (
    BatchPredictRequest,
    OutcomeFeedbackRequest,
    PredictRequest,
)
from datamind.runtime.shadow import ShadowTask


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["routing", "prediction", "persistence"])
async def test_predict_timeout_records_failure(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        stage: str,
) -> None:
    """请求预算覆盖各阶段，取消后不会继续成功流程"""
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
async def test_batch_timeout_uses_one_budget(runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """整批执行超时后一次性标记已创建的请求"""
    service_module = runtime_server.load_service_module(monkeypatch)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module, "service_config",
        service_module.service_config.model_copy(update={"timeout": 0.1}),
    )
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(return_value=MagicMock())
    service._create_batch_request_records = AsyncMock()
    service._mark_batch_failed = AsyncMock()
    service._record_batch_success = AsyncMock()

    async def wait_for_cancellation(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(
        "datamind.runtime.server.prediction.asyncio.to_thread",
        wait_for_cancellation,
    )
    response = await service._predict_batch(
        request=BatchPredictRequest(
            deployment_id="dep_test", features_list=[{"age": 35}, {"age": 45}],
        ),
        batch_id="req_batch",
    )
    assert response["error_type"] == "RequestTimeoutError"
    failure_call = service._mark_batch_failed.await_args
    assert failure_call is not None
    failure = failure_call.kwargs
    assert len(failure["request_ids"]) == 2
    assert failure["records_created"] is True
    service._record_batch_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_finalization_is_bounded(runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败记录阻塞时结束等待并记录异常"""
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
    """测试批量预测记录每项请求和决策"""
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
        predict_batch=MagicMock(return_value={
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "deployment_id": "dep_test",
            "framework": "sklearn",
            "service_type": "scoring",
            "count": 2,
            "predictions": [
                {"score": 680.0, **runtime_server.create_score_details(680.0)},
                {"score": 720.0, **runtime_server.create_score_details(720.0)},
            ],
        }),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(
        return_value=runtime_service
    )
    service._create_batch_request_records = AsyncMock()
    service._record_batch_success = AsyncMock()
    service._mark_batch_failed = AsyncMock()
    identifiers = iter((
        "req_1",
        "req_2",
        "dcs_1",
        "dcs_2",
    ))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service._predict_batch(
        request=BatchPredictRequest(
            deployment_id="dep_test",
            features_list=[
                {"age": 35},
                {"age": 45},
            ],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is True
    assert list(result) == [
        "success", "task_type", "count", "predictions", "request_id",
    ]
    assert result["task_type"] == "scoring"
    assert list(result["predictions"][0]) == [
        "success", "score", "score_intercept", "features", "request_id",
    ]
    assert result["request_id"] == "batch_test"
    service._create_batch_request_records.assert_awaited_once()
    service._record_batch_success.assert_awaited_once()
    assert result["predictions"] == [
        {"success": True, "score": 680.0, **runtime_server.create_score_details(680.0), "request_id": "req_1"},
        {"success": True, "score": 720.0, **runtime_server.create_score_details(720.0), "request_id": "req_2"},
    ]
    recorded_call = service._record_batch_success.await_args
    assert recorded_call is not None
    assert recorded_call.kwargs["request_ids"] == ["req_1", "req_2"]
    assert recorded_call.kwargs["decision_ids"] == ["dcs_1", "dcs_2"]
    assert recorded_call.kwargs["predictions"] == [
        {"score": 680.0, **runtime_server.create_score_details(680.0)},
        {"score": 720.0, **runtime_server.create_score_details(720.0)},
    ]


@pytest.mark.asyncio
async def test_submit_outcome_calls_feedback_service(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试结果回流接口调用业务服务"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    outcome_service = MagicMock()
    outcome_service.submit = AsyncMock(return_value={
        "created": True,
        "outcome": {
            "outcome_id": "out_test",
            "outcome_time": None,
            "created_at": None,
            "updated_at": None,
        },
    })
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "OutcomeService",
        lambda: outcome_service,
    )
    request = OutcomeFeedbackRequest(
        outcome_id="out_test",
        decision_id="dcs_test",
        subject_key="customer_10001",
        converted=True,
    )

    result = await service_module.DatamindRuntimeService.inner._submit_outcome(
        request=request,
        request_id="req_feedback",
    )

    assert result["success"] is True
    assert result["request_id"] == "req_feedback"
    outcome_service.submit.assert_awaited_once_with(
        outcome_id="out_test",
        subject_key="customer_10001",
        decision_id="dcs_test",
        request_id=None,
        subject_type=None,
        approved=None,
        converted=True,
        defaulted=None,
        overdue_days=None,
        amount=None,
        label=None,
        context=None,
        outcome_time=None,
    )


@pytest.mark.asyncio
async def test_predict_records_successful_decision(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测创建请求并记录成功决策"""
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
    service.shadow_dispatcher.submit.assert_called_once()
    submitted_task = (
        service.shadow_dispatcher.submit.call_args.args[0]
    )
    assert isinstance(
        submitted_task,
        ShadowTask,
    )
    assert submitted_task is shadow_task


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
    """测试预测失败时返回标准错误并标记请求"""
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
    """测试模型名称不存在时保留失败请求记录"""
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
async def test_predict_batch_rejects_mismatched_result_count(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测拒绝数量不匹配的结果"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        predict_batch=MagicMock(return_value={
            "predictions": [],
        }),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(
        return_value=runtime_service
    )
    service._create_batch_request_records = AsyncMock()
    service._record_batch_success = AsyncMock()
    service._mark_batch_failed = AsyncMock()
    identifiers = iter(("req_1", "dcs_1"))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service._predict_batch(
        request=BatchPredictRequest(
            deployment_id="dep_test",
            features_list=[{"age": 35}],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is False
    assert result["error_type"] == "RuntimeError"
    service._mark_batch_failed.assert_awaited_once()
    service._record_batch_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_predict_batch_handles_invalid_feature_type(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测将非法特征类型作为请求错误处理"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        predict_batch=MagicMock(side_effect=TypeError(
            "特征 annual_income 必须是数值"
        )),
    )
    service._validate_service_environment = AsyncMock()
    service._get_service = AsyncMock(return_value=runtime_service)
    service._create_batch_request_records = AsyncMock()
    service._mark_batch_failed = AsyncMock()
    service._record_batch_success = AsyncMock()
    identifiers = iter(("req_1", "dcs_1"))
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service._predict_batch(
        request=BatchPredictRequest(
            deployment_id="dep_test",
            features_list=[{"annual_income": "not-a-number"}],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is False
    assert result["error_type"] == "TypeError"
    service._mark_batch_failed.assert_awaited_once()
    service._record_batch_success.assert_not_awaited()
    service._logger.warning.assert_called_once()
    service._logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_create_batch_request_records(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量请求记录包含批次索引和调用上下文"""
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

    await service_module.DatamindRuntimeService.inner._create_batch_request_records(
        batch_id="batch_test",
        request_ids=["req_1", "req_2"],
        model_id="mdl_test",
        deployment_id="dep_test",
        features_list=[{"age": 35}, {"age": 45}],
    )

    assert request_repo.create_request.call_count == 2
    assert request_repo.create_request.call_args_list[0].kwargs == {
        "request_id": "req_1",
        "model_id": "mdl_test",
        "payload": {
            "batch_id": "batch_test",
            "batch_index": 0,
            "deployment_id": "dep_test",
            "features": {"age": 35},
        },
        "source": "http",
        "user": "alice",
        "ip": "127.0.0.1",
    }


@pytest.mark.asyncio
async def test_record_batch_success_creates_decisions(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理更新请求并创建决策"""
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
        source="deployment",
        strategy="manual",
    )

    await service._record_batch_success(
        batch_id="batch_test",
        request_ids=["req_1"],
        decision_ids=["dcs_1"],
        route=route,
        predictions=[{
            "probability": "0.8",
            "score": 720,
            "decision": "approved",
            **runtime_server.create_score_details(720.0),
        }],
        latency_ms=10.0,
    )

    request_repo.mark_success.assert_called_once_with(
        request_record,
        response={
            "success": True,
            "request_id": "req_1",
            "probability": "0.8",
            "score": 720,
            "decision": "approved",
            **runtime_server.create_score_details(720.0),
        },
        latency_ms=10.0,
    )
    assert decision_repo.create_decision.call_args.kwargs[
        "decision"
    ] == "approved"
    recorded_call = request_repo.mark_success.call_args
    assert recorded_call is not None
    assert list(recorded_call.kwargs["response"]) == [
        "success", "score", "probability", "decision", "score_intercept",
        "features", "request_id",
    ]
    execution = execution_repo.create_execution.call_args.kwargs
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
    assert execution["probability"] == 0.8
    assert execution["score"] == 720.0
    for key, value in runtime_server.create_score_details(720.0).items():
        assert execution["prediction"][key] == value


@pytest.mark.asyncio
async def test_record_batch_success_requires_request_record(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理要求原始请求记录存在"""
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
            route=RouteResult(
                model_id="mdl_test",
                version_id="ver_test",
                deployment_id="dep_test",
                framework="sklearn",
                environment="testing",
                source="deployment",
                strategy="manual",
            ),
            predictions=[{}],
            latency_ms=10.0,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("record_status", ["pending", "success"])
async def test_mark_batch_failed_updates_existing_records(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        record_status: str,
) -> None:
    """测试批量失败处理只更新存在的请求记录"""
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
    """测试创建请求记录并更新失败状态"""
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
    """测试单条预测成功时更新请求并创建决策"""
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
        call.kwargs
        for call in execution_repo.create_execution.call_args_list
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
    """测试单条成功处理要求请求记录存在"""
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
    """测试影子预测成功后更新对应执行记录"""
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
    """测试影子预测成功时只更新影子执行记录"""
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

    await service._execute_shadow(
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
    """测试影子预测失败不向主调用方传播"""
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

    await service._execute_shadow(
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
    """测试影子预测失败不受审计写入异常影响"""
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

    await service._execute_shadow(
        task
    )

    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_prediction_failed_handles_persistence_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录预测失败异常不会覆盖原始错误"""
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
    """测试决策负载过滤和可选值安全转换"""
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
    """测试运行时按公开模型名称解析内部模型 ID"""
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
