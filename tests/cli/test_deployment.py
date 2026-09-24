"""部署 CLI 测试.

验证部署命令能够将业务异常转换为清晰的命令行提示。

核心功能：
  - test_deployment_mutation_reports_business_error:
    验证部署状态变更命令处理业务异常
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

import pytest
import typer

from datamind.models.errors import (
    DeploymentNotFoundError,
    InvalidModelStateError,
)


disable_module = importlib.import_module(
    "datamind.cli.deployment.disable"
)
enable_module = importlib.import_module(
    "datamind.cli.deployment.enable"
)
create_module = importlib.import_module(
    "datamind.cli.deployment.create"
)


@asynccontextmanager
async def fake_cli_context(
        **_kwargs: object,
) -> AsyncIterator[SimpleNamespace]:
    """创建已认证的 CLI 上下文替身."""
    yield SimpleNamespace(
        user="alice"
    )


def configure_deployment_module(
        monkeypatch: pytest.MonkeyPatch,
        module: ModuleType,
        service: MagicMock,
) -> MagicMock:
    """配置部署命令依赖."""
    console = MagicMock()
    monkeypatch.setitem(
        vars(module),
        "DeploymentLifecycleService",
        lambda: service,
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
        "error",
        "message",
    ),
    [
        (
            enable_module,
            "enable_deployment",
            "enable_deployment",
            InvalidModelStateError(
                "版本已归档，不允许部署"
            ),
            "部署启用失败：版本已归档，不允许部署",
        ),
        (
            disable_module,
            "disable_deployment",
            "disable_deployment",
            DeploymentNotFoundError(
                "部署不存在: dep_test"
            ),
            "部署禁用失败：部署不存在: dep_test",
        ),
    ],
)
def test_deployment_mutation_reports_business_error(
        monkeypatch: pytest.MonkeyPatch,
        module: ModuleType,
        command_name: str,
        service_method: str,
        error: Exception,
        message: str,
) -> None:
    """测试部署状态变更命令处理业务异常."""
    service = MagicMock()
    method = AsyncMock(
        side_effect=error
    )
    setattr(
        service,
        service_method,
        method,
    )
    console = configure_deployment_module(
        monkeypatch,
        module,
        service,
    )

    with pytest.raises(
            typer.Exit,
    ) as raised:
        getattr(
            module,
            command_name,
        )(
            deployment_id="dep_test",
            output="text",
        )

    assert raised.value.exit_code == 1
    method.assert_awaited_once_with(
        deployment_id="dep_test",
        updated_by="alice",
    )
    console.error.assert_called_once_with(
        message,
        output_format="text",
        error_type=type(error).__name__,
    )


def test_deployment_create_rejects_invalid_release_role_before_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建命令在认证和数据库访问前拒绝非法发布角色组合."""
    service_config = SimpleNamespace(
        environment="development",
    )
    monkeypatch.setitem(
        vars(create_module),
        "get_service_config",
        lambda: service_config,
    )

    def unexpected_context(**_kwargs: object) -> None:
        raise AssertionError("非法参数不应进入 CLI 上下文")

    monkeypatch.setitem(
        vars(create_module),
        "cli_context",
        unexpected_context,
    )

    with pytest.raises(
            typer.BadParameter,
            match="全量发布自动使用 champion，无需指定 --role",
    ):
        create_module.create_deployment(
            name="scorecard",
            model_id=None,
            version="1.0.0",
            version_id=None,
            rollout="full",
            role="challenger",
            threshold=None,
            description=None,
            output="text",
        )


@pytest.mark.parametrize(
    ("rollout", "role", "expected"),
    [
        ("full", None, ("full", "champion")),
        ("shadow", None, ("shadow", "shadow")),
        ("canary", "champion", ("canary", "champion")),
        (" CANARY ", " CHALLENGER ", ("canary", "challenger")),
    ],
)
def test_resolve_release_options(
        rollout: str,
        role: str | None,
        expected: tuple[str, str],
) -> None:
    """测试 CLI 自动推导固定角色并规范化金丝雀角色."""
    assert create_module._resolve_release_options(
        rollout=rollout,
        role=role,
    ) == expected


def test_canary_deployment_requires_explicit_role() -> None:
    """测试金丝雀发布必须明确选择部署角色."""
    with pytest.raises(
            typer.BadParameter,
            match="金丝雀发布必须指定 --role",
    ):
        create_module._resolve_release_options(
            rollout="canary",
            role=None,
        )
