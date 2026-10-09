"""管理控制台静态资源测试.

验证页面缓存校验、构建资源长期缓存及静态文件访问边界。

核心功能：
  - test_static_files_sets_cache_policy:
    验证静态资源缓存策略
  - test_static_files_revalidates_cache:
    验证条件请求复用缓存
  - test_static_files_returns_updated_page:
    验证页面更新后返回新内容
  - test_static_files_preserves_access_restrictions:
    验证静态资源访问限制
  - test_console_build_serves_fingerprinted_assets:
    测试构建入口、资源及子路径部署使用正确的缓存策略
  - test_console_page_requires_build:
    测试缺少构建产物时返回明确提示而不回退到源码
"""

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.routing import Mount

from datamind.console.assets import ConsoleStaticFiles
from tests.console._app_support import app_module


def create_app(directory: Path) -> Starlette:
    """创建隔离的静态资源测试应用."""
    return Starlette(
        routes=[
            Mount("/", app=ConsoleStaticFiles(directory=directory)),
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("index.html", "no-cache"),
        ("app.js", "no-cache"),
        ("app-Ab12_cd3.js", "public, max-age=31536000, immutable"),
        ("style-1234abcd.css", "public, max-age=31536000, immutable"),
    ],
)
async def test_static_files_sets_cache_policy(
    tmp_path: Path,
    method: str,
    filename: str,
    expected: str,
) -> None:
    """测试只有带内容指纹的构建资源启用长期缓存."""
    (tmp_path / filename).write_text("test content", encoding="utf-8")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(tmp_path)),
        base_url="http://testserver",
    ) as client:
        response = await client.request(method, f"/{filename}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == expected
    assert response.headers["etag"]
    assert response.headers["last-modified"]
    assert response.text == ("test content" if method == "GET" else "")


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["index.html", "app-Ab12_cd3.js"])
@pytest.mark.parametrize(
    ("validator", "condition"),
    [("etag", "if-none-match"), ("last-modified", "if-modified-since")],
)
async def test_static_files_revalidates_cache(
    tmp_path: Path,
    filename: str,
    validator: str,
    condition: str,
) -> None:
    """测试未变化资源返回 304 并保留缓存策略."""
    (tmp_path / filename).write_text("unchanged", encoding="utf-8")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(tmp_path)),
        base_url="http://testserver",
    ) as client:
        original = await client.get(f"/{filename}")
        cached = await client.get(
            f"/{filename}",
            headers={condition: original.headers[validator]},
        )

    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["cache-control"] == original.headers["cache-control"]
    assert cached.headers["etag"] == original.headers["etag"]


@pytest.mark.asyncio
async def test_static_files_returns_updated_page(tmp_path: Path) -> None:
    """测试更新入口页面后旧校验标识不再命中缓存."""
    page = tmp_path / "index.html"
    page.write_text("first release", encoding="utf-8")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(tmp_path)),
        base_url="http://testserver",
    ) as client:
        original = await client.get("/index.html")
        page.write_text("second release with new assets", encoding="utf-8")
        updated = await client.get(
            "/index.html",
            headers={
                "if-none-match": original.headers["etag"],
                "if-modified-since": original.headers["last-modified"],
            },
        )

    assert updated.status_code == 200
    assert updated.text == "second release with new assets"
    assert updated.headers["etag"] != original.headers["etag"]
    assert updated.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/missing-12345678.js", 404),
        ("POST", "/index.html", 405),
        ("GET", "/%2e%2e/outside.txt", 404),
    ],
)
async def test_static_files_preserves_access_restrictions(
    tmp_path: Path,
    method: str,
    path: str,
    expected: int,
) -> None:
    """测试不存在文件、非法方法和越界路径不启用长期缓存."""
    directory = tmp_path / "public"
    directory.mkdir()
    (directory / "index.html").write_text("page", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(directory)),
        base_url="http://testserver",
    ) as client:
        response = await client.request(method, path)

    assert response.status_code == expected
    assert "immutable" not in response.headers.get("cache-control", "")


@pytest.mark.asyncio
@pytest.mark.parametrize("root_path", ["", "/console"])
async def test_console_build_serves_fingerprinted_assets(root_path: str) -> None:
    """测试构建入口、资源及子路径部署使用正确的缓存策略."""
    async with AsyncClient(
        transport=ASGITransport(
            app=app_module.console_app,
            root_path=root_path,
        ),
        base_url=f"https://testserver{root_path}/",
    ) as client:
        page = await client.get("")
        assert page.status_code == 200, page.text
        assert page.headers["cache-control"] == "no-cache"
        cached_page = await client.get(
            page.url,
            headers={"if-none-match": page.headers["etag"]},
        )
        assert cached_page.status_code == 304
        assert cached_page.headers["cache-control"] == "no-cache"
        assert cached_page.content == b""

        urls = re.findall(r'(?:src|href)="(\./assets/[^"?]+)"', page.text)
        assert any(url.endswith(".js") for url in urls)
        assert any(url.endswith(".css") for url in urls)
        for url in urls:
            assert re.search(r"-[A-Za-z0-9_-]{8,}\.(js|css)$", url)
            asset = await client.get(page.url.join(url))
            assert asset.status_code == 200
            assert asset.content
            assert asset.headers["cache-control"] == (
                "public, max-age=31536000, immutable"
            )
            assert asset.headers["x-content-type-options"] == "nosniff"
            cached_asset = await client.get(
                asset.url,
                headers={"if-none-match": asset.headers["etag"]},
            )
            assert cached_asset.status_code == 304
            assert cached_asset.content == b""
            assert (
                cached_asset.headers["cache-control"]
                == (asset.headers["cache-control"])
            )

        source = await client.get(page.url.join("./assets/app.js"))
        assert source.status_code == 404


@pytest.mark.asyncio
async def test_console_page_requires_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试缺少构建产物时返回明确提示而不回退到源码."""
    monkeypatch.setitem(vars(app_module), "_STATIC_DIR", tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app_module.console_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 503
    assert "npm run build:console" in response.text
    assert response.headers["cache-control"] == "no-store"
