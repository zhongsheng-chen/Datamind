# tests/runtime/server/test_service.py

"""运行时服务接口行为测试

验证 Worker 生命周期、运行控制、预测执行、持久化和错误响应行为。

核心功能：
  - 验证 Worker 启动、关闭、健康和就绪状态
  - 验证认证执行包装和 HTTP 状态映射
  - 验证加载、卸载、重载和状态查询
  - 验证单条及批量预测的成功和失败处理
  - 验证请求、决策记录和运行时服务缓存
"""

import asyncio
from contextlib import asynccontextmanager
from importlib import import_module
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import MutableHeaders

from datamind.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from datamind.auth.schemas import TokenResponse
from datamind.models.errors import RuntimeRouteError


def load_service_module(
        monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """在隔离服务环境中加载运行时服务模块"""
    monkeypatch.setenv(
        "DATAMIND_SERVICE_ENVIRONMENT",
        "testing",
    )

    return import_module(
        "datamind.runtime.server.service"
    )


def create_service(
        service_module: Any,
) -> Any:
    """创建跳过初始化的运行时服务对象"""
    service_class = service_module.DatamindRuntimeService.inner
    service = object.__new__(
        service_class
    )
    service.manager = MagicMock()
    service.manager.worker_id = "worker_test"
    service.manager.all.return_value = []
    service.manager.count.return_value = 0
    service.manager.to_dicts.return_value = []
    service.manager.status = AsyncMock(return_value={})
    service.manager.stop = AsyncMock()
    service.router = MagicMock()
    service.router.resolve = AsyncMock()
    service.controller = MagicMock()
    service.controller.load = AsyncMock()
    service.controller.unload = AsyncMock()
    service.controller.reload = AsyncMock()
    service.controller.get_status = AsyncMock()
    service.reconciler = MagicMock()
    service.reconciler.is_running = True
    service.reconciler.reconcile_once = AsyncMock()
    service.reconciler.start = AsyncMock()
    service.reconciler.stop = AsyncMock()
    service.reconciler.get_applied_generation.return_value = None
    service.reconciler.get_applied_generations.return_value = {}
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    vars(service).update({
        "_service_cache": {},
        "_service_lock": asyncio.Lock(),
        "_audit_recorder": audit_recorder,
    })
    return service


def get_service_cache(
        service: Any,
) -> dict[str, Any]:
    """获取测试服务的本地服务缓存"""
    return vars(service)["_service_cache"]


def get_audit_recorder(
        service: Any,
) -> MagicMock:
    """获取测试服务的审计记录器替身"""
    return vars(service)["_audit_recorder"]


class FakeUnitOfWork:
    """运行时服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.execute = AsyncMock()
        FakeUnitOfWork.latest = self

    latest: "FakeUnitOfWork | None" = None

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


class SecurityStub:
    """运行时安全请求作用域替身"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @asynccontextmanager
    async def request_scope(
            self,
            **kwargs: Any,
    ):
        """进入测试身份请求作用域"""
        self.calls.append(kwargs)
        yield SimpleNamespace(
            username="alice"
        )


class AuthContextStub:
    """运行时认证请求上下文替身"""

    def __init__(self) -> None:
        self.request = SimpleNamespace(
            headers={
                "user-agent": "pytest",
            },
            client=SimpleNamespace(
                host="127.0.0.1"
            ),
        )
        self.response = SimpleNamespace(
            status_code=200,
            headers=MutableHeaders(),
        )


def install_repositories(
        service_module: Any,
        monkeypatch: pytest.MonkeyPatch,
        *,
        request_repo: MagicMock | None = None,
        decision_repo: MagicMock | None = None,
        deployment_repo: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """安装运行时服务仓储替身"""
    request_repository = request_repo or MagicMock()
    decision_repository = decision_repo or MagicMock()
    deployment_repository = deployment_repo or MagicMock()

    if not isinstance(
            request_repository.get_request,
            AsyncMock,
    ):
        request_repository.get_request = AsyncMock()

    if not isinstance(
            deployment_repository.get_deployment,
            AsyncMock,
    ):
        deployment_repository.get_deployment = AsyncMock()

    monkeypatch.setitem(
        vars(service_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(service_module),
        "RequestRepository",
        lambda _session: request_repository,
    )
    monkeypatch.setitem(
        vars(service_module),
        "DecisionRepository",
        lambda _session: decision_repository,
    )
    monkeypatch.setitem(
        vars(service_module),
        "DeploymentRepository",
        lambda _session: deployment_repository,
    )

    return (
        request_repository,
        decision_repository,
        deployment_repository,
    )


def install_auth_service(
        service_module: Any,
        monkeypatch: pytest.MonkeyPatch,
        auth_service: MagicMock,
) -> None:
    """安装运行时认证服务替身"""
    monkeypatch.setitem(
        vars(service_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(service_module),
        "create_auth_service",
        lambda **_kwargs: auth_service,
    )


def test_auth_endpoints_use_top_level_request_schemas(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证端点使用顶层请求数据结构"""
    service_module = load_service_module(
        monkeypatch
    )
    apis = (
        service_module
        .DatamindRuntimeService
        .apis
    )

    assert apis["login"].route == "/auth/login"
    assert set(
        apis["login"].input_spec.model_fields
    ) == {
        "username",
        "password",
    }
    assert apis["refresh"].route == "/auth/refresh"
    assert set(
        apis["refresh"].input_spec.model_fields
    ) == {
        "refresh_token",
    }
    assert apis["logout"].route == "/auth/logout"
    assert set(
        apis["logout"].input_spec.model_fields
    ) == {
        "refresh_token",
    }


@pytest.mark.asyncio
async def test_login_returns_tokens_without_cache(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地登录签发不缓存的令牌响应"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=1800,
        )
    )
    install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("secret"),
        ctx=context,
    )

    assert result == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "expires_in": 1800,
    }
    assert context.response.status_code == 200
    assert context.response.headers[
        "cache-control"
    ] == "no-store"
    assert context.response.headers[
        "pragma"
    ] == "no-cache"
    awaited_call = auth_service.login.await_args
    assert awaited_call is not None
    login_request = awaited_call.args[0]
    assert login_request.username == "alice"
    assert (
        login_request.password.get_secret_value()
        == "secret"
    )
    assert awaited_call.kwargs == {
        "ip": "127.0.0.1",
        "user_agent": "pytest",
    }


@pytest.mark.asyncio
async def test_login_hides_authentication_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录失败不暴露账户状态"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.login = AsyncMock(
        side_effect=InvalidCredentialsError()
    )
    install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("invalid"),
        ctx=context,
    )

    assert result == {
        "error": "用户名或密码错误"
    }
    assert context.response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新接口轮换访问令牌和刷新令牌"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        return_value=TokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=1800,
        )
    )
    install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = AuthContextStub()

    result = await runtime_service.refresh(
        refresh_token=SecretStr("refresh-token"),
        ctx=context,
    )

    assert result["access_token"] == "new-access-token"
    assert result["refresh_token"] == "new-refresh-token"
    awaited_call = auth_service.refresh.await_args
    assert awaited_call is not None
    refresh_request = awaited_call.args[0]
    assert (
        refresh_request.refresh_token.get_secret_value()
        == "refresh-token"
    )


@pytest.mark.asyncio
async def test_refresh_hides_invalid_token_details(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试刷新失败返回统一认证错误"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.refresh = AsyncMock(
        side_effect=InvalidRefreshTokenError()
    )
    install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = AuthContextStub()

    result = await runtime_service.refresh(
        refresh_token=SecretStr("invalid"),
        ctx=context,
    )

    assert result == {
        "error": "刷新令牌无效或已失效"
    }
    assert context.response.status_code == 401


@pytest.mark.asyncio
async def test_logout_is_idempotent(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退出接口幂等撤销刷新令牌"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    auth_service = MagicMock()
    auth_service.logout = AsyncMock(
        return_value=False
    )
    install_auth_service(
        service_module,
        monkeypatch,
        auth_service,
    )
    context = AuthContextStub()

    result = await runtime_service.logout(
        refresh_token=SecretStr("refresh-token"),
        ctx=context,
    )

    assert result == {}
    assert context.response.status_code == 204
    auth_service.logout.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_reports_unavailable_auth_service(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试认证配置不可用时返回 HTTP 503"""
    service_module = load_service_module(
        monkeypatch
    )
    runtime_service = create_service(
        service_module
    )
    monkeypatch.setitem(
        vars(service_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(service_module),
        "create_auth_service",
        MagicMock(
            side_effect=AuthError()
        ),
    )
    context = AuthContextStub()

    result = await runtime_service.login(
        username="alice",
        password=SecretStr("secret"),
        ctx=context,
    )

    assert result == {
        "error": "认证服务暂不可用"
    }
    assert context.response.status_code == 503


def test_apply_response_status_maps_request_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试请求参数错误映射为 HTTP 400"""
    service_module = load_service_module(
        monkeypatch
    )
    service = create_service(
        service_module
    )
    context = SimpleNamespace(
        response=SimpleNamespace(
            status_code=200
        )
    )

    service._apply_response_status(
        ctx=context,
        response={
            "success": False,
            "error_type": "ValueError",
        },
    )

    assert context.response.status_code == 400


@pytest.mark.asyncio
async def test_predict_batch_records_each_request_and_decision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测记录每项请求和决策"""
    service_module = load_service_module(
        monkeypatch
    )
    service = create_service(
        service_module
    )
    runtime_service = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        predict_batch=MagicMock(return_value={
            "count": 2,
            "predictions": [
                {"score": 680.0},
                {"score": 720.0},
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
    monkeypatch.setitem(
        vars(service_module),
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service._predict_batch(
        request=service_module.BatchPredictRequest(
            deployment_id="dep_test",
            features_list=[
                {"age": 35},
                {"age": 45},
            ],
        ),
        batch_id="batch_test",
    )

    assert result["success"] is True
    assert result["request_ids"] == [
        "req_1",
        "req_2",
    ]
    assert result["decision_ids"] == [
        "dcs_1",
        "dcs_2",
    ]
    service._create_batch_request_records.assert_awaited_once()
    service._record_batch_success.assert_awaited_once()


def test_control_request_rejects_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制请求不接受客户端操作人"""
    service_module = load_service_module(
        monkeypatch
    )

    with pytest.raises(
            ValidationError,
            match="operator",
    ):
        service_module.ControlRequest(
            deployment_id="dep_test",
            operator="spoofed-user",
        )


@pytest.mark.asyncio
async def test_submit_outcome_calls_feedback_service(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试结果回流接口调用业务服务"""
    service_module = load_service_module(
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
    monkeypatch.setitem(
        vars(service_module),
        "OutcomeService",
        lambda: outcome_service,
    )
    request = service_module.OutcomeFeedbackRequest(
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


@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        ({"success": True}, 200),
        ({"success": False, "error_type": "ServiceDeploymentNotFoundError"}, 404),
        ({"success": False, "error_type": "ServiceEnvironmentMismatchError"}, 409),
        ({"success": False, "error_type": "RuntimeRouteError"}, 400),
        ({"success": False, "error_type": "ValueError"}, 400),
        ({"success": False, "error_type": "RuntimeError"}, 500),
        ({"success": False, "error_type": None}, 500),
    ],
)
def test_apply_response_status_maps_error_types(
        monkeypatch: pytest.MonkeyPatch,
        response: dict[str, Any],
        expected_status: int,
) -> None:
    """测试错误类型映射为对应 HTTP 状态"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    service._apply_response_status(
        ctx=context,
        response=response,
    )

    assert context.response.status_code == expected_status


@pytest.mark.asyncio
async def test_startup_reconciles_and_marks_worker_ready(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Worker 启动时首次协调并写入就绪标记"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    result = MagicMock()
    result.to_dict.return_value = {
        "checked": 1,
    }
    service.reconciler.reconcile_once.return_value = result
    write_marker = MagicMock()
    monkeypatch.setitem(
        vars(service_module),
        "_write_worker_ready_marker",
        write_marker,
    )

    await service.startup()

    service.reconciler.reconcile_once.assert_awaited_once()
    service.reconciler.start.assert_awaited_once()
    write_marker.assert_called_once_with(
        worker_id="worker_test",
        environment="testing",
    )


@pytest.mark.asyncio
async def test_shutdown_stops_models_and_clears_cache(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Worker 关闭时停止协调器、卸载模型并清理缓存"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service.manager.all.return_value = [
        SimpleNamespace(deployment_id="dep_1"),
        SimpleNamespace(deployment_id="dep_2"),
    ]
    service.manager.stop.side_effect = [
        None,
        RuntimeError("stop failed"),
    ]
    service_cache = get_service_cache(service)
    service_cache["dep_1"] = object()

    await service.shutdown()

    service.reconciler.stop.assert_awaited_once()
    assert service.manager.stop.await_count == 2
    assert service_cache == {}


def test_health_returns_worker_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试健康检查返回 Worker 当前状态"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service.manager.count.return_value = 2
    get_service_cache(service).update({
        "dep_1": object(),
        "dep_2": object(),
    })

    result = service.health()

    assert result == {
        "status": "ok",
        "worker_id": "worker_test",
        "environment": "testing",
        "reconciler_running": True,
        "runtime_count": 2,
        "service_cache_count": 2,
        "configured_workers": service_module.service_config.workers,
    }


@pytest.mark.asyncio
async def test_ready_returns_ready_when_database_is_available(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库和协调器可用时 Worker 就绪"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    monkeypatch.setitem(
        vars(service_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    result = await service.ready(context)

    assert result["status"] == "ready"
    assert result["database_ready"] is True
    assert context.response.status_code == 200
    assert FakeUnitOfWork.latest is not None
    FakeUnitOfWork.latest.session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_ready_returns_unavailable_when_database_fails(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库不可用时 Worker 返回未就绪"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)

    class FailingUnitOfWork(FakeUnitOfWork):
        """数据库查询失败的工作单元"""

        async def __aenter__(self) -> "FailingUnitOfWork":
            self.session.execute.side_effect = SQLAlchemyError(
                "database unavailable"
            )
            return self

    monkeypatch.setitem(
        vars(service_module),
        "UnitOfWork",
        FailingUnitOfWork,
    )
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    result = await service.ready(context)

    assert result["status"] == "not_ready"
    assert result["database_ready"] is False
    assert context.response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("successful", "expected_status", "expected_error"),
    [
        (True, "success", None),
        (False, "failed", "request failed"),
    ],
)
async def test_execute_secured_applies_status_and_records_audit(
        monkeypatch: pytest.MonkeyPatch,
        successful: bool,
        expected_status: str,
        expected_error: str | None,
) -> None:
    """测试认证执行包装设置状态并记录审计"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service.security = SecurityStub()
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )
    handler = AsyncMock(return_value={
        "success": successful,
        "error": "request failed" if not successful else None,
        "error_type": "ValueError" if not successful else None,
    })

    result = await service._execute_secured(
        ctx=context,
        permission="runtime.manage",
        request_id="req_test",
        handler=handler,
        audit_action="runtime.load",
        target_type="deployment",
        target_id="dep_test",
    )

    assert result["success"] is successful
    handler.assert_awaited_once()
    get_audit_recorder(service).record.assert_awaited_once_with(
        action="runtime.load",
        target_type="deployment",
        target_id="dep_test",
        status=expected_status,
        error=expected_error,
        after=result if successful else None,
    )
    assert context.response.status_code == (
        200 if successful else 400
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "load",
        "unload",
        "reload",
    ],
)
async def test_control_operation_updates_desired_state(
        monkeypatch: pytest.MonkeyPatch,
        action: str,
) -> None:
    """测试运行控制操作更新期望状态"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service._validate_service_environment = AsyncMock()
    controller_method = getattr(service.controller, action)
    controller_method.return_value = {
        "deployment_id": "dep_test",
        "action": action,
    }
    operation = getattr(service, f"_{action}")

    result = await operation(
        request=service_module.ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is True
    assert result["action"] == action
    controller_method.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="alice",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "load",
        "unload",
        "reload",
    ],
)
async def test_control_operation_returns_validation_error(
        monkeypatch: pytest.MonkeyPatch,
        action: str,
) -> None:
    """测试运行控制校验失败时返回标准错误响应"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service._validate_service_environment = AsyncMock(
        side_effect=RuntimeRouteError("部署不可用")
    )
    operation = getattr(service, f"_{action}")

    result = await operation(
        request=service_module.ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is False
    assert result["error_type"] == "RuntimeRouteError"
    getattr(service.controller, action).assert_not_awaited()


@pytest.mark.asyncio
async def test_status_combines_control_and_local_state(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试部署状态查询合并控制、运行记录和本地状态"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service.controller.get_status.return_value = {
        "control": {"desired_status": "loaded"},
        "runtimes": [{"worker_id": "worker_test"}],
    }
    service.manager.status.return_value = {
        "loaded_in_memory": True,
    }
    service.reconciler.get_applied_generation.return_value = 3

    result = await service._status(
        request=service_module.DeploymentRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
    )

    assert result["success"] is True
    assert result["control"] == {
        "desired_status": "loaded"
    }
    assert result["local_generation"] == 3


@pytest.mark.asyncio
async def test_services_returns_cached_service_information(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务列表返回运行时和缓存信息"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    runtime_service = MagicMock()
    runtime_service.deployment_id = "dep_test"
    runtime_service.model_id = "mdl_test"
    runtime_service.version_id = "ver_test"
    runtime_service.framework = "sklearn"
    runtime_service.SERVICE_TYPE = "scoring"
    runtime_service.get_capability_names.return_value = [
        "PREDICT_PROBA"
    ]
    get_service_cache(service)[
        "dep_test"
    ] = service_module.ServiceCacheEntry(
        service=runtime_service,
        generation=1,
        runtime_identity=100,
    )
    service.manager.count.return_value = 1
    service.manager.to_dicts.return_value = [
        {"deployment_id": "dep_test"}
    ]
    service.reconciler.get_applied_generations.return_value = {
        "dep_test": 1
    }

    result = await service._services()

    assert result["runtime_count"] == 1
    assert result["service_cache_count"] == 1
    assert result["services"] == [{
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "service_type": "scoring",
        "capabilities": ["PREDICT_PROBA"],
    }]


@pytest.mark.asyncio
async def test_predict_records_successful_decision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测创建请求并记录成功决策"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    route = service_module.RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="deployment",
        strategy="fallback",
    )
    runtime_service = MagicMock()
    runtime_service.predict.return_value = {
        "score": 720.0,
        "probability": 0.8,
    }
    service._create_request_record = AsyncMock()
    service.router.resolve.return_value = route
    service._get_service = AsyncMock(
        return_value=runtime_service
    )
    service._record_prediction_success = AsyncMock()
    service._mark_prediction_failed = AsyncMock()
    monkeypatch.setitem(
        vars(service_module),
        "generate_random_id",
        lambda **_kwargs: "dcs_test",
    )
    request = service_module.PredictRequest(
        model_id="mdl_test",
        features={"age": 35},
    )

    result = await service._predict(
        request=request,
        request_id="req_test",
    )

    assert result["success"] is True
    assert result["decision_id"] == "dcs_test"
    assert result["score"] == 720.0
    assert result["route"] == {
        "source": "deployment",
        "strategy": "fallback",
        "routing_id": None,
        "experiment_id": None,
        "variant_id": None,
        "assignment_id": None,
    }
    service._create_request_record.assert_awaited_once()
    service._record_prediction_success.assert_awaited_once()
    service._mark_prediction_failed.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_source", "error"),
    [
        ("route", RuntimeRouteError("没有可用部署")),
        ("prediction", OSError("model unavailable")),
    ],
)
async def test_predict_returns_error_and_marks_request_failed(
        monkeypatch: pytest.MonkeyPatch,
        failure_source: str,
        error: Exception,
) -> None:
    """测试预测失败时返回标准错误并标记请求"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service._create_request_record = AsyncMock()
    service._mark_prediction_failed = AsyncMock()
    route = service_module.RouteResult(
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
        service.router.resolve.return_value = route
        runtime_service = MagicMock()
        runtime_service.predict.side_effect = error
        service._get_service = AsyncMock(
            return_value=runtime_service
        )

    result = await service._predict(
        request=service_module.PredictRequest(
            model_id="mdl_test",
            features={"age": 35},
        ),
        request_id="req_test",
    )

    assert result["success"] is False
    assert result["decision_id"] is None
    assert result["error_type"] == error.__class__.__name__
    service._mark_prediction_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_predict_batch_rejects_mismatched_result_count(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量预测拒绝数量不匹配的结果"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
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
    monkeypatch.setitem(
        vars(service_module),
        "generate_random_id",
        lambda **_kwargs: next(identifiers),
    )

    result = await service._predict_batch(
        request=service_module.BatchPredictRequest(
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
async def test_create_batch_request_records(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量请求记录包含批次索引和调用上下文"""
    service_module = load_service_module(monkeypatch)
    request_repo, _, _ = install_repositories(
        service_module,
        monkeypatch,
    )
    monkeypatch.setitem(
        vars(service_module),
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
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理更新请求并创建决策"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    decision_repo = MagicMock()
    install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
        decision_repo=decision_repo,
    )
    route = service_module.RouteResult(
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
        }],
        latency_ms=10.0,
    )

    request_repo.mark_success.assert_called_once_with(
        request_record,
        response={
            "success": True,
            "request_id": "req_1",
            "decision_id": "dcs_1",
            "batch_id": "batch_test",
            "batch_index": 0,
            "probability": "0.8",
            "score": 720,
            "decision": "approved",
        },
        latency_ms=10.0,
    )
    assert decision_repo.create_decision.call_args.kwargs[
        "probability"
    ] == 0.8
    assert decision_repo.create_decision.call_args.kwargs[
        "decision"
    ] == "approved"


@pytest.mark.asyncio
async def test_record_batch_success_requires_request_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量成功处理要求原始请求记录存在"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(return_value=None)
    install_repositories(
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
            route=service_module.RouteResult(
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
async def test_mark_batch_failed_updates_existing_records(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量失败处理只更新存在的请求记录"""
    service_module = load_service_module(monkeypatch)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        side_effect=[request_record, None]
    )
    install_repositories(
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

    request_repo.mark_failed.assert_called_once_with(
        request_record,
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )


@pytest.mark.asyncio
async def test_create_and_mark_single_request_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建请求记录并更新失败状态"""
    service_module = load_service_module(monkeypatch)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
    )
    monkeypatch.setitem(
        vars(service_module),
        "get_context",
        lambda: {
            "user": "alice",
            "ip": "127.0.0.1",
        },
    )
    service_class = service_module.DatamindRuntimeService.inner

    await service_class._create_request_record(
        request_id="req_test",
        model_id="mdl_test",
        payload={"features": {"age": 35}},
    )
    await service_class._mark_request_failed(
        request_id="req_test",
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )

    request_repo.create_request.assert_called_once()
    request_repo.mark_failed.assert_called_once_with(
        request_record,
        error="prediction failed",
        response={
            "success": False,
            "error": "prediction failed",
        },
        latency_ms=10.0,
    )


@pytest.mark.asyncio
async def test_record_prediction_success_creates_decision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条预测成功时更新请求并创建决策"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    request_record = object()
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(
        return_value=request_record
    )
    decision_repo = MagicMock()
    install_repositories(
        service_module,
        monkeypatch,
        request_repo=request_repo,
        decision_repo=decision_repo,
    )
    route = service_module.RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="testing",
        source="deployment",
        strategy="fallback",
        subject_key="customer_10001",
    )

    await service._record_prediction_success(
        request_id="req_test",
        decision_id="dcs_test",
        route=route,
        result={
            "deployment_id": "dep_test",
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "framework": "sklearn",
            "service_type": "scoring",
            "probability": "0.8",
            "score": 720,
            "decision": "approved",
        },
        response={
            "success": True,
            "request_id": "req_test",
            "decision_id": "dcs_test",
            "score": 720,
        },
        latency_ms=10.0,
    )

    request_repo.mark_success.assert_called_once_with(
        request_record,
        response={
            "success": True,
            "request_id": "req_test",
            "decision_id": "dcs_test",
            "score": 720,
        },
        latency_ms=10.0,
    )
    decision = decision_repo.create_decision.call_args.kwargs
    assert decision["prediction"] == {
        "service_type": "scoring",
        "probability": "0.8",
        "score": 720,
        "decision": "approved",
    }
    assert decision["probability"] == 0.8
    assert decision["score"] == 720.0
    assert decision["context"] == {
        "framework": "sklearn",
        "environment": "testing",
        "worker_id": "worker_test",
    }


@pytest.mark.asyncio
async def test_record_prediction_success_requires_request_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条成功处理要求请求记录存在"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    request_repo = MagicMock()
    request_repo.get_request = AsyncMock(return_value=None)
    install_repositories(
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
            route=service_module.RouteResult(
                model_id="mdl_test",
                version_id="ver_test",
                deployment_id="dep_test",
                framework="sklearn",
                environment="testing",
                source="deployment",
                strategy="fallback",
            ),
            result={},
            response={
                "success": True,
            },
            latency_ms=10.0,
        )


@pytest.mark.asyncio
async def test_mark_prediction_failed_handles_persistence_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录预测失败异常不会覆盖原始错误"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
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
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试决策负载过滤和可选值安全转换"""
    service_module = load_service_module(monkeypatch)
    service_class = service_module.DatamindRuntimeService.inner
    request = service_module.PredictRequest(
        model_id="mdl_test",
        deployment_id="dep_test",
        subject_key="customer_10001",
        subject_type="customer",
        features={"age": 35},
    )

    assert service_class._build_request_payload(request) == {
        "model_id": "mdl_test",
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
async def test_get_service_reconciles_and_caches_runtime_service(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地模型收敛后创建并缓存运行时服务"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    runtime_model = object()
    service.manager.get.side_effect = [
        None,
        runtime_model,
        runtime_model,
    ]
    service.reconciler.get_applied_generation.return_value = 2
    runtime_service = MagicMock()
    runtime_service.SERVICE_TYPE = "scoring"
    factory = MagicMock(return_value=runtime_service)
    monkeypatch.setitem(
        vars(service_module),
        "RuntimeServiceFactory",
        SimpleNamespace(create=factory),
    )

    first = await service._get_service("dep_test")
    second = await service._get_service("dep_test")

    assert first is runtime_service
    assert second is runtime_service
    service.reconciler.reconcile_once.assert_awaited_once()
    factory.assert_called_once_with(
        runtime_model=runtime_model
    )


@pytest.mark.asyncio
async def test_get_service_rejects_unloaded_runtime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试状态收敛后仍未加载模型时拒绝服务"""
    service_module = load_service_module(monkeypatch)
    service = create_service(service_module)
    service.manager.get.return_value = None
    service_cache = get_service_cache(service)
    service_cache["dep_test"] = object()

    with pytest.raises(
            RuntimeError,
            match="当前 Worker 尚未加载部署模型",
    ):
        await service._get_service("dep_test")

    assert "dep_test" not in service_cache


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment", "error_type"),
    [
        (None, "ServiceDeploymentNotFoundError"),
        (
            SimpleNamespace(
                environment="production",
                status="active",
            ),
            "ServiceEnvironmentMismatchError",
        ),
        (
            SimpleNamespace(
                environment="testing",
                status="inactive",
            ),
            "RuntimeRouteError",
        ),
    ],
)
async def test_validate_service_environment_rejects_invalid_deployment(
        monkeypatch: pytest.MonkeyPatch,
        deployment: SimpleNamespace | None,
        error_type: str,
) -> None:
    """测试服务环境校验拒绝无效部署"""
    service_module = load_service_module(monkeypatch)
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=deployment
    )
    install_repositories(
        service_module,
        monkeypatch,
        deployment_repo=deployment_repo,
    )

    with pytest.raises(
            getattr(service_module, error_type),
    ):
        await service_module.DatamindRuntimeService.inner._validate_service_environment(
            deployment_id="dep_test"
        )


@pytest.mark.asyncio
async def test_validate_service_environment_accepts_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务环境校验接受当前环境的活跃部署"""
    service_module = load_service_module(monkeypatch)
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            environment="testing",
            status="active",
        )
    )
    install_repositories(
        service_module,
        monkeypatch,
        deployment_repo=deployment_repo,
    )

    await service_module.DatamindRuntimeService.inner._validate_service_environment(
        deployment_id="dep_test"
    )

    deployment_repo.get_deployment.assert_awaited_once_with(
        "dep_test"
    )
