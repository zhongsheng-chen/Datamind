"""本地认证提供方基础定义.

定义用户名密码凭证、认证身份和本地认证提供方接口。

核心功能：
  - PasswordCredentials: 用户名密码凭证
  - ProviderIdentity: 本地认证返回的身份信息
  - BaseAuthProvider: 本地认证提供方抽象基类

使用示例：
  from datamind.auth.providers import PasswordCredentials

  identity = await provider.authenticate(
      PasswordCredentials(
          username="alice",
          password="P@ssw1rd",
      )
  )
"""

from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import (
    dataclass,
    field,
)
from datetime import datetime
from types import MappingProxyType
from typing import (
    Any,
    Mapping,
    TypeAlias,
)


@dataclass(
    slots=True,
    frozen=True,
)
class PasswordCredentials:
    """用户名密码凭证."""

    username: str
    password: str = field(
        repr=False
    )

    def __post_init__(
            self,
    ) -> None:
        """校验并规范化凭证."""
        username = self.username.strip()

        if username == "":
            raise ValueError(
                "username 不能为空"
            )

        if self.password == "":
            raise ValueError(
                "password 不能为空"
            )

        object.__setattr__(
            self,
            "username",
            username,
        )


ProviderCredentials: TypeAlias = PasswordCredentials


@dataclass(
    slots=True,
    frozen=True,
)
class ProviderIdentity:
    """本地认证返回的身份信息."""

    subject: str
    username: str
    display_name: str | None = None
    email: str | None = None
    claims: Mapping[str, Any] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def __post_init__(
            self,
    ) -> None:
        """校验并规范化身份信息."""
        subject = self.subject.strip()
        username = self.username.strip()

        if subject == "":
            raise ValueError(
                "subject 不能为空"
            )

        if username == "":
            raise ValueError(
                "username 不能为空"
            )

        display_name = (
            self.display_name.strip()
            if self.display_name is not None
            else None
        )
        email = (
            self.email.strip()
            if self.email is not None
            else None
        )

        object.__setattr__(
            self,
            "subject",
            subject,
        )
        object.__setattr__(
            self,
            "username",
            username,
        )
        object.__setattr__(
            self,
            "display_name",
            display_name or None,
        )
        object.__setattr__(
            self,
            "email",
            email or None,
        )
        object.__setattr__(
            self,
            "claims",
            MappingProxyType(
                dict(
                    self.claims
                )
            ),
        )


class BaseAuthProvider(
    ABC
):
    """本地认证提供方抽象基类."""

    @abstractmethod
    async def authenticate(
            self,
            credentials: PasswordCredentials,
            *,
            current_time: datetime | None = None,
    ) -> ProviderIdentity:
        """校验凭证并返回身份信息."""


__all__ = [
    "PasswordCredentials",
    "ProviderCredentials",
    "ProviderIdentity",
    "BaseAuthProvider",
]
