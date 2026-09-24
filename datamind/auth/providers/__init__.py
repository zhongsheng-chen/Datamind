"""本地认证提供方.

统一导出本地用户名密码认证所需的凭证、身份和提供方。

核心功能：
  - BaseAuthProvider: 本地认证提供方抽象基类
  - PasswordCredentials: 用户名密码凭证
  - ProviderIdentity: 认证成功后的身份信息
  - LocalProviderConfig: 本地认证配置
  - LocalAuthProvider: 本地密码认证提供方
"""

from datamind.auth.providers.base import (
    BaseAuthProvider,
    PasswordCredentials,
    ProviderCredentials,
    ProviderIdentity,
)
from datamind.auth.providers.local import (
    LocalAuthProvider,
    LocalProviderConfig,
)

__all__ = [
    "BaseAuthProvider",
    "PasswordCredentials",
    "ProviderCredentials",
    "ProviderIdentity",
    "LocalProviderConfig",
    "LocalAuthProvider",
]
