# Datamind/datamind/cli/__init__.py

"""Datamind 命令行工具

提供完整的命令行接口，用于管理模型、审计日志、配置、健康检查等。

模块组成：
  - main: CLI 主入口，定义命令组
  - commands: 各子命令模块
    - model: 模型管理命令（注册、激活、停用、加载等）
    - audit: 审计日志命令（查询、导出）
    - config: 配置管理命令（查看、验证、重载）
    - health: 健康检查命令（API、数据库、Redis）
    - log: 日志管理命令（查看、搜索、导出、清理）
    - version: 版本信息命令
"""

from datamind.cli.main import cli

__all__ = ['cli']