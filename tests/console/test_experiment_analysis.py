"""控制台实验分析接口测试.

核心功能：
  - test_experiment_analysis_contract:
    验证分析接口鉴权、基准传递及错误响应
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from tests.console._app_support import FakeUnitOfWork, app_module, create_user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("permission", "error", "status"),
    [
        (None, None, 401),
        ("model.read", None, 403),
        ("experiment.read", None, 200),
        ("experiment.read", ValueError("实验不存在"), 404),
        ("experiment.read", ValueError("基准分组不属于当前实验"), 400),
        ("experiment.read", SQLAlchemyError("private database detail"), 503),
    ],
)
async def test_experiment_analysis_contract(
        monkeypatch: pytest.MonkeyPatch,
        permission: str | None,
        error: Exception | None,
        status: int,
) -> None:
    """验证分析接口鉴权、基准传递及错误响应."""
    if permission is None:
        user = None
    else:
        user = create_user()
        user.permissions = [permission]
    monkeypatch.setitem(
        vars(app_module), "_authenticate", AsyncMock(return_value=user),
    )
    monkeypatch.setitem(vars(app_module), "UnitOfWork", FakeUnitOfWork)
    result = MagicMock()
    result.to_dict.return_value = {"experiment_id": "exp_demo", "decision_count": 3}
    analyzer = MagicMock()
    analyzer.analyze_experiment = AsyncMock(return_value=result, side_effect=error)
    factory = MagicMock(return_value=analyzer)
    monkeypatch.setitem(vars(app_module), "ABTestAnalyzer", factory)
    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app), base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/experiments/exp_demo/analysis?baseline_variant_id=variant_control",
        )
    assert response.status_code == status
    if status in (401, 403):
        factory.assert_not_called()
    else:
        analyzer.analyze_experiment.assert_awaited_once_with(
            experiment_id="exp_demo", baseline_variant_id="variant_control",
        )
    if status == 200:
        assert response.json()["decision_count"] == 3
        assert response.headers["cache-control"] == "no-store"
    if status == 503:
        assert "private database detail" not in response.text
