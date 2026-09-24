"""网络工具测试.

验证主机 IP 获取、网络异常回退、Socket 参数和主机名获取行为。

核心功能：
  - test_get_host_ip_returns_socket_address:
    验证返回当前主机用于对外通信的 IP 地址
  - test_get_host_ip_returns_loopback_when_connect_fails:
    验证连接探测地址失败时回退到回环地址
  - test_get_host_ip_returns_loopback_when_getsockname_fails:
    验证读取主机地址失败时回退到回环地址
  - test_get_host_ip_returns_loopback_when_socket_creation_fails:
    验证创建 Socket 失败时回退到回环地址
  - test_get_hostname_returns_socket_hostname:
    验证返回当前主机名
"""

import socket
from types import TracebackType
from typing import Any

import pytest

import datamind.utils.network as network_utils


class FakeSocket:
    """测试用 Socket 对象."""

    def __init__(
            self,
            *,
            ip: str = "192.168.1.100",
            connect_error: OSError | None = None,
            getsockname_error: OSError | None = None,
    ) -> None:
        self.ip = ip
        self.connect_error = connect_error
        self.getsockname_error = getsockname_error
        self.connected_address: tuple[str, int] | None = None
        self.entered = False
        self.exited = False

    def __enter__(
            self,
    ) -> "FakeSocket":
        self.entered = True

        return self

    def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
    ) -> None:
        _ = (
            exc_type,
            exc_value,
            traceback,
        )
        self.exited = True

    def connect(
            self,
            address: tuple[str, int],
    ) -> None:
        self.connected_address = address

        if self.connect_error is not None:
            raise self.connect_error

    def getsockname(
            self,
    ) -> tuple[str, int]:
        if self.getsockname_error is not None:
            raise self.getsockname_error

        return (
            self.ip,
            54321,
        )


def test_get_host_ip_returns_socket_address(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试返回用于对外通信的主机 IP."""
    fake_socket = FakeSocket(
        ip="192.168.1.100"
    )
    socket_arguments: list[
        tuple[int, int]
    ] = []

    def create_socket(
            family: int,
            socket_type: int,
    ) -> FakeSocket:
        socket_arguments.append(
            (
                family,
                socket_type,
            )
        )

        return fake_socket

    monkeypatch.setitem(
        vars(network_utils.socket),
        "socket",
        create_socket,
    )

    result = network_utils.get_host_ip()

    assert result == "192.168.1.100"
    assert socket_arguments == [
        (
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ),
    ]
    assert fake_socket.connected_address == (
        "8.8.8.8",
        80,
    )
    assert fake_socket.entered is True
    assert fake_socket.exited is True


def test_get_host_ip_returns_loopback_when_connect_fails(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试连接失败时回退到回环地址."""
    fake_socket = FakeSocket(
        connect_error=OSError(
            "network unavailable"
        )
    )

    monkeypatch.setitem(
        vars(network_utils.socket),
        "socket",
        lambda *args: fake_socket,
    )

    result = network_utils.get_host_ip()

    assert result == "127.0.0.1"
    assert fake_socket.connected_address == (
        "8.8.8.8",
        80,
    )
    assert fake_socket.entered is True
    assert fake_socket.exited is True


def test_get_host_ip_returns_loopback_when_getsockname_fails(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试读取主机地址失败时回退到回环地址."""
    fake_socket = FakeSocket(
        getsockname_error=OSError(
            "address unavailable"
        )
    )

    monkeypatch.setitem(
        vars(network_utils.socket),
        "socket",
        lambda *args: fake_socket,
    )

    result = network_utils.get_host_ip()

    assert result == "127.0.0.1"
    assert fake_socket.entered is True
    assert fake_socket.exited is True


def test_get_host_ip_returns_loopback_when_socket_creation_fails(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建 Socket 失败时回退到回环地址."""
    def create_socket(
            *args: Any,
    ) -> FakeSocket:
        _ = args

        raise OSError(
            "socket unavailable"
        )

    monkeypatch.setitem(
        vars(network_utils.socket),
        "socket",
        create_socket,
    )

    assert (
        network_utils.get_host_ip()
        == "127.0.0.1"
    )


def test_get_hostname_returns_socket_hostname(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试返回当前主机名."""
    monkeypatch.setitem(
        vars(network_utils.socket),
        "gethostname",
        lambda: "datamind-host",
    )

    assert (
        network_utils.get_hostname()
        == "datamind-host"
    )
