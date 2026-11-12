"""管理控制台应用信息测试.

验证登录前可查询实际安装版本，并避免浏览器缓存过期版本。

核心功能：
  - test_info_returns_installed_version:
    验证版本信息无需登录且支持子路径部署
  - test_info_handles_missing_distribution:
    验证缺少发行包信息时返回空版本
"""

from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)

from tests.console._app_support import app_module


@pytest.mark.asyncio
@pytest.mark.parametrize("root_path", ["", "/console"])
async def test_info_returns_installed_version(
        monkeypatch: pytest.MonkeyPatch,
        root_path: str,
) -> None:
    """测试登录前返回实际安装版本，且响应不被浏览器缓存."""
    package_version = MagicMock(return_value="0.1.2")
    monkeypatch.setitem(vars(app_module), "package_version", package_version)

    async with AsyncClient(
        transport=ASGITransport(
            app=app_module.console_app,
            root_path=root_path,
        ),
        base_url=f"https://testserver{root_path}/",
    ) as client:
        response = await client.get("api/info")

    assert response.status_code == 200
    assert response.json() == {"version": "0.1.2"}
    assert response.headers["cache-control"] == "no-store"
    package_version.assert_called_once_with("pydatamind")


@pytest.mark.asyncio
async def test_info_handles_missing_distribution(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试缺少发行包信息时返回空版本."""
    package_version = MagicMock(side_effect=PackageNotFoundError("pydatamind"))
    monkeypatch.setitem(vars(app_module), "package_version", package_version)

    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {"version": None}
