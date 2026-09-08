"""CLI 终端输出

统一命令状态、警告、错误、常规内容和 JSON 的输出方式。

核心功能：
  - CLIConsole.info: 输出成功或提示信息
  - CLIConsole.warning: 输出警告信息
  - CLIConsole.error: 输出文本或 JSON 错误
  - CLIConsole.print: 输出常规内容或 Rich 对象
  - CLIConsole.print_json: 输出 JSON
"""

from rich.console import Console


class CLIConsole(
    Console
):
    """提供统一语义输出的 CLI Console"""

    def __init__(self) -> None:
        """初始化标准输出和标准错误 Console"""
        super().__init__()
        self._error_console = Console(
            stderr=True
        )

    def info(
            self,
            message: str,
    ) -> None:
        """输出成功或提示信息"""
        self.print(
            message,
            style="green",
        )

    def warning(
            self,
            message: str,
    ) -> None:
        """输出警告信息"""
        self.print(
            message,
            style="yellow",
        )

    def error(
            self,
            message: str,
            *,
            output_format: str = "text",
            error_type: str | None = None,
    ) -> None:
        """向标准错误流输出文本或 JSON 错误"""
        if output_format == "json":
            payload = {
                "success": False,
                "error": message,
            }

            if error_type is not None:
                payload["error_type"] = error_type

            self._error_console.print_json(
                data=payload,
                ensure_ascii=False,
            )
            return

        self._error_console.print(
            message,
            style="red",
        )


__all__ = [
    "CLIConsole",
]
