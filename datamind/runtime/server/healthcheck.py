"""运行时服务健康检查.

检查运行时服务是否已准备好接收请求。

使用方式：
  datamind service healthcheck
"""

import os
import urllib.request


_REQUEST_TIMEOUT_SECONDS = 3.0


def is_runtime_ready() -> bool:
    """检查运行时服务是否就绪."""
    url = os.environ.get("DATAMIND_HEALTHCHECK_URL")
    if not url:
        return False

    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
                request,
                timeout=_REQUEST_TIMEOUT_SECONDS,
        ):
            return True
    except (OSError, ValueError):
        return False

