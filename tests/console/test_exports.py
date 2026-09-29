"""内网管理控制台公共导出测试.

验证控制台包公开 API 的完整性和可访问性。

核心功能：
  - test_console_exports_expected_public_api:
    验证控制台公共 API
"""

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import datamind.console as console
import pytest
from httpx import ASGITransport, AsyncClient

from tests.console._app_support import app_module, create_user


EXPECTED_EXPORTS = {
    "console_app",
    "DatamindConsoleService",
}


def test_console_exports_expected_public_api() -> None:
    """测试控制台包公开完整且准确的 API."""
    assert set(console.__all__) == EXPECTED_EXPORTS

    for name in console.__all__:
        assert hasattr(
            console,
            name,
        ), name


@pytest.mark.asyncio
async def test_section_export_streams_filtered_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出当前筛选和排序条件下的全部记录."""
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
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(return_value=service),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(return_value=audit_recorder),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
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
    assert response.headers["content-type"].startswith("text/csv")
    assert re.fullmatch(
        r'attachment; filename="models_\d{8}_\d{6}\.csv"',
        response.headers["content-disposition"],
    )
    assert response.content.startswith(b"\xef\xbb\xbf")
    csv_text = response.content.decode("utf-8-sig")
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
    """测试调用链导出保留完整 ID 对应关系."""
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
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(return_value=service),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(return_value=audit_recorder),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/api/sections/{section}/export")

    assert response.status_code == 200
    csv_lines = response.content.decode("utf-8-sig").splitlines()
    assert csv_lines == [
        ",".join(item),
        ",".join(item.values()),
    ]


@pytest.mark.asyncio
async def test_section_export_only_selected_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出接口只查询用户选择的记录."""
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
        AsyncMock(return_value=user),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(return_value=service),
    )
    monkeypatch.setitem(
        vars(app_module),
        "AuditRecorder",
        MagicMock(return_value=audit_recorder),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
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
    assert audit_call.kwargs["after"]["selection"] == "selected"
    assert audit_call.kwargs["after"]["total"] == 1


def test_export_filename_uses_uniform_local_timestamp() -> None:
    """测试导出文件名统一使用页面名称和本地时间."""
    export_filename = vars(app_module)["_export_filename"]
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
    """测试导出接口要求独立数据导出权限."""
    service = MagicMock()
    service.get_access.return_value = {
        "models": True,
    }
    service.get_section = AsyncMock()
    monkeypatch.setitem(
        vars(app_module),
        "_authenticate",
        AsyncMock(return_value=create_user()),
    )
    monkeypatch.setitem(
        vars(app_module),
        "DashboardService",
        MagicMock(return_value=service),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/sections/models/export")

    assert response.status_code == 403
    assert response.json() == {
        "error": "没有数据导出权限",
    }
    service.get_section.assert_not_awaited()
