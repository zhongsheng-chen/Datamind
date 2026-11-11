"""CLI 日志策略测试.

验证单次命令的 JSON 输出与文件日志记录。

核心功能：
  - test_cli_logging_keeps_stdout_clean:
    验证标准输出为有效 JSON，文件日志遵循配置的日志级别
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import structlog
import typer
from typer.testing import CliRunner

import datamind.cli.common as common_module
import datamind.cli.logging as logging_module
import datamind.cli.main as main_module
from datamind.cli.common import CLIContext
from datamind.cli.logging import setup_cli_logging
from datamind.config.logging import LoggingConfig
from datamind.constants import Environment
from datamind.constants.logging_format import LogFormat
from datamind.constants.logging_level import LogLevel
from datamind.logging import shutdown_logging


@pytest.mark.parametrize("level", [LogLevel.INFO, LogLevel.DEBUG])
def test_cli_logging_keeps_stdout_clean(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        level: LogLevel,
) -> None:
    """测试单次命令保持标准输出为有效 JSON 并保留文件日志."""
    config = LoggingConfig(
        level=level,
        console_level=LogLevel.DEBUG,
        format=LogFormat.TEXT,
        dir=tmp_path,
        filename="cli.log",
    )
    monkeypatch.setitem(vars(logging_module), "get_logging_config", lambda: config)
    monkeypatch.setitem(vars(main_module), "setup_cli_logging", setup_cli_logging)
    settings = SimpleNamespace(
        logging=config,
        auth=SimpleNamespace(enabled=False),
        common=SimpleNamespace(environment=Environment.DEVELOPMENT),
    )
    monkeypatch.setitem(vars(common_module), "get_settings", lambda: settings)
    app = typer.Typer()
    app.callback()(main_module.main)

    @app.command()
    def probe() -> None:
        """模拟记录日志并输出 JSON 的命令."""
        async def run() -> None:
            async with CLIContext(ip="127.0.0.1", hostname="test-host"):
                logger = structlog.get_logger("datamind.cli.probe")
                logger.info("操作记录")
                logger.debug("诊断事件")
                typer.echo('{"success": true}')

        asyncio.run(run())

    try:
        result = CliRunner().invoke(app, ["probe"])
        assert result.exit_code == 0, result.exception
        assert json.loads(result.stdout) == {"success": True}
        assert result.stderr == ""
        contents = (tmp_path / "cli.log").read_text(encoding="utf-8")
        assert "操作记录" in contents
        assert ("诊断事件" in contents) is (level == LogLevel.DEBUG)
        assert config.enable_console is True
    finally:
        shutdown_logging()
