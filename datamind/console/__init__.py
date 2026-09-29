"""内网管理控制台.

提供独立于评分服务的浏览器管理界面、实时通知和只读管理接口。

核心功能：
  - console_app: 管理控制台 ASGI 应用
  - DatamindConsoleService: BentoML 管理控制台服务

使用示例：
  bentoml serve \
    datamind.console.service:DatamindConsoleService \
    --host 0.0.0.0 \
    --port 8701
"""

from datamind.console.app import console_app
from datamind.console.service import DatamindConsoleService

__all__ = [
    "console_app",
    "DatamindConsoleService",
]
