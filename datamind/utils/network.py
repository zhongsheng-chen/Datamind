"""网络工具.

提供当前主机 IP 地址和主机名获取能力。

核心功能：
  - get_host_ip: 获取当前主机 IP
  - get_hostname: 获取当前主机名

使用示例：
  from datamind.utils.network import (
      get_host_ip,
      get_hostname,
  )

  # 获取当前主机 IP
  ip = get_host_ip()

  # 获取当前主机名
  hostname = get_hostname()
"""

import socket
from typing import Final


_PROBE_ADDRESS: Final[tuple[str, int]] = (
    "8.8.8.8",
    80,
)
_LOOPBACK_ADDRESS: Final[str] = "127.0.0.1"


def get_host_ip() -> str:
    """获取当前主机 IP.

    通过 UDP Socket 判断当前主机用于对外通信的 IP 地址。
    该操作不会实际向探测地址发送数据。

    返回：
        当前主机 IP；获取失败时返回 127.0.0.1

    注意：
        返回的是当前主机出口 IP，
        不一定是公网 IP。
    """
    try:
        with socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
        ) as sock:
            sock.connect(
                _PROBE_ADDRESS
            )

            return sock.getsockname()[0]

    except OSError:
        return _LOOPBACK_ADDRESS


def get_hostname() -> str:
    """获取当前主机名.

    返回：
        当前主机名
    """
    return socket.gethostname()
