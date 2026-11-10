"""CLI 凭据存储测试.

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
  - test_credential_store_retries_transient_windows_replace_error:
    验证 Windows 短暂占用解除后可更新凭据
  - test_credential_store_preserves_tokens_when_replace_fails:
    验证持续写入失败保留旧凭据并清理临时文件
  - test_credential_store_supports_portable_paths:
    验证普通路径及含空格和中文路径的凭据生命周期
  - test_posix_replace_preserves_open_reader:
    验证 POSIX 打开的旧凭据不阻碍原子更新
"""

import json
import os
import stat
from pathlib import Path

import pytest

import datamind.cli.credentials as credentials_module

from datamind.auth.schemas import TokenResponse
from datamind.cli.credentials import (
    CredentialStore,
    get_credentials_path,
)
from datamind.cli.errors import CredentialError


def create_tokens() -> TokenResponse:
    """创建测试令牌响应."""
    return TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
    )


def test_get_credentials_path_uses_environment_override(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试环境变量覆盖凭据路径."""
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
    """测试原子保存和读取令牌."""
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
    """测试拒绝损坏的凭据文件."""
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
    """测试删除本地登录凭据."""
    store = CredentialStore(
        tmp_path / "credentials.json"
    )
    store.save(
        create_tokens()
    )

    assert store.clear() is True
    assert store.clear() is False
    assert store.load() is None


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_credential_store_retries_transient_windows_replace_error(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        winerror: int,
) -> None:
    """测试 Windows 短暂占用解除后原子更新凭据."""
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.save(create_tokens())
    original = path.read_bytes()
    replace = credentials_module.os.replace
    sleep = credentials_module.time.sleep
    attempts = []
    delays = []

    def temporarily_blocked(source: Path, target: Path) -> None:
        attempts.append(source)
        assert target.read_bytes() == original

        if len(attempts) < 3:
            error = PermissionError("credential file temporarily occupied")
            error.winerror = winerror
            raise error

        replace(source, target)

    def record_sleep(delay: float) -> None:
        delays.append(delay)
        sleep(delay)

    monkeypatch.setattr(credentials_module.os, "replace", temporarily_blocked)
    monkeypatch.setattr(credentials_module.time, "sleep", record_sleep)
    updated = TokenResponse(
        access_token="updated-access",
        refresh_token="updated-refresh",
        expires_in=1800,
    )

    saved = store.save(updated)
    loaded = store.load()

    assert loaded is not None
    assert saved == loaded
    assert loaded.access_token == "updated-access"
    assert 3 <= len(attempts) <= 6
    assert len(delays) == len(attempts) - 1
    assert delays[:2] == [0.05, 0.1]
    assert not list(tmp_path.glob(".credentials.json.*.tmp"))


@pytest.mark.parametrize("winerror, expected_attempts", [(5, 6), (None, 1)])
def test_credential_store_preserves_tokens_when_replace_fails(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        winerror: int | None,
        expected_attempts: int,
) -> None:
    """测试持续写入失败保留旧凭据并清理临时文件."""
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.save(create_tokens())
    original = path.read_bytes()
    attempts = []
    delays = []

    def denied(source: Path, _target: Path) -> None:
        attempts.append(source)
        error = PermissionError("credential file access denied")

        if winerror is not None:
            error.winerror = winerror

        raise error

    monkeypatch.setattr(credentials_module.os, "replace", denied)
    monkeypatch.setattr(credentials_module.time, "sleep", delays.append)

    with pytest.raises(CredentialError, match="凭据保存失败"):
        store.save(create_tokens())

    assert path.read_bytes() == original
    assert len(attempts) == expected_attempts
    assert sum(delays) <= 1.55
    assert not list(tmp_path.glob(".credentials.json.*.tmp"))


@pytest.mark.parametrize(
    "directory, filename",
    [("session", "credentials.json"), ("登录 会话", "凭据 文件.json")],
)
def test_credential_store_supports_portable_paths(
        tmp_path: Path,
        directory: str,
        filename: str,
) -> None:
    """测试普通及含空格和中文路径的跨平台凭据生命周期."""
    path = tmp_path / directory / filename
    store = CredentialStore(path)
    original = store.save(create_tokens())

    assert store.load() == original

    updated = TokenResponse(
        access_token="updated-access",
        refresh_token="updated-refresh",
        expires_in=1800,
    )
    saved = store.save(updated)

    assert store.load() == saved
    assert not list(path.parent.glob(".*.tmp"))

    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    assert store.clear()
    assert store.load() is None


@pytest.mark.skipif(os.name != "posix", reason="POSIX 原子替换语义")
def test_posix_replace_preserves_open_reader(
        tmp_path: Path,
) -> None:
    """测试 POSIX 打开的旧凭据不阻碍原子更新."""
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.save(create_tokens())
    updated = TokenResponse(
        access_token="updated-access",
        refresh_token="updated-refresh",
        expires_in=1800,
    )

    with path.open(encoding="utf-8") as reader:
        saved = store.save(updated)

        assert store.load() == saved
        assert json.load(reader)["access_token"] == "access-token"
