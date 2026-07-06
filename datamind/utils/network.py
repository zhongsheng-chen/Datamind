# datamind/utils/network.py

"""网络工具

提供网络相关辅助能力。

核心功能：
  - get_host_ip: 获取当前主机 IP
  - get_hostname: 获取当前主机名

使用示例：
    from datamind.utils.network import (
        get_host_ip,
        get_hostname,
    )

    ip = get_host_ip()
    hostname = get_hostname()
"""

import socket


def get_host_ip() -> str:
    """获取当前主机 IP

    获取当前主机用于对外通信的 IP 地址。

    返回：
        当前主机 IP

    注意：
        返回的是当前主机出口 IP，
        不一定是公网 IP。
    """
    try:
        with socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
        ) as sock:
            sock.connect(("8.8.8.8", 80))

            return sock.getsockname()[0]

    except OSError:
        return "127.0.0.1"


def get_hostname() -> str:
    """获取当前主机名

    返回：
        当前主机名
    """
    return socket.gethostname()
