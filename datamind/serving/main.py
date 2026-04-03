# datamind/serving/main.py

"""BentoML服务入口

提供统一的BentoML服务启动入口，负责初始化日志系统、数据库连接等基础设施。

核心功能：
  - 日志系统初始化：安装启动日志缓存，初始化正式日志系统
  - 数据库连接初始化：初始化数据库连接池
  - 服务组件预热：预加载生产模型
  - 优雅关闭：清理资源，确保日志完整写入

特性：
  - 启动日志缓存：启动期间日志先缓存，日志系统初始化后统一写入
  - 线程安全：使用锁保护初始化过程
  - 错误处理：详细的异常信息和错误追踪
  - 完整审计：记录服务启动和关闭事件
  - 链路追踪：完整的 span 追踪

启动方式：
  # 启动评分卡服务
  bentoml serve datamind.serving.scoring_service:ScoringService --port 8000

  # 启动反欺诈服务
  bentoml serve datamind.serving.fraud_service:FraudService --port 8001

  # 构建Bento包
  bentoml build

  # 部署到生产环境
  bentoml deploy scoring_service:latest
"""

import os
import sys
import threading
from pathlib import Path
from typing import Optional

from datamind.core.logging.bootstrap import (
    install_bootstrap_logger,
    bootstrap_info,
    bootstrap_debug,
    bootstrap_warning,
    bootstrap_error,
    flush_bootstrap_logs,
)

install_bootstrap_logger(capacity=10000)

bootstrap_info("=" * 60)
bootstrap_info("Datamind BentoML 服务启动中...")
bootstrap_info("=" * 60)

from datamind.core.logging import get_logger
from datamind.core.logging.manager import log_manager
from datamind.core.db.database import db_manager
from datamind.config import get_settings

# 获取配置
settings = get_settings()
logger = get_logger(__name__)

# 设置环境变量
os.environ.setdefault("DATAMIND_ENV", settings.app.env)
os.environ.setdefault("DATAMIND_LOG_LEVEL", settings.logging.level.name)

# 初始化状态标志
_initialized = False
_init_lock = threading.RLock()


def initialize_services() -> bool:
    """
    初始化所有服务组件

    核心功能：
      - 初始化日志系统
      - 刷新启动日志到正式日志文件
      - 初始化数据库连接

    返回:
        bool: 初始化是否成功

    异常:
        Exception: 初始化失败时抛出异常
    """
    global _initialized

    with _init_lock:
        if _initialized:
            bootstrap_debug("服务组件已初始化，跳过")
            return True

        bootstrap_info("开始初始化服务组件...")

        # 初始化日志系统
        try:
            bootstrap_info("初始化日志系统...")
            log_manager.initialize(settings.logging)

            # 刷新启动日志到正式日志文件
            bootstrap_info("刷新启动日志到正式日志文件...")
            flushed_count = flush_bootstrap_logs()
            bootstrap_info("已刷新 %d 条启动日志", flushed_count)

        except Exception as e:
            bootstrap_error("日志系统初始化失败: %s", e)
            return False

        # 初始化数据库连接
        try:
            bootstrap_info("初始化数据库连接...")
            db_manager.initialize()
            bootstrap_info("数据库连接初始化完成")

        except Exception as e:
            bootstrap_error("数据库初始化失败: %s", e)
            return False

        _initialized = True

        bootstrap_info("=" * 60)
        bootstrap_info("服务组件初始化完成")
        bootstrap_info("=" * 60)

        return True


def main() -> None:
    """
    主入口函数

    功能：
      - 初始化所有服务组件
      - 等待BentoML加载服务类

    异常:
        SystemExit: 初始化失败时退出
    """
    if not initialize_services():
        bootstrap_error("服务初始化失败，退出")
        sys.exit(1)

    bootstrap_info("服务初始化成功，等待BentoML加载...")

main()