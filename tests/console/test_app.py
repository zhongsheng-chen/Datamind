# tests/console/test_app.py

"""内网管理控制台应用测试

验证静态页面、浏览器登录 Cookie、会话认证和权限化概览接口。

核心功能：
  - test_console_page_is_available: 验证控制台页面可访问
  - test_overview_navigation_requires_request_access:
    验证概览导航遵循 API 调用查看权限
  - test_console_page_supports_realtime_details: 验证实时详情交互
  - test_session_requires_login: 验证会话接口要求登录
  - test_login_creates_http_only_session: 验证登录创建安全 Cookie
  - test_overview_uses_authenticated_permissions: 验证概览使用用户权限
  - test_section_uses_server_pagination: 验证控制台页面服务端分页
  - test_model_versions_uses_server_pagination: 验证模型版本服务端分页
  - test_experiment_variants_use_server_pagination: 验证实验分组服务端分页
  - test_section_export_streams_filtered_csv: 验证按查询条件导出 CSV
  - test_stream_events_starts_with_consistent_sync: 验证事件流一致性同步
  - test_stream_events_filters_topics_by_permission: 验证事件流权限过滤
  - test_event_query_waits_for_cleanup_when_cancelled:
    验证事件查询取消时等待数据库清理完成
"""

import asyncio
import importlib
import json
import re
from collections.abc import (
    AsyncIterator,
    Coroutine,
)
from contextlib import asynccontextmanager
from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)
from pydantic import (
    BaseModel,
    ValidationError,
)
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from datamind.auth.enums import UserStatus
from datamind.auth.schemas import (
    AuthenticatedUser,
    TokenResponse,
)
from datamind.audit.enums import AuditSource
from datamind.console.schemas import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
    ExperimentCreateRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    RoutingCreateRequest,
    UserCreateRequest,
)
from datamind.db.models.outbox import OutboxEvent


app_module = importlib.import_module(
    "datamind.console.app"
)
cookies_module = importlib.import_module(
    "datamind.console.cookies"
)


class FakeUnitOfWork:
    """控制台应用测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_user() -> AuthenticatedUser:
    """创建控制台测试用户"""
    return AuthenticatedUser(
        user_id="usr_alice",
        username="alice",
        display_name="Alice",
        email="alice@example.com",
        status=UserStatus.ACTIVE,
        roles=["developer"],
        permissions=["model.read"],
    )


def test_http_audit_context_generates_missing_identifiers(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台为缺失标识的 HTTP 审计补全上下文"""
    monkeypatch.setitem(
        vars(app_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_generated",
    )
    monkeypatch.setitem(
        vars(app_module),
        "generate_trace_id",
        lambda: "fedcba9876543210fedcba9876543210",
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_hostname",
        lambda: "console-host",
    )
    request = Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/api/deployments",
        "raw_path": b"/api/deployments",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    })

    context = app_module._http_audit_context(
        request,
        user=create_user(),
    )

    assert context == {
        "user": "alice",
        "source": AuditSource.HTTP,
        "ip": "127.0.0.1",
        "request_id": "req_generated",
        "trace_id": "fedcba9876543210fedcba9876543210",
        "hostname": "console-host",
    }


@pytest.mark.asyncio
async def test_model_registration_target_does_not_require_csrf(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试只读的模型注册检查不要求 CSRF 令牌"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.read",
                "model.write",
            ]
        }
    )
    repository = MagicMock()
    repository.get_model = AsyncMock(
        return_value=SimpleNamespace(
            model_id="mdl_scorecard",
            description="信用评分卡模型"
        )
    )
    version_repository = MagicMock()
    version_repository.list_versions = AsyncMock(
        return_value=[
            SimpleNamespace(
                version_id="ver_scorecard"
            )
        ]
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "MetadataRepository",
        lambda _session: repository,
    )
    monkeypatch.setitem(
        vars(app_module),
        "VersionRepository",
        lambda _session: version_repository,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/registration-target",
            params={
                "name": "scorecard",
                "version": "1.0.0",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "exists": True,
        "description": "信用评分卡模型",
        "version_exists": True,
    }
    repository.get_model.assert_awaited_once_with(
        name="scorecard"
    )
    version_repository.list_versions.assert_awaited_once_with(
        model_id="mdl_scorecard",
        version="1.0.0",
        include_archived=True,
        limit=1,
    )


def test_console_password_requests_accept_short_passwords() -> None:
    """测试控制台密码请求只要求密码非空"""
    created = UserCreateRequest(
        username="alice",
        password="x",
    )
    changed = PasswordChangeRequest(
        current_password="x",
        new_password="y",
    )
    reset = PasswordResetRequest(
        password="z",
    )

    assert created.password == "x"
    assert changed.new_password == "y"
    assert reset.password == "z"


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (
            DeploymentCreateRequest,
            {
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "environment": "development",
            },
        ),
        (
            DeploymentUpdateRequest,
            {
                "environment": "development",
            },
        ),
        (
            RoutingCreateRequest,
            {
                "deployment_id": "dep_test",
                "environment": "development",
            },
        ),
        (
            ExperimentCreateRequest,
            {
                "model_id": "mdl_test",
                "name": "experiment",
                "environment": "development",
            },
        ),
    ],
)
def test_environment_is_not_a_console_write_parameter(
        schema: type[BaseModel],
        payload: dict[str, object],
) -> None:
    """测试单环境控制台拒绝客户端指定资源环境。"""
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.asyncio
async def test_console_page_is_available() -> None:
    """测试控制台页面和本地静态资源可访问"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get("/")
        stylesheet = await client.get(
            "/assets/style.css"
        )
        script = await client.get(
            "/assets/app.js"
        )
        dashboard_script = await client.get(
            "/assets/dashboard.js"
        )
        resources_script = await client.get(
            "/assets/resources.js"
        )
        navigation_script = await client.get(
            "/assets/navigation.js"
        )
        presentation_script = await client.get(
            "/assets/presentation.js"
        )
        format_script = await client.get(
            "/assets/format.js"
        )
        management_script = await client.get(
            "/assets/management.js"
        )
        table_script = await client.get(
            "/assets/table.js"
        )
        health = await client.get(
            "/health"
        )

    script = SimpleNamespace(
        status_code=script.status_code,
        text="\n".join((
            script.text,
            dashboard_script.text,
            resources_script.text,
            navigation_script.text,
            presentation_script.text,
        )),
    )

    assert response.status_code == 200
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
    }
    assert "Datamind 管理控制台" in response.text
    assert "让服务的每一次变化，都清晰可见。" in response.text
    assert "登录控制台" in response.text
    assert "Powered by" in response.text
    assert "Zhongsheng Chen" in response.text
    assert 'id="account-menu-button"' in response.text
    assert 'id="account-menu"' in response.text
    assert 'id="account-management"' in response.text
    assert 'id="change-password-button"' in response.text
    assert "账户安全" in response.text
    assert "修改密码" in response.text
    assert 'data-account-section="users"' in response.text
    assert 'data-account-section="roles"' in response.text
    assert 'id="create-button"' in response.text
    assert 'id="account-menu-username"' in response.text
    assert 'id="account-role-list"' in response.text
    assert "退出登录" in response.text
    assert "正在建立实时连接" in response.text
    assert 'class="overview-metrics"' in response.text
    assert "API 调用趋势" in response.text
    assert 'id="trend-volume-total"' in response.text
    assert 'id="trend-failure-rate"' in response.text
    assert 'id="trend-range-selector"' in response.text
    assert 'data-trend-range="1h"' in response.text
    assert 'data-trend-range="24h"' in response.text
    assert 'data-trend-range="7d"' in response.text
    assert 'data-trend-range="30d"' in response.text
    assert "最近 24 小时 · 每 5 分钟聚合" in response.text
    assert "trend-tooltip" in script.text
    assert "trend-current-line" in script.text
    assert "近 24 小时模型调用" in response.text
    assert "累计调用排行" in response.text
    assert "调用量、成功率、平均耗时与流量占比" in response.text
    assert "各模型的历史调用规模" in response.text
    assert 'label: "近 24 小时 API 调用"' in script.text
    assert 'label: "累计 API 调用"' in script.text
    assert 'label: "近 24 小时成功率"' in script.text
    assert 'label: "近 24 小时 P95 耗时"' in script.text
    signed_percentage_formatter = format_script.text.split(
        "function formatSignedPercentage(value)",
        maxsplit=1,
    )[1].split(
        "function formatPercentage(value)",
        maxsplit=1,
    )[0]
    assert (
        'if (number > 0) return `+${formatted}`'
        in signed_percentage_formatter
    )
    assert ".overview-metric-card" in stylesheet.text
    sidebar_style = stylesheet.text.split(
        ".sidebar {",
        maxsplit=1,
    )[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "align-self: start" in sidebar_style
    assert "height: 100dvh" in sidebar_style
    assert "overflow: hidden" in sidebar_style
    normalized_stylesheet = stylesheet.text.replace("\r\n", "\n")
    assert ".navigation {\n  min-height: 0" in normalized_stylesheet
    assert "overflow-y: auto" in stylesheet.text
    assert "scrollbar-color: rgba(139,163,188,.34) transparent" in stylesheet.text
    assert ".navigation::-webkit-scrollbar { width: 6px; }" in stylesheet.text
    assert ".navigation::-webkit-scrollbar-track { background: transparent; }" in stylesheet.text
    assert ".navigation::-webkit-scrollbar-thumb:hover" in stylesheet.text
    assert ".navigation::-webkit-scrollbar-button" in stylesheet.text
    assert "返回控制台首页" in response.text
    assert 'label: "模型"' in script.text
    assert 'label: "版本"' in script.text
    assert 'label: "路由"' in script.text
    assert 'label: "实验"' in script.text
    assert 'label: "分组"' in script.text
    assert 'title: "API 调用记录"' in script.text
    assert 'label: "决策记录"' in script.text
    assert 'title: "决策记录列表"' in script.text
    assert 'label: "执行记录"' in script.text
    assert 'title: "执行记录列表"' in script.text
    assert 'title: "审计记录列表"' in script.text
    assert 'title: "部署列表"' in script.text
    routing_columns = script.text.split(
        "routings: {",
        maxsplit=1,
    )[1].split(
        "experiments: {",
        maxsplit=1,
    )[0]
    assert '["name", "路由名称"]' in routing_columns
    assert '["model_name", "模型名称"]' in routing_columns
    assert '["model_version", "版本"]' in routing_columns
    assert '["rollout_group", "发布分组", "deployment-role"]' in routing_columns
    assert 'title: "用户列表"' in script.text
    assert 'title: "角色列表"' in script.text
    assert '["email", "邮箱", "blank"]' in script.text
    assert 'kind === "blank"' in script.text
    assert "createResourceManager" in script.text
    assert "createTableControls" in script.text
    console_model_type = script.text.split(
        "@typedef {Object} ConsoleModel",
        maxsplit=1,
    )[1].split("*/", maxsplit=1)[0]
    assert "@property {string | null} [display_name]" in console_model_type
    assert "@property {string | null} [framework]" in console_model_type
    assert "@property {string | null} [model_type]" in console_model_type
    assert "@property {string | null} [task_type]" in console_model_type
    assert "@property {string | null} [description]" in console_model_type
    assert "async function openModelRegistrationDialog(" in (
        management_script.text
    )
    assert (
        "function openVersionRegistrationDialog()"
        in management_script.text
    )
    assert 'versions: "models.create"' in management_script.text
    assert 'versions: "添加版本"' in management_script.text
    assert (
        "await openVersionRegistrationDialog();"
        in management_script.text
    )
    version_registration_section = _function_source(
        management_script.text,
        "async function openVersionRegistrationDialog()",
        "async function openModelRegistrationDialog(",
    )
    assert "await openModelRegistrationDialog(null, models);" in (
        version_registration_section
    )
    assert "createManagementDialog({" not in version_registration_section
    model_registration_section = _function_source(
        management_script.text,
        "async function openModelRegistrationDialog(",
        "async function openDeploymentCreateDialog(",
    )
    assert 'label: "选择模型"' in model_registration_section
    assert 'label: addingVersion ? "版本信息" : "基本信息"' in (
        model_registration_section
    )
    assert "modelCandidates.map((model) => ({" in model_registration_section
    assert 'submitLabel: "确认注册"' in model_registration_section
    assert "if (wizard && activeStep < stepFields.length - 1)" in (
        management_script.text
    )
    assert "next.addEventListener(\"click\", advanceWizard)" in (
        management_script.text
    )
    assert (
        "async function openDeploymentCreateDialog(targetVersion = null)"
        in management_script.text
    )
    assert 'description: "选择模型版本并定义发布方式。"' in management_script.text
    assert "async function openRoutingCreateDialog()" in management_script.text
    assert (
        '"sections/deployments?page=1&page_size=100&sort_by=updated_at'
        '&sort_order=desc"'
        in management_script.text
    )
    assert "if (field.compact) label.classList.add(\"compact\")" in (
        management_script.text
    )
    assert ".management-field.checkbox-field.compact" in stylesheet.text
    wizard_steps_style = stylesheet.text.split(
        ".management-wizard-steps {",
        maxsplit=1,
    )[1].split("}", maxsplit=1)[0]
    assert "grid-auto-flow: column" in wizard_steps_style
    assert "grid-auto-columns: minmax(0, 1fr)" in wizard_steps_style
    assert "repeat(3" not in wizard_steps_style
    assert ".management-wizard-steps li.complete span::before" in (
        stylesheet.text
    )
    assert 'const deploymentRoleOptionsByRollout = {' in management_script.text
    assert 'full: [["champion", "Champion"]]' in management_script.text
    assert (
        'canary: [["champion", "Champion"], ["challenger", "Challenger"]]'
        in management_script.text
    )
    assert 'shadow: [["shadow", "Shadow"]]' in management_script.text
    assert 'optionsByField: "rollout_type"' in management_script.text
    assert 'label: "部署配置"' in management_script.text
    assert 'help: "可选，仅支持 JSON 文件。"' in management_script.text
    assert 'suffix: "%"' in management_script.text
    assert management_script.text.count("stepper: true") >= 3
    assert 'lockByField: "deployment_id"' in management_script.text
    assert 'lockValues: fullDeploymentIds' in management_script.text
    assert 'lockValue: 100' in management_script.text
    assert 'stepper: record.rollout_type !== "full"' in (
        management_script.text
    )
    assert 'readonly: record.rollout_type === "full"' in (
        management_script.text
    )
    assert 'function createNumberStepper(input, field)' in (
        management_script.text
    )
    assert 'button.setAttribute("aria-label", `${action}${field.label}`)' in (
        management_script.text
    )
    assert 'traffic_ratio: Number(formData.get("traffic_ratio")) / 100' in (
        management_script.text
    )
    assert '["traffic_ratio", "流量比例", "percentage"]' in script.text
    assert ".management-input-affix" in stylesheet.text
    assert ".management-number-stepper" in stylesheet.text
    assert ".management-number-stepper-button" in stylesheet.text
    assert ".management-number-stepper.locked" in stylesheet.text
    assert 'const environmentLabels = {' in script.text
    assert 'const environmentCodes = {' in script.text
    assert 'development: "开发环境"' in script.text
    assert 'development: "DEV"' in script.text
    assert 'id="service-environment"' in response.text
    assert 'class="topbar-actions"' in response.text
    assert 'class="service-environment topbar-environment"' in response.text
    assert 'align-items: center; gap: 14px; margin-left: auto' in stylesheet.text
    assert response.text.index('id="service-environment"') < (
        response.text.index('id="account-menu-button"')
    )
    assert response.text.index('id="account-avatar"') < (
        response.text.index('id="account-name"')
    )
    assert 'class="account-chevron"' in response.text
    assert 'getAccountInitials(displayName)' in script.text
    assert 'function getAccountAvatarTone(username)' in script.text
    assert 'accountAvatar.dataset.tone = getAccountAvatarTone(user.username)' in (
        script.text
    )
    assert '.account-avatar[data-tone="0"]' in stylesheet.text
    assert '.account-avatar[data-tone="7"]' in stylesheet.text
    assert 'background: #34495b' in stylesheet.text
    assert '.account-trigger:hover .account-avatar' in stylesheet.text
    assert 'filter: brightness(1.08)' in stylesheet.text
    assert 'background: #102d4f' in stylesheet.text
    assert '.account-trigger[aria-expanded="true"] .account-chevron' in (
        stylesheet.text
    )
    assert 'environmentBadge.dataset.environment = environment' in script.text
    assert '当前服务环境：${environmentLabel}' in script.text
    assert 'topbar.dataset.environment = environment' in script.text
    assert '.service-environment[data-environment="development"]' in (
        stylesheet.text
    )
    assert '.service-environment[data-environment="testing"]' in (
        stylesheet.text
    )
    assert '.service-environment[data-environment="staging"]' in (
        stylesheet.text
    )
    assert '.service-environment[data-environment="production"]' in (
        stylesheet.text
    )
    assert '.topbar-environment[data-environment="development"]' in (
        stylesheet.text
    )
    assert 'border-radius: 999px' in stylesheet.text
    assert 'environmentBadge.textContent = environmentCode' in script.text
    assert 'environmentBadge.title = environmentLabel' in script.text
    assert '.topbar[data-environment="production"]' in stylesheet.text
    assert "async function openExperimentCreateDialog()" in management_script.text
    assert "function openUserCreateDialog()" in management_script.text
    assert "function openRoleCreateDialog()" in management_script.text
    assert "function openUserEditDialog(record)" in management_script.text
    assert "function openRoleEditDialog(record)" in management_script.text
    assert '["name", "模型名称"]' in script.text
    assert '["latest_version", "最新版本"]' in script.text
    assert '["version_count", "版本数", "version-count"]' in script.text
    assert 'link.title = "查看全部版本"' in script.text
    assert '"编辑"' in management_script.text
    assert "function openModelEditDialog(record)" in management_script.text
    assert '["model_name", "模型名称"]' in script.text
    assert 'add("激活", "versions"' in management_script.text
    assert 'add("停用", "versions"' in management_script.text
    assert "function openVersionEditDialog(record)" in management_script.text
    assert 'add("弃用", "versions"' in management_script.text
    assert 'add("归档", "versions"' in management_script.text
    assert 'add("删除", "versions"' in management_script.text
    assert 'add("删除", "models"' in management_script.text
    assert 'add("恢复", "models"' in management_script.text
    assert 'add("永久清理", "models"' in management_script.text
    assert 'add("激活", "models"' in management_script.text
    assert 'add("停用", "models"' in management_script.text
    assert 'add("弃用", "models"' in management_script.text
    assert 'add("归档", "models"' in management_script.text
    assert '"restore", "models.create"' in management_script.text
    assert '"purge", "models.create", "danger"' in management_script.text
    assert '"delete", "models.create", "danger"' in management_script.text
    assert 'add("恢复", "versions"' in management_script.text
    assert 'add("永久清理", "versions"' in management_script.text
    assert "actions[lifecycleStart].dividerBefore = true;" in management_script.text
    assert 'actionConfig.dividerBefore ? "group-start" : ""' in management_script.text
    assert 'title: `删除${resourceLabel}`' in management_script.text
    assert 'id="resource-view-toggle"' in response.text
    assert '>回收站</button>' in response.text
    assert 'inTrash ? "返回列表" : "回收站"' in script.text
    model_actions = management_script.text.split(
        'if (section === "models")',
        1,
    )[1].split(
        '} else if (section === "versions")',
        1,
    )[0]
    assert model_actions.index(
        'add("删除", "models"'
    ) > model_actions.index(
        'add("归档", "models"'
    )
    assert 'const deletionMetadataColumns = [' in script.text
    assert 'const deletedModelVersionColumns = [' in script.text
    assert 'const deletedSectionColumns = {' in script.text
    assert 'models: [' in script.text
    assert 'versionView: "versions"' in script.text
    assert 'const recyclableSections = new Set(' in script.text
    assert 'const inRecyclableSection = recyclableSections.has(state.active)' in script.text
    assert 'sections/${section}?${buildPageQuery' in script.text
    assert 'state.active === "versions"' in script.text
    assert 'name: "config_file"' in management_script.text
    assert 'name: "rules_file"' in management_script.text
    assert 'name: "variant_config_file"' in management_script.text
    routing_create_section = management_script.text.split(
        "async function openRoutingCreateDialog()",
        maxsplit=1,
    )[1].split(
        "function openExperimentCreateDialog()",
        maxsplit=1,
    )[0]
    assert 'name: "name"' in routing_create_section
    assert 'label: "路由名称"' in routing_create_section
    assert 'name: optionalValue(formData, "name")' in routing_create_section
    assert 'label: "规则配置"' in routing_create_section
    assert 'help: "可选，仅支持 JSON 文件。"' in routing_create_section
    assert 'effective_from: optionalValue(formData, "effective_from")' in (
        routing_create_section
    )
    assert 'effective_to: optionalValue(formData, "effective_to")' in (
        routing_create_section
    )
    assert routing_create_section.index('label: "规则配置"') < (
        routing_create_section.index('label: "描述"')
    )
    experiment_create_section = management_script.text.split(
        "async function openExperimentCreateDialog()",
        maxsplit=1,
    )[1].split(
        "async function openVariantCreateDialog()",
        maxsplit=1,
    )[0]
    assert 'label: "模型"' in experiment_create_section
    assert 'type: "select"' in experiment_create_section
    assert '.filter((model) => model.status === "active")' in (
        experiment_create_section
    )
    assert 'description: "配置实验分流策略和生效时间。"' in (
        experiment_create_section
    )
    assert 'label: "流量比例"' in experiment_create_section
    assert 'suffix: "%"' in experiment_create_section
    assert 'stepper: true' in experiment_create_section
    assert 'label: "分桶字段"' in experiment_create_section
    assert 'placeholder: "例如 customer_id"' in experiment_create_section
    assert 'traffic_ratio: Number(formData.get("traffic_ratio")) / 100' in (
        experiment_create_section
    )
    assert experiment_create_section.index('name: "effective_from"') < (
        experiment_create_section.index('name: "effective_to"')
    )
    assert 'parseJsonFile(formData, "rules_file", "规则配置")' in (
        management_script.text
    )
    assert "async function parseJsonFile" in management_script.text
    assert "function openDeploymentEditDialog(record)" in management_script.text
    assert "function openRoutingEditDialog(record)" in management_script.text
    assert "function openExperimentEditDialog(record)" in management_script.text
    assert "function openVariantEditDialog(record)" in management_script.text
    assert "创建本地用户并分配角色。" in management_script.text
    assert "创建角色并从权限目录中分配权限。" in management_script.text
    assert "变更将在保存后生效。" in management_script.text
    assert "修改用户资料及角色分配。" in management_script.text
    assert 'element.dataset.conditionallyHidden === "true"' in management_script.text
    assert "forceField.dataset.conditionallyHidden" in management_script.text
    assert "readonly: builtin" in management_script.text
    assert 'label.classList.add("readonly")' in management_script.text
    assert 'input.setAttribute("aria-readonly", "true")' in management_script.text
    assert ".management-field.readonly > span" in stylesheet.text
    assert "background: #edf1f4" in stylesheet.text
    assert 'lockedValues: builtin ? ["administrator"] : []' in management_script.text
    assert 'fixedValue.type = "hidden"' in management_script.text
    assert "function openPasswordChangeDialog()" in management_script.text
    assert "function getRecordActions(section, record)" in management_script.text
    assert "function runRecordAction(actionConfig, record)" in management_script.text
    assert 'formData.getAll("roles")' in management_script.text
    assert 'formData.getAll("permissions")' in management_script.text
    assert 'title: "编辑角色"' in management_script.text
    assert 'label: "描述", type: "textarea"' in management_script.text
    assert 'description: optionalValue(formData, "description")' in (
        management_script.text
    )
    assert 'type: "choices"' in management_script.text
    assert 'type: "multiselect"' in management_script.text
    assert "function appendMultiSelectField(body, field)" in management_script.text
    assert "function buildManagementFormData(form)" in management_script.text
    assert "function closeManagementMultiselects(form)" in management_script.text
    assert "formData.delete(fieldName)" in management_script.text
    assert 'input.dataset.selected === "true"' in management_script.text
    assert 'menu.setAttribute("popover", "manual")' in management_script.text
    assert 'search.placeholder = "搜索权限"' in management_script.text
    assert "function filterOptions()" in management_script.text
    assert "function handleOutsidePointerDown(event)" in management_script.text
    assert "selected.slice(0, 2)" in management_script.text
    assert 'overflow.className = "multiselect-overflow"' in management_script.text
    assert "closeManagementMultiselects(form)" in management_script.text
    assert "onSubmit(formData)" in management_script.text
    assert 'tag.className = "multiselect-tag"' in management_script.text
    assert 'removePath.setAttribute("d", "M7 7l10 10M17 7 7 17")' in management_script.text
    assert 'menu.setAttribute("role", "listbox")' in management_script.text
    assert "mark.hidden = true" in management_script.text
    assert "mark.hidden = !selectedOption" in management_script.text
    assert 'markPath.setAttribute("d", "m5 12.5 4.2 4.2L19 7")' in management_script.text
    assert 'input.type = "hidden"' in management_script.text
    assert "input.disabled = !selected" in management_script.text
    assert 'if (nextSelected && input.value === "*")' in management_script.text
    assert "if (!record.is_builtin)" in management_script.text
    assert 'label: "内置角色不可修改"' in management_script.text
    assert "button.disabled = Boolean(actionConfig.disabled)" in management_script.text
    assert "const iconOnly = Boolean(createLabels[resource])" in management_script.text
    assert 'createButton.textContent = iconOnly ? "+" : label' in management_script.text
    assert 'createButton.setAttribute("aria-label", label)' in management_script.text
    assert "await openDeploymentCreateDialog();" in management_script.text
    assert '.filter((model) => model.status === "active")' in management_script.text
    assert '.filter((version) => version.status === "active")' in management_script.text
    assert 'label: "模型"' in management_script.text
    assert 'label: "版本"' in management_script.text
    assert 'optionsByField: "model_id"' in management_script.text
    assert "accountSectionKeys.has(key)" in script.text
    account_management_source = _function_source(
        script.text,
        "function renderAccountManagement()",
        "function showLogin(",
    )
    assert 'users: "users.manage"' in account_management_source
    assert 'roles: "roles.manage"' in account_management_source
    assert 'headers["X-CSRF-Token"] = csrfToken' in script.text
    assert "if (!csrfToken && retry && refreshable && await restoreCsrfSession())" in script.text
    assert "body.error === csrfErrorMessage" in script.text
    assert 'fetch("./api/session"' in script.text
    assert 'title: "实验列表"' in script.text
    assert "function renderModelUsage()" in script.text
    assert "function renderModelUsageRanking(" in script.text
    assert ".model-ranking-list" in stylesheet.text
    assert "compareModelUsageNames(left, right)" in script.text
    assert '["model_name", "模型名称"]' in script.text
    assert '["model_version", "版本"]' in script.text
    assert '["rollout_type", "发布类型"]' in script.text
    assert '["role", "角色", "deployment-role"]' in script.text
    assert '["variant_count", "分组", "variant-count"]' in script.text
    assert 'function renderExperimentVariantsPage(experiment)' in script.text
    assert 'function navigateToExperimentVariants(' in script.text
    assert '["name", "分组名称"]' in script.text
    assert "createExperimentDetailController" in script.text
    assert '["request_id", "请求 ID", "mono"]' in script.text
    assert '["latency_ms", "耗时（毫秒）", "duration"]' in script.text
    assert "createSortHeader" in script.text
    assert "aria-sort" in script.text
    assert "event.shiftKey || event.ctrlKey || event.metaKey" in script.text
    assert 'priority.className = "sort-priority"' in script.text
    assert "function normalizeSortParameters(" in script.text
    assert "最多支持 ${maxSortFields} 个排序字段" in script.text
    assert ".sort-priority" in stylesheet.text
    assert 'createInferenceDetailController({' in script.text
    assert 'executionType === "primary"' in script.text
    assert 'executionType === "shadow"' in script.text
    assert ".login-credit" in stylesheet.text
    assert "width: min(660px, 100%)" in stylesheet.text
    assert "margin: auto" in stylesheet.text
    assert "align-self: stretch" in stylesheet.text
    assert "height: 100dvh" in stylesheet.text
    assert (
        script.text.index('label: "模型"')
        < script.text.index('label: "版本"')
        < script.text.index('label: "部署"')
        < script.text.index('label: "路由"')
        < script.text.index('label: "实验"')
        < script.text.index('label: "分组"')
        < script.text.index('label: "运行状态"')
        < script.text.index('label: "API 调用"')
        < script.text.index('label: "决策记录"')
        < script.text.index('label: "执行记录"')
        < script.text.index('label: "审计记录"')
    )
    assert "返回模型" in response.text
    assert "输入关键词查询" in response.text
    assert 'id="search-toggle-button"' in response.text
    assert 'class="search-toggle-icon"' in response.text
    assert 'id="search-form" class="search-form" role="search" hidden' in response.text
    assert 'id="collapse-search-button"' in response.text
    assert "queryToggle.addEventListener" in table_script.text
    assert "queryCollapse.addEventListener" in table_script.text
    assert 'queryInput.addEventListener("input"' in table_script.text
    assert "let queryDraftDirty = false" in table_script.text
    assert "hasQueryDraft()" in table_script.text
    assert "const queryBeingEdited" in table_script.text
    assert "document.activeElement === queryInput" in table_script.text
    assert "const preserveQueryDraft" in table_script.text
    assert "if (!preserveQueryDraft)" in table_script.text
    assert "const listRefreshPaused" in script.text
    assert "tableControls.hasQueryDraft()" in script.text
    assert 'queryToggle.classList.toggle("has-query"' in table_script.text
    assert '["permissions", "权限", "permissions"]' in script.text
    assert "function createPermissionSummary(value, record = null)" in script.text
    assert "@typedef {Object} ConsoleRole" in script.text
    assert "@property {string[]} [effective_permissions]" in script.text
    assert "record.effective_permissions" in script.text
    assert 'overflow.textContent = `+${hiddenCount}`' in script.text
    assert 'id="selected-export-button"' in response.text
    assert "下载已选" in response.text
    assert "已选择 ${formattedCount} 条" in script.text
    assert "clear-selection-button" in response.text
    assert "select-all-checkbox" in script.text
    assert "record-select-checkbox" in script.text
    assert "selectedRecordIds" in script.text
    assert "async function exportRecords(recordIds)" in script.text
    assert 'class="panel-heading-main"' in response.text
    assert "data.total_pages" in table_script.text
    assert "if (data.total_pages > 1)" in table_script.text
    assert "jump.noValidate = true" in table_script.text
    assert "之间的页码" in table_script.text
    assert 'jumpButton.textContent = "跳转"' in table_script.text
    assert "PAGE_SIZE_OPTIONS = [10, 20, 50, 100]" in table_script.text
    assert 'sizeSelect.setAttribute("aria-label", "每页显示条数")' in table_script.text
    assert 'parameters.set("page_size", String(pageSize))' in script.text
    build_export_section = script.text.split(
        "function buildExportPath()",
        maxsplit=1,
    )[1].split(
        "function buildPageQuery(",
        maxsplit=1,
    )[0]
    assert (
        'parameters.set("deleted", '
        'String(state.versionView === "trash"))'
        in build_export_section
    )
    assert ".page-jump" in stylesheet.text
    assert ".page-size" in stylesheet.text
    assert ".create-icon-button" in stylesheet.text
    assert "background: var(--navy-900)" in stylesheet.text
    assert ".create-icon-button::before" in stylesheet.text
    assert ".create-icon-button::after" in stylesheet.text
    assert ".pagination .page-indicator" in stylesheet.text
    assert ".table-container { overflow-x: auto; }" in stylesheet.text
    assert 'page.className = "page-indicator"' in table_script.text
    assert 'page.textContent = `${formatNumber(data.page)} / ${formatNumber(data.total_pages)}`' in table_script.text
    assert ".permission-summary" in stylesheet.text
    assert ".permission-chip" in stylesheet.text
    assert ".permission-overflow" in stylesheet.text
    assert ".multiselect-trigger" in stylesheet.text
    assert ".multiselect-menu" in stylesheet.text
    assert ".multiselect-menu-header" in stylesheet.text
    assert ".multiselect-search" in stylesheet.text
    assert ".multiselect-overflow" in stylesheet.text
    assert ".multiselect-tag-remove" in stylesheet.text
    assert ".multiselect-option-mark[hidden]" in stylesheet.text
    assert "appearance: none" in stylesheet.text
    assert "frame-ancestors 'none'" in response.headers[
        "content-security-policy"
    ]
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"
    assert stylesheet.status_code == 200
    assert format_script.status_code == 200
    assert management_script.status_code == 200
    assert table_script.status_code == 200
    assert "--navy-950" in stylesheet.text
    assert ".request-drawer-body { display: flex" in stylesheet.text
    assert ".request-detail-grid { display: grid; flex: 0 0 auto" in stylesheet.text
    assert ".request-json-section { flex: 0 0 auto" in stylesheet.text
    assert ".execution-comparison-section { flex: 0 0 auto" in stylesheet.text
    assert ".execution-type.primary" in stylesheet.text
    assert ".execution-type.shadow" in stylesheet.text
    assert 'if (status === "received") return "info"' in format_script.text
    assert ".status.info" in stylesheet.text
    assert 'dataPanel.classList.add("access-empty")' in script.text
    assert "当前账户暂无可访问内容" in script.text
    assert "请联系管理员分配角色或查看权限。" in script.text
    assert "function configureEmptyListControls(query)" in script.text
    assert "tableControls.setQueryAvailable(Boolean(query))" in script.text
    assert "configureEmptyListControls(state.sectionQuery)" in script.text
    assert "configureEmptyListControls(state.versionQuery)" in script.text
    assert "configureEmptyListControls(state.variantQuery)" in script.text
    assert ".data-panel.access-empty .panel-heading" in stylesheet.text
    assert ".request-json-section pre { margin: 0" in stylesheet.text


@pytest.mark.asyncio
async def test_overview_navigation_requires_request_access() -> None:
    """测试概览导航遵循 API 调用查看权限"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        script = await client.get(
            "/assets/app.js"
        )
        dashboard_script = await client.get(
            "/assets/dashboard.js"
        )

    script = SimpleNamespace(
        status_code=script.status_code,
        text="\n".join((script.text, dashboard_script.text)),
    )

    assert script.status_code == 200
    assert "function canViewOverview(" in script.text
    assert "Boolean(snapshot.access.requests)" in script.text
    assert "if (canViewOverview(snapshot))" in script.text
    assert "applyDefaultRoute(available)" in script.text
    assert "snapshot !== null && canViewOverview(snapshot)" in script.text


@pytest.mark.asyncio
async def test_console_page_supports_realtime_details() -> None:
    """测试资源详情和无闪烁实时更新交互"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        page = await client.get("/")
        script = await client.get(
            "/assets/app.js"
        )
        resources_script = await client.get(
            "/assets/resources.js"
        )
        presentation_script = await client.get(
            "/assets/presentation.js"
        )
        deployment_script = await client.get(
            "/assets/details/deployment.js"
        )
        routing_script = await client.get(
            "/assets/details/routing.js"
        )
        model_script = await client.get(
            "/assets/details/model.js"
        )
        version_script = await client.get(
            "/assets/details/version.js"
        )
        common_script = await client.get(
            "/assets/details/common.js"
        )
        access_script = await client.get(
            "/assets/details/access.js"
        )
        runtime_script = await client.get(
            "/assets/details/runtime.js"
        )
        experiment_script = await client.get(
            "/assets/details/experiment.js"
        )
        inference_script = await client.get(
            "/assets/details/inference.js"
        )
        audit_script = await client.get(
            "/assets/details/audit.js"
        )
        management_script = await client.get(
            "/assets/management.js"
        )
        format_script = await client.get(
            "/assets/format.js"
        )
        stylesheet = await client.get(
            "/assets/style.css"
        )

    script = SimpleNamespace(
        status_code=script.status_code,
        text="\n".join((
            script.text,
            resources_script.text,
            presentation_script.text,
        )),
    )

    assert 'class="auth-pending"' in page.text
    assert ".auth-pending .login-shell" in stylesheet.text
    assert ".auth-pending .dashboard" in stylesheet.text
    assert 'document.documentElement.classList.remove("auth-pending")' in script.text
    assert '["version", "版本"]' in script.text
    assert 'function enableDetailRow(row, section, record)' in script.text
    assert 'function isInteractiveRowTarget(target, row)' in script.text
    assert 'enableDetailRow(row, state.active, record)' in script.text
    assert 'enableDetailRow(row, "models", record)' in script.text
    assert 'enableDetailRow(row, "experiments", record)' in script.text
    assert "snapshot.counts[section] = data.total;" in script.text
    assert "renderNavigation();" in resources_script.text
    assert 'enableDetailRow(versionRow, "versions", version)' in script.text
    assert 'enableDetailRow(variantRow, "variants", variant)' in script.text
    assert '.detail-row { cursor: pointer; }' in stylesheet.text
    assert common_script.status_code == 200
    assert "export function appendDetailField" in common_script.text
    assert "export function createDetailDrawer" in common_script.text
    assert "export function createDetailSummary" in common_script.text
    assert "export function createDetailSection" in common_script.text
    assert "export function createDetailAction" in common_script.text
    assert "export function mountDetailDrawer" in common_script.text
    assert model_script.status_code == 200
    model_source = model_script.text
    version_source = version_script.text
    assert "export function createModelDetailController" in model_source
    assert "export function createVersionDetailController" in version_source
    assert '"版本详情",' in version_source
    assert 'createUsageSection(model, related, dialog)' in model_source
    assert 'document.createTextNode("关联资源")' in model_source
    assert 'document.createTextNode("关联资源")' in version_source
    assert 'document.createTextNode("流量分配")' in model_source
    assert '"用户请求按比例转发"' in model_source
    assert '"仅复制请求，不返回响应"' in model_source
    assert 'const sections = ["deployments", "routings", "runtimes", "experiments"]' in model_source
    assert 'navigateToModelVersions(model)' in model_source
    assert (
        'navigateToSection(\n'
        '            key,\n'
        '            1,\n'
        '            `model_id:${model.model_id}`,\n'
        '          )'
        in model_source
    )
    assert 'icon: "version"' in model_source
    assert "iconContainer.classList.add(icon)" in model_source
    assert ".registry-model-usage-icon.runtime" in stylesheet.text
    assert '["deployments", "model", "部署"]' in model_source
    assert '["runtimes", "runtime", "运行实例"]' in model_source
    assert 'createDeploymentRoleBadge(route.rollout_group)' in model_source
    assert 'deployment.setAttribute("aria-label", "查看部署")' in model_source
    assert '["模型 ID", () => createCopyableNavigationLink(' in model_source
    assert '["版本 ID", () => createCopyableNavigationLink(' in version_source
    assert '"文件信息",' in version_source
    assert '["制品 ID", () => createFileIdentifier(' in version_source
    assert '["Bento Tag", () => createFileIdentifier(' in version_source
    assert '["文件路径", () => createFileIdentifier(' in version_source
    assert '["SHA-256 校验值", () => createFileIdentifier(' in version_source
    assert '"registry-version-file-identifier-truncated"' in version_source
    assert '.registry-version-file-identifier-truncated {' in stylesheet.text
    assert 'if (!storageKey && !schema) return "未配置";' in version_source
    assert 'createDetailBadge(version.framework, "framework")' in version_source
    assert 'createSchemaFileValue(' in version_source
    assert '["显示名称", version.display_name]' in version_source
    assert '["类型", version.model_type]' in version_source
    assert '["任务类型", version.task_type]' in version_source
    assert 'const sections = ["deployments", "routings", "runtimes"]' in version_source
    assert (
        'navigateToSection(\n'
        '            key,\n'
        '            1,\n'
        '            `version_id:${version.version_id}`,\n'
        '          )'
        in version_source
    )
    assert 'createRelatedResourceCard({' in version_source
    assert 'button.className = "registry-model-usage-item"' in version_source
    assert 'createDetailAction("查看部署", "model")' in version_source
    assert 'createDetailAction("部署版本", "deploy", "primary")' in version_source
    assert 'activating ? "激活版本" : "停用版本"' in version_source
    assert 'openVersionCreateDialog(model)' in model_source
    assert 'openDeploymentCreateDialog(version)' in version_source
    assert 'value: targetVersion?.model_id' in management_script.text
    assert 'value: targetVersion?.version_id' in management_script.text
    assert '.registry-detail-summary {' in stylesheet.text
    assert '.registry-version-list {' in stylesheet.text
    assert '.registry-detail-actions {' in stylesheet.text
    assert deployment_script.status_code == 200
    deployment_source = deployment_script.text
    assert "export function createDeploymentDetailController" in deployment_source
    assert '"deployment-detail-drawer",' in deployment_source
    assert '["开始时间", formatTime(record.effective_from)]' in deployment_source
    assert "...(record.effective_to" in deployment_source
    assert '["运行实例", "当前没有运行实例"]' in deployment_source
    assert '["运行数据", "正在获取…"]' in deployment_source
    assert '["运行数据", "运行状态暂不可用"]' in deployment_source
    assert '["控制版本", generations[0]]' in deployment_source
    assert '`deployment_id:${record.deployment_id}`' in deployment_source
    assert '"部署配置",' in deployment_source
    assert '"运行状态",' in deployment_source
    assert '["部署 ID", (drawer) => createCopyableSectionNavigationLink(' in deployment_source
    assert '["描述", record.description]' in deployment_source
    assert '["创建时间", formatTime(record.created_at)]' in deployment_source
    assert '["更新时间", formatTime(record.updated_at)]' in deployment_source
    assert '["角色", createDeploymentRoleBadge(record.role)]' in deployment_source
    assert 'createDetailAction("查看运行实例", "monitor")' in deployment_source
    assert 'getRecordActions("deployments", record)' in deployment_source
    assert "appendDetailFooter(dialog, buttons)" in deployment_source
    assert routing_script.status_code == 200
    routing_source = routing_script.text
    assert "export function createRoutingDetailController" in routing_source
    assert '"routing-detail-drawer",' in routing_source
    assert '["路由名称", record.name]' in routing_source
    assert '["路由 ID", (drawer) => createCopyableSectionNavigationLink(' in routing_source
    assert '["状态", createStatusBadge(record.status)]' in routing_source
    assert "subtitle:" in routing_source
    assert "[record.model_name, record.model_version]" in routing_source
    assert "badges: record.rollout_group" in routing_source
    assert "[createDeploymentRoleBadge(record.rollout_group)]" in (
        routing_source
    )
    assert 'headingText.textContent = "流量分配"' in routing_source
    assert 'traffic: ["M12 21a9' in common_script.text
    assert '(left, right) => Number(right.traffic_ratio || 0)' in routing_source
    assert '"deployments",\n        dialog,\n        "›",' in routing_source
    assert 'viewDeployment.setAttribute("aria-label", "查看部署")' in routing_source
    assert 'copyButton.append(createDetailIcon("copy"))' in (
        presentation_script.text
    )
    assert 'await navigator.clipboard.writeText(value)' in script.text
    assert 'copyButton.replaceChildren(createDetailIcon("check"))' in (
        presentation_script.text
    )
    assert 'feedback.textContent = "已复制"' in script.text
    assert 'titleText.textContent = "规则配置"' in routing_source
    assert 'createDeploymentRoleBadge(record.rollout_group)' in routing_source
    assert 'getRecordActions("routings", record)' in routing_source
    assert 'label = "删除路由"' in routing_source
    assert 'delete: ["M4 6h16"' in common_script.text
    assert 'help.className = "routing-traffic-help"' in routing_source
    assert 'createDetailIcon("help", "routing-traffic-help-icon")' in routing_source
    assert 'createDetailIcon("help", "routing-traffic-help-icon")' in model_script.text
    assert 'help: [' in common_script.text
    assert 'tooltip.setAttribute("role", "tooltip")' in routing_source
    assert '.routing-traffic-track {' in stylesheet.text
    assert '.routing-traffic-tooltip {' in stylesheet.text
    assert '.routing-condition-card {' in stylesheet.text
    assert runtime_script.status_code == 200
    runtime_source = runtime_script.text
    assert "export function createRuntimeDetailController" in runtime_source
    assert '"运行实例详情"' in runtime_source
    assert '["实例 ID", () => createCopyableNavigationLink(' in runtime_source
    assert 'createDetailSection("运行状态"' in runtime_source
    assert 'runtime: ["M3 13h4l2.2-7 4.3 13 3-9 2.2 5H21"]' in common_script.text
    assert '.runtime-detail-drawer .registry-summary-icon {' in stylesheet.text
    assert "color: #4f5fb3; background: #eef1ff" in stylesheet.text
    assert '"m12 3 8 4.5-8 4.5-8-4.5L12 3Z"' in common_script.text
    runtime_section = script.text.split(
        "  runtimes: {",
        maxsplit=1,
    )[1].split(
        "  requests: {",
        maxsplit=1,
    )[0]
    assert '["role", "角色", "deployment-role"]' in runtime_section
    assert '["worker_id", "运行节点", "runtime-worker"]' in runtime_section
    assert 'summary.className = "worker-summary"' in script.text
    assert 'hostname.className = "worker-hostname"' in script.text
    assert '.worker-hostname {' in stylesheet.text
    assert '.request-link:hover {' in stylesheet.text
    assert 'text-decoration-color: #8fc8c1' in stylesheet.text
    assert '.worker-process {' in stylesheet.text
    assert '.deployment-role.champion {' in stylesheet.text
    assert '["health_status", "健康状态", "status"]' in script.text
    assert '["健康状态", createStatusBadge(record.health_status)]' in runtime_source
    assert '"unhealthy"' in format_script.text
    assert '["healthy", "running"].includes(status)' in format_script.text
    assert experiment_script.status_code == 200
    experiment_source = experiment_script.text
    assert "export function createExperimentDetailController" in experiment_source
    assert '"实验详情"' in experiment_source
    assert '"分组详情"' in experiment_source
    assert '["实验 ID", () => createCopyableNavigationLink(' in experiment_source
    assert '["分组 ID", () => createCopyableNavigationLink(' in experiment_source
    assert '["分组名称", () => createSectionNavigationLink(' in experiment_source
    assert 'record.variant_id,\n          "variants",' in experiment_source
    assert 'document.createTextNode("分组分配")' in experiment_source
    assert 'getRecordActions(section, record)' in experiment_source
    assert '`experiment_id:${record.experiment_id}`' in experiment_source
    assert '`variant_id:${record.variant_id}`' in experiment_source
    assert inference_script.status_code == 200
    inference_source = inference_script.text
    assert "export function createInferenceDetailController" in inference_source
    assert '"API 调用详情"' in inference_source
    assert '"决策记录详情"' in inference_source
    assert '"执行记录详情"' in inference_source
    assert '"inference-detail-drawer api-detail-drawer"' in inference_source
    assert '"inference-detail-drawer decision-detail-drawer"' in inference_source
    assert '"inference-detail-drawer execution-detail-drawer"' in inference_source
    assert '["调用 ID", () => createCopyableNavigationLink(' in inference_source
    assert '["决策 ID", () => createCopyableNavigationLink(' in inference_source
    assert '["执行 ID", () => createCopyableNavigationLink(' in inference_source
    assert 'document.createTextNode("模型执行")' in inference_source
    assert 'document.createTextNode("决策路径")' in inference_source
    assert 'label: "路由命中"' in inference_source
    assert 'label: "实验分配"' in inference_source
    assert 'label: "最终目标"' in inference_source
    assert 'createDecisionPathAction(' in inference_source
    assert '"查看路由",' in inference_source
    assert '"查看实验",' in inference_source
    assert '`${sectionIdFields[section]}:${identifier}`' in inference_source
    assert inference_source.count(
        "formatOptionalDuration(record.latency_ms)"
    ) == 5
    assert "formatOptionalDuration(execution.latency_ms)" in inference_source
    assert 'createDetailBadge(record.user, "purple")' in inference_source
    assert "subtitle: [record.model_version, record.ip]" in inference_source
    assert 'createJsonDetailSection("执行结果", record.prediction, "prediction")' in (
        inference_source
    )
    assert 'createJsonDetailSection("执行上下文", record.context, "metadata")' in (
        inference_source
    )
    assert "function createExecutionRoutingSection(record, dialog)" in inference_source
    assert 'createDetailIcon("link", "registry-section-icon")' in inference_source
    assert 'document.createTextNode("路由来源")' in inference_source
    assert "title: record.routing_name || record.routing_id" in inference_source
    assert '[record.model_name, record.model_version].filter(Boolean).join(" · ")' in (
        inference_source
    )
    assert 'copy.replaceChildren(createDetailIcon("check"))' in (
        common_script.text
    )
    assert "navigator.clipboard.writeText(serialized)" in common_script.text
    assert "createDetailIcon(\"copy\")" in common_script.text
    assert 'code.className = "registry-json-code"' in common_script.text
    assert "dialog.append(header, createJsonCode(value ?? {}, title))" in (
        common_script.text
    )
    assert ".registry-json-copy.copied" in stylesheet.text
    assert ".registry-decision-path-step" in stylesheet.text
    assert audit_script.status_code == 200
    audit_source = audit_script.text
    assert "export function createAuditDetailController" in audit_source
    assert '"审计记录详情"' in audit_source
    assert '["审计 ID", () => createCopyableNavigationLink(' in audit_source
    assert 'document.createTextNode("变更内容")' in audit_source
    assert 'createDetailIcon("change", "registry-section-icon")' in audit_source
    assert "createJsonCode," in audit_source
    assert "const content = createJsonCode(value, label)" in audit_source
    assert "export function createJsonCode(value, title)" in common_script.text
    assert '], dialog, "request", appendRequestDetail)' in audit_source
    assert 'record.context, "metadata"' in audit_source
    assert '`audit_id:${record.audit_id}`' in audit_source
    assert '`${sectionIdFields[targetSection]}:${record.target_id}`' in audit_source
    assert '`${sectionIdFields[section]}:${value}`' in presentation_script.text
    assert 'request: [' in common_script.text
    assert 'decision: [' in common_script.text
    assert 'execution: [' in common_script.text
    assert 'audit: [' in common_script.text
    assert 'change: [' in common_script.text
    assert 'metadata: [' in common_script.text
    assert '"M12 7v6"' in common_script.text
    assert '"M9 3h6v4H9Z"' in common_script.text
    assert '"m8 14 2.5 2.5L16 11"' in common_script.text
    assert '.api-detail-drawer .registry-summary-icon {' in stylesheet.text
    assert '.decision-detail-drawer .registry-summary-icon {' in stylesheet.text
    assert '.execution-detail-drawer .registry-summary-icon {' in stylesheet.text
    assert '.audit-detail-drawer .registry-summary-icon {' in stylesheet.text
    assert access_script.status_code == 200
    access_source = access_script.text
    assert "export function createAccessDetailController" in access_source
    assert "/** @type {string[]} */" in access_source
    assert "for (const role of record.roles) roles.push(String(role))" in access_source
    assert 'createDetailDrawer("用户详情")' in access_source
    assert 'createDetailDrawer("角色详情")' in access_source
    assert "await refreshVisiblePage();" in script.text
    refresh_source = _function_source(
        script.text,
        "async function refreshOverview",
        "async function refreshVisiblePage",
    )
    assert "if (state.active === null)" in refresh_source
    normalized_script = script.text.replace(
        "\r\n",
        "\n",
    )
    assert "await loadOverview({ silent: true });\n    startAutoRefresh();" in normalized_script
    assert 'setRealtimeStatus("实时连接中断 · 30 秒校准中", false);' in script.text
    assert 'eventSource.addEventListener("changed", (event) =>' in script.text
    assert 'eventSource.addEventListener("sync", (event) =>' in script.text
    assert "function startRealtimeUpdates(skipInitialSync = false)" in script.text
    assert "if (skipInitialSync)" in script.text
    assert "skipInitialSync = false;" in script.text
    assert script.text.count("startRealtimeUpdates(true);") == 3
    assert "queueRealtimeRefresh(event);" in script.text
    assert "const realtimeRefreshDelay = 200;" in script.text
    assert "await applyRealtimeChanges(queuedChanges);" in script.text
    realtime_apply_source = _function_source(
        script.text,
        "async function applyRealtimeChanges",
        "function clearRealtimeRefresh",
    )
    assert "await loadOverview({ silent: true });" in realtime_apply_source
    assert "realtimeRefreshRunning = true;" in script.text
    assert "scheduleRealtimeRefresh();" in script.text
    assert "function refreshSession()" in script.text
    assert "if (sessionRefreshRequest !== null) return sessionRefreshRequest;" in script.text
    assert script.text.count('fetch("./api/refresh"') == 1
    assert script.text.count("await refreshSession()") == 2
    visibility_source = _function_source(
        script.text,
        'document.addEventListener("visibilitychange"',
        "(async function boot()",
    )
    assert "startRealtimeUpdates();" in visibility_source


def _function_source(
        source: str,
        start: str,
        end: str,
) -> str:
    """提取两个函数声明之间的脚本内容"""
    source = source.replace(
        "\r\n",
        "\n",
    )

    return source[
        source.index(start):source.index(end)
    ]


@pytest.mark.asyncio
async def test_session_requires_login() -> None:
    """测试会话接口拒绝未登录请求"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/session"
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "尚未登录"
    }


@pytest.mark.asyncio
async def test_session_restores_missing_csrf_cookie(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效会话自动补发缺失的 CSRF Cookie"""
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=create_user()),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/session"
        )

    assert response.status_code == 200
    csrf_cookie = next(
        cookie
        for cookie in response.headers.get_list(
            "set-cookie"
        )
        if cookie.startswith(
            "datamind_console_csrf="
        )
    )
    assert "SameSite=strict" in csrf_cookie


@pytest.mark.asyncio
async def test_management_options_return_selectable_catalogs(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试管理表单返回模型类型、权限和有效角色选项"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
                "identity.manage",
            ]
        }
    )
    identity_service = MagicMock()
    identity_service.list_roles = AsyncMock(
        return_value=[
            {
                "name": "developer",
                "description": "开发人员",
            }
        ]
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "IdentityService",
        lambda: identity_service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/management/options"
        )

    assert response.status_code == 200
    payload = response.json()
    assert "logistic_regression" in payload["model_types"]
    assert payload["permissions"][0] == "*"
    assert "model.read" in payload["permissions"]
    assert payload["roles"] == [
        {
            "name": "developer",
            "description": "开发人员",
        }
    ]
    identity_service.list_roles.assert_awaited_once_with(
        status=app_module.RoleStatus.ACTIVE,
        limit=1000,
    )


@pytest.mark.asyncio
async def test_login_creates_http_only_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地账户登录创建 HttpOnly 浏览器会话"""
    service = MagicMock()
    service.login = AsyncMock(
        return_value=TokenResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=1800,
        )
    )
    service.authenticate_access_token = AsyncMock(
        return_value=create_user()
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "create_auth_service",
        lambda *, session: service,
    )
    monkeypatch.setitem(
        vars(cookies_module),
        "get_settings",
        lambda: SimpleNamespace(
            auth=SimpleNamespace(
                refresh_token_expires_days=7
            )
        ),
    )
    authentication_audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_record_authentication_event",
        authentication_audit,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/login",
            json={
                "username": "alice",
                "password": "secret",
            },
        )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert any(
        "datamind_console_access=access-token" in cookie
        and "HttpOnly" in cookie
        and "SameSite=strict" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_refresh=refresh-token" in cookie
        and "HttpOnly" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_csrf=" in cookie
        and "SameSite=strict" in cookie
        for cookie in cookies
    )
    authentication_audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_deployment_requires_csrf_and_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试部署创建同时校验写权限和 CSRF 令牌"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "deployment.write",
            ]
        }
    )
    service = MagicMock()
    service.create_deployment = AsyncMock(
        return_value={
            "deployment_id": "dep_test",
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "environment": "development",
            "rollout_type": "full",
            "role": "champion",
            "status": "inactive",
        }
    )
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DeploymentLifecycleService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        lambda: audit_recorder,
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_hostname",
        lambda: "console-host",
    )
    payload = {
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "rollout_type": "full",
        "role": "champion",
    }

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        denied = await client.post(
            "/api/deployments",
            json=payload,
        )
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        created = await client.post(
            "/api/deployments",
            json=payload,
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
                "X-Request-ID": "req_console_test",
                "traceparent": (
                    "00-0123456789abcdef0123456789abcdef-"
                    "0123456789abcdef-01"
                ),
            },
        )
        legacy = await client.post(
            "/api/deployments",
            json={
                **payload,
                "environment": "testing",
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert denied.status_code == 403
    assert denied.json() == {
        "error": "请求安全校验失败，请刷新页面后重试"
    }
    assert created.status_code == 201
    assert created.json()["deployment_id"] == "dep_test"
    assert legacy.status_code == 400
    service.create_deployment.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
        environment="development",
        rollout_type="full",
        role="champion",
        config=None,
        description=None,
        deployed_by="alice",
    )
    audit_recorder.record.assert_awaited_once()
    record_call = audit_recorder.record.await_args
    assert record_call is not None
    audit_context = (
        record_call.kwargs[
            "context"
        ]
    )
    assert audit_context["source"] is AuditSource.HTTP
    assert audit_context["request_id"] == "req_console_test"
    assert audit_context["trace_id"] == (
        "0123456789abcdef0123456789abcdef"
    )
    assert audit_context["hostname"] == "console-host"


@pytest.mark.asyncio
async def test_register_model_accepts_schema_files(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型注册接口接收并解析 Schema 文件"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
            ],
        }
    )
    service = MagicMock()
    service.register = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "version_id": "ver_test",
        }
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "ModelRegistrationService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_record_write_audit",
        audit,
    )
    metadata = {
        "name": "scorecard",
        "version": "1.0.0",
        "framework": "sklearn",
        "model_type": "logistic_regression",
        "task_type": "scoring",
        "force": False,
    }

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        response = await client.post(
            "/api/models",
            files={
                "metadata": (
                    None,
                    json.dumps(metadata),
                ),
                "file": (
                    "scorecard.pkl",
                    b"model-data",
                    "application/octet-stream",
                ),
                "input_schema": (
                    "input_schema.json",
                    json.dumps({
                        "feature_names": [
                            "age",
                        ],
                    }),
                    "application/json",
                ),
                "output_schema": (
                    "output_schema.json",
                    json.dumps({
                        "type": "number",
                    }),
                    "application/json",
                ),
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 201
    register_call = service.register.await_args
    assert register_call is not None
    register_kwargs = register_call.kwargs
    assert register_kwargs["input_schema"] == {
        "feature_names": [
            "age",
        ],
    }
    assert register_kwargs["output_schema"] == {
        "type": "number",
    }
    assert register_kwargs["created_by"] == "alice"
    assert register_kwargs["model_path"].endswith(
        "model.pkl"
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_model_information(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型显示名称和描述更新接口"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
            ],
        }
    )
    service = MagicMock()
    service.update_model = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "name": "scorecard",
            "display_name": "信用评分卡模型",
            "description": "用于信用风险评分",
        }
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "ModelCatalogService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_record_write_audit",
        audit,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        response = await client.patch(
            "/api/models/mdl_test",
            json={
                "display_name": "信用评分卡模型",
                "description": "用于信用风险评分",
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    service.update_model.assert_awaited_once_with(
        model_id="mdl_test",
        display_name="信用评分卡模型",
        description="用于信用风险评分",
        updated_by="alice",
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_version_information(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本说明更新接口"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
            ],
        }
    )
    service = MagicMock()
    service.update_version = AsyncMock(
        return_value={
            "version_id": "ver_test",
            "model_id": "mdl_test",
            "version": "1.0.0",
            "description": "稳定版本",
            "status": "inactive",
        }
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "ModelCatalogService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_record_write_audit",
        audit,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        response = await client.patch(
            "/api/versions/ver_test",
            json={
                "description": "稳定版本",
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    service.update_version.assert_awaited_once_with(
        version_id="ver_test",
        description="稳定版本",
        updated_by="alice",
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_password_is_available_without_admin_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试普通登录用户可以修改自己的密码"""
    user = create_user().model_copy(
        update={
            "permissions": [],
        }
    )
    service = MagicMock()
    service.change_password = AsyncMock(
        return_value={
            "user_id": user.user_id,
            "username": user.username,
            "password_changed_at": "2026-08-21T01:00:00Z",
        }
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "IdentityService",
        lambda **_kwargs: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_access",
            "access-token",
        )
        client.cookies.set(
            "datamind_console_refresh",
            "refresh-token",
        )
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        response = await client.post(
            "/api/account/password",
            json={
                "current_password": "current-secret",
                "new_password": "new",
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    service.change_password.assert_awaited_once_with(
        username="alice",
        current_password="current-secret",
        new_password="new",
        operator_id="usr_alice",
        operator="alice",
    )
    cookies = response.headers.get_list(
        "set-cookie"
    )
    assert any(
        "datamind_console_access=" in cookie
        and "Max-Age=0" in cookie
        for cookie in cookies
    )
    assert any(
        "datamind_console_refresh=" in cookie
        and "Max-Age=0" in cookie
        for cookie in cookies
    )
@pytest.mark.asyncio
async def test_identity_manager_updates_user_and_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份管理员更新用户资料和角色权限"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "identity.manage",
            ],
        }
    )
    service = MagicMock()
    service.update_user = AsyncMock(
        return_value={
            "user_id": "usr_bob",
            "username": "robert",
        }
    )
    service.update_role = AsyncMock(
        return_value={
            "role_id": "rol_developer",
            "name": "developer",
            "description": "模型开发角色",
            "permissions": [
                "model.read",
                "model.write",
            ],
        }
    )
    identity_factory = MagicMock(
        return_value=service
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "IdentityService",
        identity_factory,
    )
    monkeypatch.setitem(
        vars(app_module),
        "get_hostname",
        lambda: "console-host",
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        client.cookies.set(
            "datamind_console_csrf",
            "csrf-token",
        )
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": "csrf-token",
            "X-Request-ID": "req_identity_update",
            "X-Trace-ID": (
                "0123456789abcdef0123456789abcdef"
            ),
        }
        user_response = await client.patch(
            "/api/users/bob",
            json={
                "username": "robert",
                "display_name": "Robert",
                "email": "robert@example.com",
                "roles": [
                    "developer",
                ],
            },
            headers=headers,
        )
        role_response = await client.patch(
            "/api/roles/developer",
            json={
                "description": "模型开发角色",
                "permissions": [
                    "model.read",
                    "model.write",
                ],
            },
            headers=headers,
        )

    assert user_response.status_code == 200
    assert role_response.status_code == 200
    assert identity_factory.call_count == 2
    for factory_call in identity_factory.call_args_list:
        assert factory_call.kwargs[
            "audit_source"
        ] is AuditSource.HTTP
        audit_context = factory_call.kwargs[
            "audit_context"
        ]
        assert audit_context["request_id"] == (
            "req_identity_update"
        )
        assert audit_context["trace_id"] == (
            "0123456789abcdef0123456789abcdef"
        )
        assert audit_context["ip"] == "127.0.0.1"
        assert audit_context["hostname"] == "console-host"
        assert audit_context["user"] == "alice"
    service.update_user.assert_awaited_once_with(
        username="bob",
        new_username="robert",
        display_name="Robert",
        email="robert@example.com",
        role_names=[
            "developer",
        ],
        operator_id="usr_alice",
        operator="alice",
    )
    service.update_role.assert_awaited_once_with(
        name="developer",
        description="模型开发角色",
        permissions=[
            "model.read",
            "model.write",
        ],
        operator_id="usr_alice",
        operator="alice",
    )


@pytest.mark.asyncio
async def test_version_restore_and_purge_actions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台接入版本恢复和永久清理服务"""
    user = create_user().model_copy(
        update={"permissions": ["model.write"]}
    )
    deletion_service = MagicMock()
    deletion_service.restore = AsyncMock(
        return_value={"version_id": "ver_test", "action": "restore_version"}
    )
    deletion_service.purge = AsyncMock(
        return_value={"version_id": "ver_test", "action": "purge_completed"}
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "ModelDeletionService",
        lambda: deletion_service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_record_write_audit",
        audit,
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set("datamind_console_csrf", "csrf-token")
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": "csrf-token",
        }
        restore_response = await client.post(
            "/api/actions/versions/ver_test/restore",
            json={},
            headers=headers,
        )
        purge_response = await client.post(
            "/api/actions/versions/ver_test/purge",
            json={"reason": "超过保留期"},
            headers=headers,
        )

    assert restore_response.status_code == 200
    assert purge_response.status_code == 200
    deletion_service.restore.assert_awaited_once_with(
        version_id="ver_test",
        operator="alice",
    )
    deletion_service.purge.assert_awaited_once_with(
        version_id="ver_test",
        reason="超过保留期",
        operator="alice",
    )
    assert audit.await_count == 2


@pytest.mark.asyncio
async def test_model_lifecycle_action_is_exposed_over_http(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型生命周期动作可通过统一管理接口调用。"""
    user = create_user().model_copy(
        update={"permissions": ["model.write"]}
    )
    lifecycle_service = MagicMock()
    lifecycle_service.deactivate = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "model_status": "inactive",
        }
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "ModelLifecycleService",
        lambda: lifecycle_service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_record_write_audit",
        audit,
    )

    async with AsyncClient(
            transport=ASGITransport(app=app_module.console_app),
            base_url="http://testserver",
    ) as client:
        client.cookies.set("datamind_console_csrf", "csrf-token")
        response = await client.post(
            "/api/actions/models/mdl_test/deactivate",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.json()["model_status"] == "inactive"
    lifecycle_service.deactivate.assert_awaited_once_with(
        model_id="mdl_test",
        updated_by="alice",
    )
    audit.assert_awaited_once()


def test_user_payload_exposes_write_capabilities() -> None:
    """测试当前会话返回基于权限计算的管理能力"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.write",
                "runtime.manage",
            ]
        }
    )

    payload = app_module._user_payload(
        user
    )

    assert payload["environment"] == "development"
    assert payload["capabilities"] == {
        capability: permission in {
            "model.write",
            "runtime.manage",
        }
        for capability, permission in (
            app_module._CAPABILITY_PERMISSIONS.items()
        )
    }


@pytest.mark.asyncio
async def test_overview_uses_authenticated_permissions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台概览按当前用户权限生成"""
    user = create_user()
    service = MagicMock()
    service.snapshot = AsyncMock(
        return_value={
            "access": {
                "models": True
            },
            "sections": {
                "models": []
            },
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/overview"
        )

    assert response.status_code == 200
    service.snapshot.assert_awaited_once_with(
        permissions=["model.read"],
        trend_range="24h",
    )


@pytest.mark.asyncio
async def test_overview_uses_requested_trend_range(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概览传递 API 调用趋势时间范围"""
    service = MagicMock()
    service.snapshot = AsyncMock(
        return_value={
            "access": {},
            "sections": {},
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/overview?range=7d"
        )

    assert response.status_code == 200
    service.snapshot.assert_awaited_once_with(
        permissions=["model.read"],
        trend_range="7d",
    )


@pytest.mark.asyncio
async def test_model_versions_uses_server_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口使用当前用户权限和分页参数"""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
    service.get_model_versions = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions",
            params={
                "page": 2,
                "page_size": 10,
                "q": "score",
                "sort": "version",
                "order": "desc",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with([
        "model.read"
    ])
    service.get_model_versions.assert_awaited_once_with(
        model_id="mdl_test",
        page=2,
        page_size=10,
        query="score",
        sort_by="version",
        sort_order="desc",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_experiment_variants_use_server_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口使用当前用户权限和分页参数"""
    service = MagicMock()
    service.get_access.return_value = {
        "experiments": True
    }
    service.get_experiment_variants = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/experiments/exp_test/variants",
            params={
                "page": 2,
                "page_size": 10,
                "q": "control",
                "sort": "weight",
                "order": "desc",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with([
        "model.read"
    ])
    service.get_experiment_variants.assert_awaited_once_with(
        experiment_id="exp_test",
        page=2,
        page_size=10,
        query="control",
        sort_by="weight",
        sort_order="desc",
    )


@pytest.mark.asyncio
async def test_section_uses_server_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台页面接口使用当前用户权限和分页参数"""
    user = create_user()
    service = MagicMock()
    service.get_access.return_value = {
        "versions": True
    }
    service.get_section = AsyncMock(
        return_value={
            "items": [],
            "page": 2,
            "page_size": 10,
            "has_previous": True,
            "has_next": False,
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/versions",
            params={
                "page": 2,
                "page_size": 10,
                "q": "score",
                "sort": "name",
                "order": "asc",
                "deleted": "true",
            },
        )

    assert response.status_code == 200
    service.get_access.assert_called_once_with([
        "model.read"
    ])
    service.get_section.assert_awaited_once_with(
        section="versions",
        page=2,
        page_size=10,
        query="score",
        sort_by="name",
        sort_order="asc",
        deleted=True,
    )


@pytest.mark.asyncio
async def test_runtime_section_uses_current_instances(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行实例接口只查询当前实例。"""
    service = MagicMock()
    service.get_access.return_value = {
        "runtimes": True
    }
    service.get_section = AsyncMock(
        return_value={
            "items": [],
            "page": 1,
            "page_size": 10,
            "has_previous": False,
            "has_next": False,
        }
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/runtimes",
        )

    assert response.status_code == 200
    service.get_section.assert_awaited_once_with(
        section="runtimes",
        page=1,
        page_size=10,
        query="",
        sort_by=None,
        sort_order="asc",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_section_export_streams_filtered_csv(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出当前筛选和排序条件下的全部记录"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.read",
                "data.export",
            ]
        }
    )
    service = MagicMock()
    service.get_access.return_value = {
        "models": True,
    }
    service.get_section = AsyncMock(
        return_value={
            "items": [
                {
                    "model_id": "mdl_test",
                    "name": "scorecard",
                    "params": {
                        "threshold": 0.5,
                    },
                }
            ],
            "page": 1,
            "page_size": 100,
            "total": 1,
            "total_pages": 1,
            "has_previous": False,
            "has_next": False,
            "query": "score",
            "sort_by": "name",
            "sort_order": "desc",
        }
    )
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(
            return_value=user
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(
            return_value=service
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(
            return_value=audit_recorder
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/models/export",
            params={
                "q": "score",
                "sort": "name",
                "order": "desc",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/csv"
    )
    assert re.fullmatch(
        r'attachment; filename="models_\d{8}_\d{6}\.csv"',
        response.headers["content-disposition"],
    )
    assert response.content.startswith(
        b"\xef\xbb\xbf"
    )
    csv_text = response.content.decode(
        "utf-8-sig"
    )
    assert "model_id,name,params" in csv_text
    assert "mdl_test,scorecard" in csv_text
    assert '"{""threshold"":0.5}"' in csv_text
    service.get_section.assert_awaited_once_with(
        section="models",
        page=1,
        page_size=100,
        query="score",
        sort_by="name",
        sort_order="desc",
        deleted=False,
    )
    audit_recorder.record.assert_awaited_once()
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["target_type"] == "console"
    assert audit_call.kwargs["context"]["source"] == "http"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("section", "item"),
    [
        (
            "requests",
            {
                "request_id": "req_test",
                "decision_id": "dcs_test",
                "model_id": "mdl_test",
                "deployment_id": "dep_test",
            },
        ),
        (
            "decisions",
            {
                "decision_id": "dcs_test",
                "request_id": "req_test",
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "deployment_id": "dep_test",
                "experiment_id": "exp_test",
                "variant_id": "var_test",
                "assignment_id": "asn_test",
            },
        ),
        (
            "executions",
            {
                "execution_id": "exe_test",
                "decision_id": "dcs_test",
                "request_id": "req_test",
                "model_id": "mdl_test",
                "version_id": "ver_test",
                "deployment_id": "dep_test",
                "routing_id": "rtn_test",
            },
        ),
    ],
)
async def test_trace_exports_preserve_complete_id_relationships(
        monkeypatch: pytest.MonkeyPatch,
        section: str,
        item: dict[str, str],
) -> None:
    """测试调用链导出保留完整 ID 对应关系"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "request.read",
                "data.export",
            ]
        }
    )
    service = MagicMock()
    service.get_access.return_value = {
        section: True,
    }
    service.get_section = AsyncMock(
        return_value={
            "items": [item],
            "page": 1,
            "page_size": 100,
            "total": 1,
            "total_pages": 1,
            "has_previous": False,
            "has_next": False,
            "query": "",
            "sort_by": None,
            "sort_order": "asc",
        }
    )
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(
            return_value=user
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(
            return_value=service
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(
            return_value=audit_recorder
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/sections/{section}/export"
        )

    assert response.status_code == 200
    csv_lines = response.content.decode(
        "utf-8-sig"
    ).splitlines()
    assert csv_lines == [
        ",".join(item),
        ",".join(item.values()),
    ]


@pytest.mark.asyncio
async def test_section_export_only_selected_records(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出接口只查询用户选择的记录"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "model.read",
                "data.export",
            ]
        }
    )
    service = MagicMock()
    service.get_access.return_value = {
        "models": True,
    }
    service.get_section = AsyncMock(
        return_value={
            "items": [
                {
                    "model_id": "mdl_second",
                    "name": "scorecard",
                }
            ],
            "page": 1,
            "page_size": 100,
            "total": 1,
            "total_pages": 1,
            "has_previous": False,
            "has_next": False,
            "query": "score",
            "sort_by": "name",
            "sort_order": "asc",
        }
    )
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(
            return_value=user
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(
            return_value=service
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(
            return_value=audit_recorder
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/sections/models/export",
            params={
                "q": "score",
                "sort": "name",
            },
            json={
                "record_ids": [
                    "mdl_second",
                    "mdl_first",
                ]
            },
        )

    assert response.status_code == 200
    assert "mdl_second,scorecard" in response.text
    service.get_section.assert_awaited_once_with(
        section="models",
        page=1,
        page_size=100,
        query="score",
        sort_by="name",
        sort_order="asc",
        deleted=False,
        record_ids=(
            "mdl_second",
            "mdl_first",
        ),
    )
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    assert audit_call.kwargs["after"][
        "selection"
    ] == "selected"
    assert audit_call.kwargs["after"][
        "total"
    ] == 1


def test_export_filename_uses_uniform_local_timestamp() -> None:
    """测试导出文件名统一使用页面名称和本地时间"""
    export_filename = vars(app_module)[
        "_export_filename"
    ]
    filename = export_filename(
        "versions",
        now=datetime(
            2026,
            8,
            17,
            1,
            32,
            38,
            tzinfo=timezone.utc,
        ),
        timezone_name="Asia/Shanghai",
    )

    assert filename == "versions_20260817_093238.csv"


@pytest.mark.asyncio
async def test_section_export_requires_export_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出接口要求独立数据导出权限"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True,
    }
    service.get_section = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(
            return_value=create_user()
        ),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(
            return_value=service
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/models/export"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有数据导出权限",
    }
    service.get_section.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/overview",
        "/api/models/mdl_test/versions",
        "/api/experiments/exp_test/variants",
        "/api/sections/models",
        "/api/events",
    ],
)
async def test_console_data_endpoints_require_login(
        path: str,
) -> None:
    """测试控制台数据接口统一要求登录"""
    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            path
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": "尚未登录"
    }


@pytest.mark.asyncio
async def test_overview_reports_unavailable_database(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概览在数据库异常时返回服务不可用"""
    service = MagicMock()
    service.snapshot = AsyncMock(
        side_effect=SQLAlchemyError(
            "database unavailable"
        )
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/overview"
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": "控制台数据暂不可用"
    }


@pytest.mark.asyncio
async def test_model_versions_enforces_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本接口拒绝无查看权限用户"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": False
    }

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有模型查看权限"
    }


@pytest.mark.asyncio
async def test_experiment_variants_enforce_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组接口拒绝无实验查看权限用户"""
    service = MagicMock()
    service.get_access.return_value = {
        "experiments": False
    }

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/experiments/exp_test/variants"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有实验查看权限"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "message"),
    [
        (
            ValueError("分页参数无效"),
            400,
            "分页参数无效",
        ),
        (
            SQLAlchemyError("database unavailable"),
            503,
            "模型版本数据暂不可用",
        ),
    ],
)
async def test_model_versions_maps_service_errors(
        monkeypatch: pytest.MonkeyPatch,
        error: Exception,
        status_code: int,
        message: str,
) -> None:
    """测试模型版本接口转换参数和数据库异常"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
    service.get_model_versions = AsyncMock(
        side_effect=error
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/models/mdl_test/versions"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("access", "section", "status_code", "message"),
    [
        (
            {
                "models": True
            },
            "unknown",
            404,
            "控制台页面不存在",
        ),
        (
            {
                "models": False
            },
            "models",
            403,
            "没有页面查看权限",
        ),
    ],
)
async def test_section_validates_access(
        monkeypatch: pytest.MonkeyPatch,
        access: dict[str, bool],
        section: str,
        status_code: int,
        message: str,
) -> None:
    """测试分页接口校验页面存在性和查看权限"""
    service = MagicMock()
    service.get_access.return_value = access

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/sections/{section}"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


@pytest.mark.asyncio
async def test_section_rejects_identity_reader_for_users(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份只读用户不能访问控制台用户列表"""
    user = create_user().model_copy(
        update={
            "permissions": [
                "identity.read"
            ]
        }
    )

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(
            return_value=user
        ),
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/users"
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有页面查看权限"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "message"),
    [
        (
            ValueError("分页参数无效"),
            400,
            "分页参数无效",
        ),
        (
            SQLAlchemyError("database unavailable"),
            503,
            "控制台页面数据暂不可用",
        ),
    ],
)
async def test_section_maps_service_errors(
        monkeypatch: pytest.MonkeyPatch,
        error: Exception,
        status_code: int,
        message: str,
) -> None:
    """测试分页接口转换参数和数据库异常"""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True
    }
    service.get_section = AsyncMock(
        side_effect=error
    )

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        lambda: service,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/sections/models"
        )

    assert response.status_code == status_code
    assert response.json() == {
        "error": message
    }


class FakeEventBroker:
    """控制台 SSE 测试事件代理"""

    @asynccontextmanager
    async def subscribe(
            self,
    ) -> AsyncIterator[asyncio.Queue[int]]:
        """返回隔离事件队列"""
        yield asyncio.Queue()


def create_event_request(
        last_event_id: str | None = None,
) -> Request:
    """创建控制台事件流请求"""
    headers: list[tuple[bytes, bytes]] = []

    if last_event_id is not None:
        headers.append((
            b"last-event-id",
            last_event_id.encode(
                "ascii"
            ),
        ))

    async def receive() -> dict[str, object]:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/events",
        "headers": headers,
    }, receive)


@pytest.mark.asyncio
async def test_stream_events_starts_with_consistent_sync(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次连接从最新游标执行一致性同步"""
    async def get_event_window() -> tuple[int | None, int]:
        return None, 12

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    request = create_event_request()
    stream = app_module._stream_events(
        request=request,
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: sync" in message
    assert "id: 12" in message
    assert 'data: {"topics":["models"]}' in message


@pytest.mark.asyncio
async def test_stream_events_filters_topics_by_permission(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流只推送当前用户有权查看的主题"""
    events = [
        OutboxEvent(
            event_id=6,
            topic="models",
            action="update",
        ),
        OutboxEvent(
            event_id=7,
            topic="audits",
            action="insert",
        ),
    ]

    async def get_event_window() -> tuple[int, int]:
        return 1, 7

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return events

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    request = create_event_request(
        "5"
    )
    stream = app_module._stream_events(
        request=request,
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: changed" in message
    assert "id: 7" in message
    assert '"topics":["models"]' in message
    assert (
        '"changes":[{"topic":"models",'
        '"action":"update"}]'
    ) in message


@pytest.mark.asyncio
async def test_events_streams_only_granted_topics(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件接口仅建立有权限主题的事件流"""
    user = create_user()
    received_topics: set[str] | None = None

    class DashboardStub:
        """控制台权限测试服务"""

        @staticmethod
        def get_access(
                _permissions: list[str],
        ) -> dict[str, bool]:
            return {
                "models": True,
                "audits": False,
            }

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return user

    async def stream_events(
            *,
            request: Request,
            allowed_topics: set[str],
    ) -> AsyncIterator[str]:
        nonlocal received_topics
        assert request.url.path == "/api/events"
        received_topics = allowed_topics
        yield "event: sync\ndata: {}\n\n"

    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        DashboardStub,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_stream_events",
        stream_events,
    )

    async with AsyncClient(
            transport=ASGITransport(
                app=app_module.console_app
            ),
            base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/events"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == (
        "no-cache, no-transform"
    )
    assert response.headers["x-accel-buffering"] == "no"
    assert received_topics == {
        "models"
    }


async def timeout_wait_for(
        awaitable: Coroutine[object, object, object],
        *,
        timeout: float,
) -> None:
    """关闭等待协程并模拟 SSE 心跳超时"""
    assert timeout > 0
    awaitable.close()
    raise TimeoutError


@pytest.mark.asyncio
async def test_stream_events_reports_expired_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件流定期校验并报告登录会话过期"""
    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
            _request: object,
    ) -> None:
        return None

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request(
            "1"
        ),
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert "event: authentication" in message
    assert 'data: {"status":"expired"}' in message


@pytest.mark.asyncio
async def test_stream_events_sends_heartbeat_for_valid_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试有效会话在空闲时接收 SSE 心跳"""
    async def get_event_window() -> tuple[int, int]:
        return 1, 1

    async def get_events_after(
            _event_id: int,
    ) -> list[OutboxEvent]:
        return []

    async def authenticate(
            _request: object,
    ) -> AuthenticatedUser:
        return create_user()

    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        FakeEventBroker(),
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_event_window",
        get_event_window,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_get_events_after",
        get_events_after,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        authenticate,
    )
    monkeypatch.setitem(
        vars(app_module),
        "_EVENT_AUTH_CHECK_SECONDS",
        0,
    )
    monkeypatch.setitem(
        vars(app_module.asyncio),
        "wait_for",
        timeout_wait_for,
    )
    stream = app_module._stream_events(
        request=create_event_request(
            "1"
        ),
        allowed_topics={
            "models"
        },
    )

    message = await anext(
        stream
    )
    await stream.aclose()

    assert message == ": keep-alive\n\n"


@pytest.mark.asyncio
async def test_event_repository_helpers(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试事件游标范围和增量事件查询"""
    event = OutboxEvent(
        event_id=8,
        topic="models",
        action="update",
    )
    repository = MagicMock()
    repository.get_oldest_event_id = AsyncMock(
        return_value=3
    )
    repository.get_latest_event_id = AsyncMock(
        return_value=8
    )
    repository.list_events = AsyncMock(
        return_value=[
            event
        ]
    )
    monkeypatch.setitem(
        vars(app_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(app_module),
        "OutboxRepository",
        lambda _session: repository,
    )

    window = await app_module._get_event_window()
    events = await app_module._get_events_after(
        7
    )

    assert window == (
        3,
        8,
    )
    assert events == [
        event
    ]
    repository.list_events.assert_awaited_once_with(
        after_event_id=7,
        limit=200,
    )


@pytest.mark.asyncio
async def test_event_query_waits_for_cleanup_when_cancelled() -> None:
    """验证事件查询取消时等待数据库清理完成"""
    query_started = asyncio.Event()
    allow_query_completion = asyncio.Event()

    async def query() -> str:
        query_started.set()
        await allow_query_completion.wait()
        return "completed"

    task = asyncio.create_task(
        app_module._complete_event_query(
            query()
        )
    )
    await query_started.wait()

    task.cancel()
    await asyncio.sleep(0)

    assert not task.done()

    allow_query_completion.set()

    with pytest.raises(
            asyncio.CancelledError
    ):
        await task


def test_event_cursor_and_sse_encoding_helpers() -> None:
    """测试事件游标解析和 SSE 消息编码"""
    assert app_module._parse_event_cursor(None) is None
    assert app_module._parse_event_cursor("invalid") is None
    assert app_module._parse_event_cursor("-1") is None
    assert app_module._parse_event_cursor("0") == 0

    message = app_module._encode_sse(
        event="authentication",
        data={
            "status": "expired"
        },
    )

    assert message == (
        "event: authentication\n"
        'data: {"status":"expired"}\n\n'
    )


def test_client_ip_returns_none_without_client() -> None:
    """测试缺少客户端地址时返回 None"""
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    })

    assert app_module._client_ip(request) is None


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_event_broker(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应用生命周期管理事件代理"""
    broker = MagicMock()
    broker.start = AsyncMock()
    broker.stop = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "event_broker",
        broker,
    )

    async with app_module._lifespan(
            app_module.console_app
    ):
        broker.start.assert_awaited_once_with()
        broker.stop.assert_not_awaited()

    broker.stop.assert_awaited_once_with()
