# datamind/console/service.py

"""管理控制台运行服务

通过 BentoML 独立承载内网管理控制台，不占用评分服务 Worker。

核心功能：
  - DatamindConsoleService: 管理控制台服务

使用示例：
  bentoml serve \
    datamind.console.service:DatamindConsoleService \
    --host 0.0.0.0 \
    --port 3100
"""

import bentoml

from datamind.console.app import console_app
from datamind.config import get_settings
from datamind.logging import setup_logging


@bentoml.asgi_app(
    console_app,
    path="/",
    name="datamind-console",
)
@bentoml.service(
    name="datamind_console_service",
    workers=1,
)
class DatamindConsoleService:
    """独立管理控制台服务"""

    def __init__(self) -> None:
        """初始化控制台日志"""
        setup_logging(
            get_settings().logging
        )
