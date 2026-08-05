# tests/cli/test_credentials.py

"""CLI 凭据存储测试

验证凭据路径、原子读写、格式校验和本地会话清理。

核心功能：
  - test_get_credentials_path_uses_environment_override:
    验证环境变量覆盖凭据路径
  - test_credential_store_saves_and_loads_tokens:
    验证原子保存和读取令牌
  - test_credential_store_rejects_invalid_content:
    验证拒绝损坏的凭据文件
  - test_credential_store_clears_credentials:
    验证删除本地登录凭据
"""

import json
from pathlib import Path

import pytest

from datamind.auth.schemas import TokenResponse
from datamind.cli.credentials import (
    CredentialStore,
    get_credentials_path,
)
from datamind.cli.errors import CredentialError


def create_tokens() -> TokenResponse:
    """创建测试令牌响应"""
    return TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
    )


def test_get_credentials_path_uses_environment_override(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """验证环境变量覆盖凭据路径"""
    expected_path = (
        tmp_path
        / "custom-credentials.json"
    )
    monkeypatch.setenv(
        "DATAMIND_CREDENTIALS_FILE",
        str(expected_path),
    )

    assert get_credentials_path() == expected_path


def test_credential_store_saves_and_loads_tokens(
        tmp_path: Path,
) -> None:
    """验证原子保存和读取令牌"""
    path = tmp_path / "credentials.json"
    store = CredentialStore(
        path
    )

    saved = store.save(
        create_tokens()
    )
    loaded = store.load()

    assert saved.access_token == "access-token"
    assert saved.refresh_token == "refresh-token"
    assert loaded == saved
    assert json.loads(
        path.read_text(
            encoding="utf-8"
        )
    ) == {
        "version": 1,
        "access_token": "access-token",
        "refresh_token": "refresh-token",
    }
    assert list(
        tmp_path.glob(
            ".credentials.json.*.tmp"
        )
    ) == []


def test_credential_store_rejects_invalid_content(
        tmp_path: Path,
) -> None:
    """验证拒绝损坏的凭据文件"""
    path = tmp_path / "credentials.json"
    path.write_text(
        "not-json",
        encoding="utf-8",
    )
    path.chmod(
        0o600
    )

    with pytest.raises(
            CredentialError,
            match="格式无效",
    ):
        CredentialStore(
            path
        ).load()


def test_credential_store_clears_credentials(
        tmp_path: Path,
) -> None:
    """验证删除本地登录凭据"""
    store = CredentialStore(
        tmp_path / "credentials.json"
    )
    store.save(
        create_tokens()
    )

    assert store.clear() is True
    assert store.clear() is False
    assert store.load() is None
