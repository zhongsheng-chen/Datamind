"""管理控制台健康检查.

检查管理控制台是否可以接收请求。

核心功能：
  - is_console_healthy: 检查配置的控制台健康检查地址

使用方式：
  datamind console healthcheck
"""

import os
import urllib.request


_REQUEST_TIMEOUT_SECONDS = 3.0


def is_console_healthy() -> bool:
    """检查管理控制台是否健康."""
    url = os.environ.get("DATAMIND_HEALTHCHECK_URL")
    if not url:
        return False

    try:
        with urllib.request.urlopen(
                url,
                timeout=_REQUEST_TIMEOUT_SECONDS,
        ):
            return True
    except (OSError, ValueError):
        return False

