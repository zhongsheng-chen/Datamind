# datamind/cli/common.py

"""CLI 公共模块

提供 CLI 命令的通用上下文管理。

核心功能：
  - cli_context: CLI 上下文管理器

使用示例：
  from datamind.cli.common import cli_context

  async with cli_context(
      user="alice",
      ip="10.0.0.1",
      source="cli",
      verbose=True,
      enable_audit=True
  ):
      # 执行 CLI 命令
"""

import uuid

from datamind.utils.network import get_host_ip, get_hostname
from datamind.audit.dispatcher import get_queue
from datamind.audit.worker import start_audit_worker, stop_audit_worker
from datamind.config import get_settings
from datamind.context.scope import context_scope
from datamind.logging import setup_logging


class CLIContext:
    """CLI 上下文"""

    def __init__(
        self,
        *,
        user: str = "system",
        ip: str | None = None,
        hostname: str | None = None,
        source: str = "cli",
        verbose: bool = False,
        enable_audit: bool = False,
    ):
        """初始化 CLI 上下文

        参数：
            user: 操作人
            ip: 客户端 IP 地址，默认自动获取
            hostname: 客户端名称，默认自动获取
            source: 请求来源
            verbose: 是否显示调试日志
            enable_audit: 是否启用审计
        """
        self.user = user
        self.ip = ip or get_host_ip()
        self.hostname = hostname or get_hostname()
        self.source = source
        self.verbose = verbose
        self.enable_audit = enable_audit

        self.settings = get_settings()

        self.scope = None
        self.audit_started = False

    async def __aenter__(self):
        """进入上下文

        初始化日志系统、启动审计 Worker（如启用）、
        创建上下文作用域。

        返回：
            CLIContext 实例
        """
        # 配置日志
        base_config = self.settings.logging

        logging_config = base_config.model_copy(
            update={
                "enable_console": self.verbose,
                "enable_file": True,
            }
        )

        setup_logging(logging_config)

        # 启动审计 Worker
        if self.enable_audit:
            await start_audit_worker()
            self.audit_started = True

        # 创建上下文作用域
        self.scope = context_scope(
            user=self.user,
            ip=self.ip,
            hostname=self.hostname,
            trace_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            source=self.source,
        )
        self.scope.__enter__()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        """退出上下文

        等待审计队列处理完成、停止审计 Worker，
        最后恢复上下文作用域。
        """
        try:
            if self.audit_started:
                await get_queue().join()
                await stop_audit_worker()
        finally:
            if self.scope is not None:
                self.scope.__exit__(exc_type, exc, tb)


def cli_context(
    *,
    user: str = "system",
    ip: str | None = None,
    source: str = "cli",
    verbose: bool = False,
    enable_audit: bool = False,
) -> CLIContext:
    """CLI 上下文管理器

    参数：
        user: 操作人
        ip: 客户端 IP
        source: 请求来源
        verbose: 是否显示调试日志
        enable_audit: 是否启用审计

    返回：
        CLIContext 实例
    """
    return CLIContext(
        user=user,
        ip=ip,
        source=source,
        verbose=verbose,
        enable_audit=enable_audit,
    )