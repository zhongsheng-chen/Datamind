"""Console 写操作 HTTP 契约测试

验证控制台写接口的权限、CSRF、防重复提交、审计以及错误响应契约。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from datamind.auth.schemas import AuthenticatedUser
from datamind.audit.enums import AuditSource
from datamind.services.mutation import MutationResult
from tests.console._app_support import app_module, create_user


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
            "environment": "testing",
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
    monkeypatch.setitem(
        vars(app_module),
        "_service_environment",
        lambda: "testing",
    )
    payload = {
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "rollout_type": "full",
        "role": "champion",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
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
                    "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
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
    assert denied.json() == {"error": "请求安全校验失败，请刷新页面后重试"}
    assert created.status_code == 201
    assert created.json()["deployment_id"] == "dep_test"
    assert legacy.status_code == 400
    service.create_deployment.assert_awaited_once_with(
        model_id="mdl_test",
        version_id="ver_test",
        environment="testing",
        rollout_type="full",
        role="champion",
        threshold=None,
        description=None,
        deployed_by="alice",
    )
    audit_recorder.record.assert_awaited_once()
    record_call = audit_recorder.record.await_args
    assert record_call is not None
    audit_context = record_call.kwargs["context"]
    assert audit_context["source"] is AuditSource.HTTP
    assert audit_context["request_id"] == "req_console_test"
    assert audit_context["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert audit_context["hostname"] == "console-host"


@pytest.mark.asyncio
async def test_register_model_uploads_model_file(
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
        transport=ASGITransport(app=app_module.console_app),
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
    assert register_kwargs["created_by"] == "alice"
    assert register_kwargs["model_path"].endswith("model.pkl")
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
        transport=ASGITransport(app=app_module.console_app),
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
        transport=ASGITransport(app=app_module.console_app),
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
    identity_factory = MagicMock(return_value=service)
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
        transport=ASGITransport(app=app_module.console_app),
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
            "X-Trace-ID": "0123456789abcdef0123456789abcdef",
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
        assert factory_call.kwargs["audit_source"] is AuditSource.HTTP
        audit_context = factory_call.kwargs["audit_context"]
        assert audit_context["request_id"] == "req_identity_update"
        assert audit_context["trace_id"] == "0123456789abcdef0123456789abcdef"
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
    user = create_user().model_copy(update={"permissions": ["model.write"]})
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
    """测试模型生命周期动作可通过统一管理接口调用"""
    user = create_user().model_copy(update={"permissions": ["model.write"]})
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


@pytest.mark.asyncio
async def test_routing_enable_audit_records_state_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由启用审计仅记录状态变化"""
    user = create_user().model_copy(update={"permissions": ["routing.write"]})
    result = MutationResult(
        {
            "routing_id": "rtn_test",
            "name": "primary-route",
            "enabled": True,
        },
        before={"enabled": False},
        after={"enabled": True},
    )
    service = MagicMock()
    service.enable_routing = AsyncMock(return_value=result)
    audit_recorder = MagicMock()
    audit_recorder.record = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "RoutingLifecycleService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        lambda: audit_recorder,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set("datamind_console_csrf", "csrf-token")
        response = await client.post(
            "/api/actions/routings/rtn_test/enable",
            json={},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.json() == dict(result)
    service.enable_routing.assert_awaited_once_with(
        routing_id="rtn_test",
        updated_by="alice",
    )
    audit_recorder.record.assert_awaited_once()
    audit_call = audit_recorder.record.await_args
    assert audit_call is not None
    audit_arguments = audit_call.kwargs
    assert audit_arguments["action"] == "console.routings.enable"
    assert audit_arguments["target_type"] == "routing"
    assert audit_arguments["before"] == {"enabled": False}
    assert audit_arguments["after"] == {"enabled": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "retry"])
async def test_batch_action_is_exposed_over_http(
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批次取消和重试可通过统一管理接口调用"""
    user = create_user().model_copy(update={"permissions": ["prediction.invoke"]})
    service = MagicMock()
    setattr(
        service,
        action,
        AsyncMock(
            return_value={
                "batch_id": "bat_test",
                "status": "queued",
            }
        ),
    )
    audit = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "BatchLifecycleService",
        lambda: service,
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
            f"/api/actions/batches/bat_test/{action}",
            json={},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": "csrf-token",
            },
        )

    assert response.status_code == 200
    assert response.json()["batch_id"] == "bat_test"
    expected_arguments = {"batch_id": "bat_test"}
    getattr(service, action).assert_awaited_once_with(**expected_arguments)
    audit.assert_awaited_once()
    audit_call = audit.await_args
    assert audit_call is not None
    assert audit_call.kwargs["target_type"] == "batch"
