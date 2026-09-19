"""路由 CLI 测试

验证路由列表和详情的输出契约。

核心功能：
  - test_route_list_filters_and_displays_current_deployment_release:
    验证路由列表筛选并展示当前部署发布信息
  - test_route_show_displays_current_deployment_release:
    验证路由详情展示当前部署发布信息
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import importlib
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.constants import Environment


list_module = importlib.import_module(
    "datamind.cli.route.list"
)
show_module = importlib.import_module(
    "datamind.cli.route.show"
)


class FakeUnitOfWork:
    """路由命令测试工作单元。"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


@asynccontextmanager
async def fake_cli_context(
        **_kwargs: object,
) -> AsyncIterator[SimpleNamespace]:
    """创建已认证的 CLI 上下文替身。"""
    yield SimpleNamespace(user="alice")


def create_route() -> SimpleNamespace:
    """创建带旧发布快照的路由。"""
    return SimpleNamespace(
        routing_id="rtn_test",
        name="scorecard-route",
        deployment_id="dep_test",
        environment="production",
        rollout_type="full",
        rollout_group="champion",
        enabled=True,
        traffic_ratio=0.2,
        rules=None,
        description=None,
        created_by="alice",
        updated_by="alice",
        created_at=None,
        updated_at=None,
        deleted_at=None,
        deleted_by=None,
        deletion_reason=None,
    )


def create_deployment() -> SimpleNamespace:
    """创建包含当前发布信息的部署。"""
    return SimpleNamespace(
        deployment_id="dep_test",
        environment="development",
        rollout_type="canary",
        role="challenger",
    )


def configure_module(
        monkeypatch: pytest.MonkeyPatch,
        module: object,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """配置路由命令依赖。"""
    routing_repo = MagicMock()
    routing_repo.get_routing = AsyncMock(
        return_value=create_route()
    )
    routing_repo.list_routings = AsyncMock(
        return_value=[create_route()]
    )
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=create_deployment()
    )
    console = MagicMock()
    namespace = vars(module)
    monkeypatch.setitem(namespace, "UnitOfWork", FakeUnitOfWork)
    monkeypatch.setitem(
        namespace,
        "RoutingRepository",
        lambda _session: routing_repo,
    )
    monkeypatch.setitem(
        namespace,
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(namespace, "cli_context", fake_cli_context)
    monkeypatch.setitem(namespace, "console", console)

    if module is list_module:
        monkeypatch.setitem(
            namespace,
            "get_service_config",
            lambda: SimpleNamespace(
                environment=Environment.DEVELOPMENT
            ),
        )

    return routing_repo, deployment_repo, console


def printed_json(console: MagicMock) -> Any:
    """读取命令输出的 JSON。"""
    payload = console.print_json.call_args.args[0]
    return json.loads(payload)


def test_route_list_filters_and_displays_current_deployment_release(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由列表按部署筛选并显示部署当前发布信息"""
    routing_repo, deployment_repo, console = configure_module(
        monkeypatch,
        list_module,
    )

    list_module.list_routes(
        name=None,
        deployment_id=None,
        rollout="canary",
        rollout_group="challenger",
        enabled=None,
        created_by=None,
        include_deleted=False,
        limit=10,
        offset=0,
        output="json",
    )

    routing_repo.list_routings.assert_awaited_once_with(
        name=None,
        include_deleted=False,
        limit=10,
        offset=0,
        deployment_id=None,
        environment=Environment.DEVELOPMENT,
        rollout_type="canary",
        rollout_group="challenger",
        enabled=None,
        created_by=None,
    )
    deployment_repo.get_deployment.assert_awaited_once_with(
        "dep_test",
        include_deleted=True,
    )
    result = printed_json(console)[0]
    assert result["environment"] == "development"
    assert result["rollout_type"] == "canary"
    assert result["rollout_group"] == "challenger"


def test_route_show_displays_current_deployment_release(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由详情忽略旧快照并显示部署当前发布信息"""
    _, deployment_repo, console = configure_module(
        monkeypatch,
        show_module,
    )

    show_module.show_route(
        routing_id="rtn_test",
        include_deleted=False,
        output="json",
    )

    deployment_repo.get_deployment.assert_awaited_once_with(
        "dep_test",
        include_deleted=True,
    )
    result = printed_json(console)
    assert result["environment"] == "development"
    assert result["rollout_type"] == "canary"
    assert result["rollout_group"] == "challenger"
