# datamind/cli/common.py

"""CLI 公共模块

提供 CLI 命令的通用上下文管理。

核心功能：
  - cli_context: CLI 上下文管理器

使用示例：
  from datamind.cli.common import cli_context

  with cli_context(verbose=True, enable_audit=True):
      # 执行 CLI 命令
"""

import uuid

from datamind.config import get_settings
from datamind.logging import setup_logging
from datamind.context.scope import context_scope
from datamind.audit.worker import start_audit_worker, stop_audit_worker
from datamind.audit.dispatcher import get_queue


class CLIContext:
    """CLI 上下文"""

    def __init__(self, verbose: bool = False, enable_audit: bool = False):
        """初始化 CLI 上下文

        参数：
            verbose: 是否显示调试日志
            enable_audit: 是否启用审计
        """
        self.verbose = verbose
        self.enable_audit = enable_audit
        self.settings = get_settings()

        self.scope = None
        self.audit_started = False

    async def __aenter__(self):
        """进入上下文

        初始化日志系统、启动审计 Worker（如启用）、创建上下文作用域。

        返回：
            CLIContext 实例
        """
        # 配置日志级别
        logging_config = (
            self.settings.logging
            if self.verbose
            else self.settings.logging.model_copy(update={"level": "ERROR"})
        )
        setup_logging(logging_config)

        # 启动审计 Worker
        if self.enable_audit:
            await start_audit_worker()
            self.audit_started = True

        # 创建上下文作用域
        self.scope = context_scope(
            user="system",
            ip="127.0.0.1",
            trace_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            source="cli",
        )
        self.scope.__enter__()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        """退出上下文

        恢复上下文、等待审计队列处理完成、停止审计 Worker。
        """
        self.scope.__exit__(exc_type, exc, tb)

        # 等待队列处理完成后，停止审计 Worker
        if self.audit_started:
            await get_queue().join()
            await stop_audit_worker()


def cli_context(verbose: bool = False, enable_audit: bool = False):
    """CLI 上下文管理器

    参数：
        verbose: 是否显示调试日志
        enable_audit: 是否启用审计

    返回：
        CLIContext 实例
    """
    return CLIContext(verbose=verbose, enable_audit=enable_audit)