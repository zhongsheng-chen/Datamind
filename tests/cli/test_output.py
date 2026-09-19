"""CLI 终端输出测试

验证常规信息与错误信息的输出边界。

核心功能：
  - test_cli_console_writes_status_to_stdout:
    验证状态和常规内容写入标准输出
  - test_cli_console_writes_errors_to_stderr:
    验证错误信息写入标准错误
"""

import json

import pytest

from datamind.cli.output import CLIConsole


def test_cli_console_writes_status_to_stdout(
        capsys: pytest.CaptureFixture[str],
) -> None:
    """测试状态和常规内容输出到标准输出"""
    console = CLIConsole()

    console.info("操作成功")
    console.warning("请确认配置")
    console.print("详情")
    console.print_json(
        data={
            "success": True,
        }
    )

    captured = capsys.readouterr()

    assert "操作成功" in captured.out
    assert "请确认配置" in captured.out
    assert "详情" in captured.out
    assert '"success": true' in captured.out
    assert captured.err == ""


@pytest.mark.parametrize(
    "output_format",
    [
        "text",
        "json",
    ],
)
def test_cli_console_writes_errors_to_stderr(
        capsys: pytest.CaptureFixture[str],
        output_format: str,
) -> None:
    """测试文本和 JSON 错误输出到标准错误"""
    console = CLIConsole()

    console.error(
        "操作失败",
        output_format=output_format,
        error_type="ValueError",
    )

    captured = capsys.readouterr()

    assert captured.out == ""

    if output_format == "text":
        assert "操作失败" in captured.err
        return

    payload = json.loads(
        captured.err
    )
    assert payload == {
        "success": False,
        "error": "操作失败",
        "error_type": "ValueError",
    }
