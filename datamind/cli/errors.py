"""CLI 异常定义.

统一定义命令行工具本地状态管理过程中的异常类型。

核心功能：
  - CredentialError: CLI 凭据读写异常

使用示例：
  from datamind.cli.errors import CredentialError

  raise CredentialError(
      "CLI 凭据文件格式无效"
  )
"""


class CredentialError(
    OSError
):
    """CLI 凭据读写异常."""


__all__ = [
    "CredentialError",
]
