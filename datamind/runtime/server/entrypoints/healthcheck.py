"""运行时服务健康检查.

检查运行时服务是否已准备好接收请求。

运行方式：
  python -m datamind.runtime.server.entrypoints.healthcheck
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


def main() -> None:
    """通过进程退出码输出健康检查结果."""
    raise SystemExit(0 if is_runtime_ready() else 1)


if __name__ == "__main__":
    main()
