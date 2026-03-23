# datamind/core/security/__init__.py

"""安全模块

提供密码安全、API密钥生成、JWT令牌等核心安全功能。

模块组成：
  - password: 密码工具，提供密码哈希、验证、随机密码生成
  - jwt: JWT令牌，提供JWT的创建、验证、刷新功能
  - api_key: API密钥工具，提供API密钥生成、验证、哈希功能

功能特性：
  - 密码安全：使用bcrypt算法，支持可配置加密轮数
  - 密码策略：支持密码复杂度验证、过期时间管理
  - JWT认证：支持HS256/RS256算法，可配置过期时间
  - API密钥：支持密钥前缀、过期时间、IP白名单
  - 安全审计：记录所有认证事件和异常尝试
"""

from datamind.core.security.password import (
    hash_password,
    verify_password,
    generate_random_password,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)

__all__ = [
    'hash_password',
    'verify_password',
    'generate_random_password',
    'generate_api_key',
    'hash_api_key',
    'verify_api_key',
]