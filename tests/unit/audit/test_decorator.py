"""审计装饰器测试.

验证装饰器参数校验、目标 ID 解析、成功和失败审计以及故障隔离。

核心功能：
  - test_audit_rejects_invalid_action:
    验证操作名称格式校验
  - test_audit_requires_target_id_source:
    验证目标 ID 来源约束
  - test_success_records_target_id_from_parameter:
    验证成功操作审计
  - test_business_error_records_failure_and_reraises:
    验证失败操作审计
  - test_record_failure_does_not_mask_business_error:
    验证故障隔离
  - test_audit_preserves_function_metadata:
    验证装饰后函数元数据
"""

from typing import Any

import pytest

from datamind.audit import decorator as decorator_module
from datamind.audit.decorator import audit
from datamind.audit.errors import AuditValidationError
from datamind.audit.policy import AuditFailureMode


class RecordingRecorder:
    """记录审计调用的测试 Recorder."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        record_error: Exception | None = None,
    ) -> None:
        self.enabled = enabled
        self.record_error = record_error
        self.records: list[dict[str, Any]] = []

    @property
    def failure_mode(self) -> AuditFailureMode:
        """返回默认失败策略."""
        return AuditFailureMode.OPEN

    async def record(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        status: str = "success",
        error: str | None = None,
        before: Any | None = None,
        after: Any | None = None,
        context: dict[str, Any] | None = None,
        failure_mode: AuditFailureMode | None = None,
    ) -> None:
        """保存审计调用并按配置模拟异常."""
        record = {
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "status": status,
                "error": error,
                "before": before,
                "after": after,
                "context": context,
            }

        if failure_mode is AuditFailureMode.CLOSED:
            record["failure_mode"] = failure_mode

        self.records.append(
            record
        )

        if self.record_error is not None:
            raise self.record_error


class RecordingLogger:
    """记录错误日志的测试 Logger."""

    def __init__(self) -> None:
        self.error_records: list[tuple[str, dict[str, Any]]] = []

    def error(
        self,
        message: str,
        **values: Any,
    ) -> None:
        """保存错误日志."""
        self.error_records.append(
            (
                message,
                values,
            )
        )


def install_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    record_error: Exception | None = None,
) -> RecordingRecorder:
    """替换装饰器创建的 AuditRecorder."""
    recorder = RecordingRecorder(
        enabled=enabled,
        record_error=record_error,
    )

    monkeypatch.setitem(
        vars(decorator_module),
        "AuditRecorder",
        lambda: recorder,
    )

    return recorder


def install_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> RecordingLogger:
    """替换装饰器使用的结构化 Logger."""
    logger = RecordingLogger()

    monkeypatch.setattr(
        decorator_module,
        "logger",
        logger,
    )

    return logger


@pytest.mark.parametrize(
    (
        "action",
        "error_message",
    ),
    [
        (
            "",
            "action 不能为空",
        ),
        (
            "   ",
            "action 不能为空",
        ),
        (
            "register",
            "action 必须采用 resource.operation 格式",
        ),
        (
            ".register",
            "action 必须采用 resource.operation 格式",
        ),
        (
            "model.",
            "action 必须采用 resource.operation 格式",
        ),
    ],
)
def test_audit_rejects_invalid_action(
    action: str,
    error_message: str,
) -> None:
    """测试拒绝无效操作名称."""
    with pytest.raises(
        ValueError,
        match=error_message,
    ):
        audit(
            action=action,
            target_type="model",
            target_id_from="model_id",
        )


@pytest.mark.parametrize(
    "target_type",
    [
        "",
        "   ",
    ],
)
def test_audit_rejects_blank_target_type(
    target_type: str,
) -> None:
    """测试拒绝空目标类型."""
    with pytest.raises(
        ValueError,
        match="target_type 不能为空",
    ):
        audit(
            action="model.register",
            target_type=target_type,
            target_id_from="model_id",
        )


@pytest.mark.parametrize(
    "target_id_from",
    [
        "",
        "   ",
    ],
)
def test_audit_rejects_blank_target_id_from(
    target_id_from: str,
) -> None:
    """测试拒绝空目标 ID 参数名."""
    with pytest.raises(
        ValueError,
        match="target_id_from 不能为空字符串",
    ):
        audit(
            action="model.register",
            target_type="model",
            target_id_from=target_id_from,
        )


def test_audit_requires_target_id_source() -> None:
    """测试至少提供一种目标 ID 解析方式."""
    with pytest.raises(
        ValueError,
        match=(
            "target_id_from 和 target_id_func "
            "至少需要提供一个"
        ),
    ):
        audit(
            action="model.register",
            target_type="model",
        )


def test_audit_rejects_synchronous_function() -> None:
    """测试装饰器拒绝同步函数."""

    def register_model(
        model_id: str,
    ) -> str:
        return model_id

    sync_callable: Any = register_model
    decorator = audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )

    with pytest.raises(
        TypeError,
        match="装饰器仅支持 async 函数：register_model",
    ):
        decorator(sync_callable)


def test_audit_rejects_missing_target_id_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标 ID 参数不在函数签名中时立即报错."""
    install_recorder(monkeypatch)

    with pytest.raises(
        ValueError,
        match="函数 register_model 不包含参数：model_id",
    ):

        @audit(
            action="model.register",
            target_type="model",
            target_id_from="model_id",
        )
        async def register_model(
            name: str,
        ) -> str:
            return name


@pytest.mark.asyncio
async def test_disabled_audit_executes_business_without_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试审计关闭时直接执行原函数."""
    recorder = install_recorder(
        monkeypatch,
        enabled=False,
    )
    calls: list[str] = []

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> str:
        calls.append(model_id)
        return "registered"

    result = await register_model(
        "mdl_0123456789abcdef"
    )

    assert result == "registered"
    assert calls == [
        "mdl_0123456789abcdef",
    ]
    assert recorder.records == []


@pytest.mark.asyncio
async def test_success_records_target_id_from_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试成功操作从参数解析并规范化目标 ID."""
    recorder = install_recorder(
        monkeypatch
    )
    result_value = {
        "name": "scorecard",
        "version": "1.0.0",
    }

    @audit(
        action=" model.register ",
        target_type=" model ",
        target_id_from=" model_id ",
    )
    async def register_model(
        model_id: str,
        name: str,
    ) -> dict[str, str]:
        assert model_id == " mdl_0123456789abcdef "
        assert name == "scorecard"
        return result_value

    result = await register_model(
        " mdl_0123456789abcdef ",
        "scorecard",
    )

    assert result is result_value
    assert recorder.records == [
        {
            "action": "model.register",
            "target_type": "model",
            "target_id": "mdl_0123456789abcdef",
            "status": "success",
            "error": None,
            "before": None,
            "after": result_value,
            "context": None,
        },
    ]


@pytest.mark.asyncio
async def test_empty_parameter_target_id_raises_before_business_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标 ID 参数为空时不执行业务函数."""
    recorder = install_recorder(
        monkeypatch
    )
    business_called = False

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> str:
        nonlocal business_called
        business_called = True
        return model_id

    with pytest.raises(
        AuditValidationError,
        match="缺少 target_id，参数 model_id 的值为空",
    ):
        await register_model("   ")

    assert business_called is False
    assert recorder.records == []


@pytest.mark.asyncio
async def test_non_string_parameter_target_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标 ID 参数必须是字符串."""
    recorder = install_recorder(
        monkeypatch
    )
    business_called = False

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: object,
    ) -> object:
        nonlocal business_called
        business_called = True
        return model_id

    with pytest.raises(
        AuditValidationError,
        match="target_id 必须是字符串",
    ):
        await register_model(1001)

    assert business_called is False
    assert recorder.records == []


@pytest.mark.asyncio
async def test_target_id_func_resolves_id_from_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过返回值解析目标 ID."""
    recorder = install_recorder(
        monkeypatch
    )
    resolver_calls: list[tuple[dict[str, Any], dict[str, str]]] = []

    def resolve_target_id(
        params: dict[str, Any],
        function_result: dict[str, str],
    ) -> str:
        resolver_calls.append(
            (
                params,
                function_result,
            )
        )
        return function_result["model_id"]

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=resolve_target_id,
    )
    async def register_model(
        name: str,
        version: str = "1.0.0",
    ) -> dict[str, str]:
        return {
            "model_id": "mdl_0123456789abcdef",
            "name": name,
            "version": version,
        }

    result = await register_model(
        "scorecard"
    )

    assert resolver_calls == [
        (
            {
                "name": "scorecard",
                "version": "1.0.0",
            },
            result,
        ),
    ]
    assert recorder.records[0]["target_id"] == "mdl_0123456789abcdef"
    assert recorder.records[0]["after"] is result


@pytest.mark.asyncio
async def test_target_id_func_params_exclude_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标 ID 解析参数排除实例 self."""
    recorder = install_recorder(
        monkeypatch
    )
    received_params: list[dict[str, Any]] = []

    def resolve_target_id(
        params: dict[str, Any],
        function_result: dict[str, str],
    ) -> str:
        received_params.append(params)
        return function_result["model_id"]

    class ModelService:
        """用于验证实例方法参数绑定的测试服务."""

        @audit(
            action="model.register",
            target_type="model",
            target_id_func=resolve_target_id,
        )
        async def register(
            self,
            name: str,
        ) -> dict[str, str]:
            return {
                "model_id": "mdl_0123456789abcdef",
                "name": name,
            }

    result = await ModelService().register(
        "scorecard"
    )

    assert result["model_id"] == "mdl_0123456789abcdef"
    assert received_params == [
        {
            "name": "scorecard",
        },
    ]
    assert recorder.records[0]["target_id"] == "mdl_0123456789abcdef"


@pytest.mark.asyncio
async def test_business_error_records_failure_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试业务异常记录失败审计并原样抛出."""
    recorder = install_recorder(
        monkeypatch
    )
    business_error = RuntimeError(
        "模型文件不存在"
    )

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> None:
        assert model_id == "mdl_0123456789abcdef"
        raise business_error

    with pytest.raises(RuntimeError) as exc_info:
        await register_model(
            "mdl_0123456789abcdef"
        )

    assert exc_info.value is business_error
    assert recorder.records == [
        {
            "action": "model.register",
            "target_type": "model",
            "target_id": "mdl_0123456789abcdef",
            "status": "failed",
            "error": "模型文件不存在",
            "before": None,
            "after": None,
            "context": None,
        },
    ]


@pytest.mark.asyncio
async def test_business_error_uses_unknown_target_for_result_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试业务失败且仅有结果解析器时使用未知目标 ID."""
    recorder = install_recorder(
        monkeypatch
    )
    resolver_called = False

    def resolve_target_id(
        _params: dict[str, Any],
        _result: object,
    ) -> str:
        nonlocal resolver_called
        resolver_called = True
        return "mdl_unused"

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=resolve_target_id,
    )
    async def register_model() -> None:
        raise ValueError(
            "注册失败"
        )

    with pytest.raises(
        ValueError,
        match="注册失败",
    ):
        await register_model()

    assert resolver_called is False
    assert recorder.records[0]["target_id"] == "model:unknown"
    assert recorder.records[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_record_failure_does_not_change_success_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试审计记录失败不影响成功业务结果."""
    audit_error = RuntimeError(
        "audit unavailable"
    )
    recorder = install_recorder(
        monkeypatch,
        record_error=audit_error,
    )
    logger = install_logger(
        monkeypatch
    )

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> str:
        return f"registered:{model_id}"

    result = await register_model(
        "mdl_0123456789abcdef"
    )

    assert result == "registered:mdl_0123456789abcdef"
    assert len(recorder.records) == 1
    assert logger.error_records == [
        (
            "审计事件记录失败",
            {
                "audit_error": "audit unavailable",
                "action": "model.register",
                "target_type": "model",
                "target_id": "mdl_0123456789abcdef",
                "status": "success",
                "exc_info": True,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_closed_mode_propagates_audit_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Fail-closed 模式阻止成功结果返回."""
    audit_error = RuntimeError(
        "audit unavailable"
    )
    install_recorder(
        monkeypatch,
        record_error=audit_error,
    )

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
        failure_mode=AuditFailureMode.CLOSED,
    )
    async def register_model(
            model_id: str,
    ) -> str:
        return model_id

    with pytest.raises(RuntimeError) as exc_info:
        await register_model(
            "mdl_0123456789abcdef"
        )

    assert exc_info.value is audit_error


@pytest.mark.asyncio
async def test_record_failure_does_not_mask_business_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试审计记录失败不覆盖原始业务异常."""
    business_error = RuntimeError(
        "business failure"
    )
    install_recorder(
        monkeypatch,
        record_error=RuntimeError(
            "audit failure"
        ),
    )
    logger = install_logger(
        monkeypatch
    )

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> None:
        assert model_id == "mdl_0123456789abcdef"
        raise business_error

    with pytest.raises(RuntimeError) as exc_info:
        await register_model(
            "mdl_0123456789abcdef"
        )

    assert exc_info.value is business_error
    assert logger.error_records[0][0] == "审计事件记录失败"
    assert logger.error_records[0][1]["status"] == "failed"
    assert logger.error_records[0][1]["audit_error"] == (
        "audit failure"
    )


@pytest.mark.asyncio
async def test_target_id_func_error_is_logged_without_changing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标 ID 解析异常只记录日志."""
    recorder = install_recorder(
        monkeypatch
    )
    logger = install_logger(
        monkeypatch
    )
    result_value = {
        "name": "scorecard",
    }

    def failing_resolver(
        _params: dict[str, Any],
        _result: dict[str, str],
    ) -> str:
        raise RuntimeError(
            "resolver failure"
        )

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=failing_resolver,
    )
    async def register_model() -> dict[str, str]:
        return result_value

    result = await register_model()

    assert result is result_value
    assert recorder.records == []
    assert logger.error_records == [
        (
            "审计目标 ID 解析失败",
            {
                "audit_error": "resolver failure",
                "action": "model.register",
                "target_type": "model",
                "function": "register_model",
                "exc_info": True,
            },
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resolved_target_id",
    [
        None,
        "   ",
    ],
)
async def test_blank_target_id_from_func_is_logged(
    monkeypatch: pytest.MonkeyPatch,
    resolved_target_id: str | None,
) -> None:
    """测试解析器返回空目标 ID 时记录日志并返回业务结果."""
    recorder = install_recorder(
        monkeypatch
    )
    logger = install_logger(
        monkeypatch
    )

    def resolve_blank_target_id(
        _params: dict[str, Any],
        _result: str,
    ) -> str | None:
        return resolved_target_id

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=resolve_blank_target_id,
    )
    async def register_model() -> str:
        return "registered"

    result = await register_model()

    assert result == "registered"
    assert recorder.records == []
    assert logger.error_records == [
        (
            "审计目标 ID 为空",
            {
                "action": "model.register",
                "target_type": "model",
                "function": "register_model",
            },
        ),
    ]


def test_audit_preserves_function_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 wraps 保留原函数名称和文档."""
    install_recorder(
        monkeypatch
    )

    @audit(
        action="model.register",
        target_type="model",
        target_id_from="model_id",
    )
    async def register_model(
        model_id: str,
    ) -> str:
        """注册模型."""
        return model_id

    assert register_model.__name__ == "register_model"
    assert register_model.__doc__ == "注册模型."
    assert hasattr(
        register_model,
        "__wrapped__",
    )
