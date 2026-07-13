# datamind/cli/credentials.py

"""CLI 凭据存储

提供用户登录凭据的读写能力。

核心功能：
  - CLICredentials: CLI 登录凭据
  - CredentialStore.load: 读取本地登录凭据
  - CredentialStore.save: 原子保存本地登录凭据
  - CredentialStore.clear: 删除本地登录凭据

使用示例：
  from datamind.cli.credentials import CredentialStore

  store = CredentialStore()
  credentials = store.load()

  if credentials is not None:
      print(credentials.access_token)
"""

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from datamind.auth.schemas import TokenResponse
from datamind.cli.errors import CredentialError


_CREDENTIALS_VERSION = 1


@dataclass(
    frozen=True,
    slots=True,
)
class CLICredentials:
    """CLI 登录凭据"""

    access_token: str
    refresh_token: str | None


def get_credentials_path() -> Path:
    """获取当前用户的 CLI 凭据文件路径"""
    configured_path = os.environ.get(
        "DATAMIND_CREDENTIALS_FILE",
        "",
    ).strip()

    if configured_path:
        return Path(
            configured_path
        ).expanduser()

    if os.name == "nt":
        app_data = os.environ.get(
            "APPDATA",
            "",
        ).strip()
        config_root = (
            Path(app_data)
            if app_data
            else (
                Path.home()
                / "AppData"
                / "Roaming"
            )
        )
    else:
        xdg_config_home = os.environ.get(
            "XDG_CONFIG_HOME",
            "",
        ).strip()
        config_root = (
            Path(xdg_config_home).expanduser()
            if xdg_config_home
            else Path.home() / ".config"
        )

    return (
        config_root
        / "datamind"
        / "credentials.json"
    )


class CredentialStore:
    """CLI 凭据存储"""

    def __init__(
            self,
            path: Path | None = None,
    ) -> None:
        """初始化凭据存储"""
        self.path = (
            path
            if path is not None
            else get_credentials_path()
        )

    def load(
            self,
    ) -> CLICredentials | None:
        """读取本地登录凭据"""
        if not self.path.exists():
            return None

        if self.path.is_symlink():
            raise CredentialError(
                "CLI 凭据文件不能是符号链接"
            )

        if not self.path.is_file():
            raise CredentialError(
                "CLI 凭据路径不是普通文件"
            )

        self._validate_permissions()

        try:
            raw_data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise CredentialError(
                "CLI 凭据文件格式无效，"
                "请重新登录"
            ) from exc

        if not isinstance(
                raw_data,
                dict,
        ):
            raise CredentialError(
                "CLI 凭据文件格式无效，"
                "请重新登录"
            )

        version = raw_data.get(
            "version"
        )
        access_token = raw_data.get(
            "access_token"
        )
        refresh_token = raw_data.get(
            "refresh_token"
        )

        if version != _CREDENTIALS_VERSION:
            raise CredentialError(
                "CLI 凭据文件版本不受支持，"
                "请重新登录"
            )

        if (
                not isinstance(
                    access_token,
                    str,
                )
                or not access_token
        ):
            raise CredentialError(
                "CLI 凭据文件缺少访问令牌，"
                "请重新登录"
            )

        if (
                refresh_token is not None
                and not isinstance(
                    refresh_token,
                    str,
                )
        ):
            raise CredentialError(
                "CLI 凭据文件中的刷新令牌无效，"
                "请重新登录"
            )

        return CLICredentials(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def save(
            self,
            tokens: TokenResponse,
    ) -> CLICredentials:
        """原子保存登录凭据"""
        credentials = CLICredentials(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        )
        payload: dict[str, object] = {
            "version": _CREDENTIALS_VERSION,
            "access_token": credentials.access_token,
            "refresh_token": credentials.refresh_token,
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._protect_directory()

        temporary_path = self._write_temporary(
            payload
        )

        try:
            self._protect_file(
                temporary_path
            )
            os.replace(
                temporary_path,
                self.path,
            )
            self._protect_file(
                self.path
            )
        except OSError as exc:
            raise CredentialError(
                f"CLI 凭据保存失败：{exc}"
            ) from exc
        finally:
            if (
                    temporary_path.exists()
            ):
                temporary_path.unlink()

        return credentials

    def clear(
            self,
    ) -> bool:
        """删除本地登录凭据"""
        if not self.path.exists():
            return False

        if self.path.is_symlink():
            raise CredentialError(
                "CLI 凭据文件不能是符号链接"
            )

        try:
            self.path.unlink()
        except OSError as exc:
            raise CredentialError(
                f"CLI 凭据删除失败：{exc}"
            ) from exc

        return True

    def _write_temporary(
            self,
            payload: dict[str, object],
    ) -> Path:
        """将凭据写入同目录临时文件"""
        temporary_file = NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = Path(
            temporary_file.name
        )

        try:
            with temporary_file:
                json.dump(
                    payload,
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                )
                temporary_file.write(
                    "\n"
                )
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )
        except (
            OSError,
            TypeError,
        ) as exc:
            temporary_path.unlink(
                missing_ok=True
            )
            raise CredentialError(
                f"CLI 凭据保存失败：{exc}"
            ) from exc

        return temporary_path

    def _validate_permissions(
            self,
    ) -> None:
        """校验 POSIX 凭据文件权限"""
        if os.name == "nt":
            return

        mode = stat.S_IMODE(
            self.path.stat().st_mode
        )

        if mode & 0o077:
            raise CredentialError(
                "CLI 凭据文件权限过宽，"
                f"请执行 chmod 600 {self.path}"
            )

    def _protect_directory(
            self,
    ) -> None:
        """保护 POSIX 凭据目录"""
        if os.name != "nt":
            self.path.parent.chmod(
                0o700
            )

    @staticmethod
    def _protect_file(
            path: Path,
    ) -> None:
        """保护 POSIX 凭据文件"""
        if os.name != "nt":
            path.chmod(
                0o600
            )


__all__ = [
    "CLICredentials",
    "CredentialStore",
    "get_credentials_path",
]
