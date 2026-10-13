"""运行实例查询 CLI 测试.

验证运行实例查询命令能够将业务异常转换为清晰提示。

核心功能：
  - test_runtime_query_reports_business_error:
    验证运行状态查询命令处理业务异常
  - test_runtime_show_json_preserves_applied_generation:
    验证运行状态 JSON 输出保留实际应用的控制代次
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import (
    ModuleType,
    SimpleNamespace,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)
import importlib
import json

import pytest
import typer

from datamind.models.errors import (
    DeploymentNotFoundError,
)


list_module = importlib.import_module(
    "datamind.cli.runtime.list"
)
show_module = importlib.import_module(
    "datamind.cli.runtime.show"
)


@asynccontextmanager
async def fake_cli_context(
        **_kwargs: object,
) -> AsyncIterator[SimpleNamespace]:
    """创建已认证的 CLI 上下文替身."""
    yield SimpleNamespace(
        user="alice"
    )


def configure_runtime_module(
        monkeypatch: pytest.MonkeyPatch,
        module: ModuleType,
        controller: MagicMock,
) -> MagicMock:
    """配置运行状态命令依赖."""
    console = MagicMock()
    monkeypatch.setitem(
        vars(module),
        "RuntimeControlService",
        lambda: controller,
    )
    monkeypatch.setitem(
        vars(module),
        "cli_context",
        fake_cli_context,
    )
    monkeypatch.setitem(
        vars(module),
        "console",
        console,
    )

    if "audit" in vars(module):
        monkeypatch.setitem(
            vars(module),
            "audit",
            lambda **_kwargs: lambda function: function,
        )

    return console


@pytest.mark.parametrize(
    (
        "module",
        "command_name",
        "service_method",
        "arguments",
        "error",
    ),
    [
        (
            show_module,
            "show_runtime",
            "get_status",
            {
                "deployment_id": "dep_test",
                "output": "text",
            },
            DeploymentNotFoundError(
                "部署不存在: dep_test"
            ),
        ),
        (
            list_module,
            "list_runtimes",
            "list_services",
            {
                "desired_status": None,
                "limit": 10,
                "offset": 0,
                "output": "text",
            },
            ValueError(
                "运行环境配置无效"
            ),
        ),
    ],
)
def test_runtime_query_reports_business_error(
        monkeypatch: pytest.MonkeyPatch,
        module: ModuleType,
        command_name: str,
        service_method: str,
        arguments: dict[str, object],
        error: Exception,
) -> None:
    """测试运行状态查询命令处理业务异常."""
    controller = MagicMock()
    method = AsyncMock(
        side_effect=error
    )
    setattr(
        controller,
        service_method,
        method,
    )
    console = configure_runtime_module(
        monkeypatch,
        module,
        controller,
    )

    with pytest.raises(
            typer.Exit,
    ) as raised:
        getattr(
            module,
            command_name,
        )(**arguments)

    assert raised.value.exit_code == 1
    console.error.assert_called_once_with(
        f"运行状态查询失败：{error}",
        output_format="text",
        error_type=type(error).__name__,
    )


def test_runtime_show_json_preserves_applied_generation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行状态 JSON 输出保留实际应用的控制代次."""
    controller = MagicMock()
    controller.get_status = AsyncMock(
        return_value={
            "deployment": {
                "deployment_id": "dep_test",
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "framework": "sklearn",
                "environment": "production",
                "rollout_type": "full",
                "role": "champion",
                "status": "active",
            },
            "control": None,
            "runtimes": [
                {
                    "runtime_id": "run_test",
                    "deployment_id": "dep_test",
                    "model_id": "mdl_test",
                    "version_id": "ver_test",
                    "framework": "sklearn",
                    "status": "running",
                    "worker_id": "worker_test",
                    "applied_generation": None,
                    "loaded_at": None,
                    "unloaded_at": None,
                    "last_heartbeat_at": None,
                    "error": None,
                    "context": None,
                }
            ],
        }
    )
    console = configure_runtime_module(
        monkeypatch,
        show_module,
        controller,
    )

    show_module.show_runtime(
        deployment_id="dep_test",
        output="json",
    )

    rendered = json.loads(
        console.print_json.call_args.args[0]
    )
    assert rendered["runtimes"][0]["applied_generation"] is None
