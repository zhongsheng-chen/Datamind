"""单次 CLI 命令的日志策略.

命令结果使用标准输出，内部诊断按环境配置写入文件日志。

核心功能：
  - setup_cli_logging: 初始化单次命令日志，关闭控制台日志输出并沿用文件日志配置

使用示例：
  from datamind.cli.logging import setup_cli_logging

  setup_cli_logging()
"""

from datamind.config import get_logging_config
from datamind.logging import setup_logging


def setup_cli_logging() -> None:
    """配置单次命令的诊断输出，保留文件日志策略."""
    config = get_logging_config()
    config = config.model_copy(update={"enable_console": False})

    setup_logging(config)
