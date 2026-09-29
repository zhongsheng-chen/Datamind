"""管理控制台健康检查.

检查管理控制台是否可以接收请求。

运行方式：
  python -m datamind.console.entrypoints.healthcheck
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


def main() -> None:
    """通过进程退出码输出健康检查结果."""
    raise SystemExit(0 if is_console_healthy() else 1)


if __name__ == "__main__":
    main()
