# Datamind/datamind/core/domain/__init__.py

"""领域模型模块

包含所有领域枚举、值对象和验证函数，提供核心业务规则的统一入口。

模块组成：
  - enums: 领域枚举定义（任务类型、模型类型、框架、状态等）
  - validation: 框架-模型兼容性验证（核心业务规则）
"""

from datamind.core.domain.enums import (
    TaskType,
    ModelType,
    Framework,
    ModelStatus,
    AuditAction,
    DeploymentEnvironment,
    ABTestStatus,
)

from datamind.core.domain.validation import (
    FRAMEWORK_MODEL_COMPATIBILITY,
    is_compatible,
    get_supported_models,
    get_supported_frameworks,
    validate_or_raise,
)

__all__ = [
    'TaskType',
    'ModelType',
    'Framework',
    'ModelStatus',
    'AuditAction',
    'DeploymentEnvironment',
    'ABTestStatus',
    'FRAMEWORK_MODEL_COMPATIBILITY',
    'is_compatible',
    'get_supported_models',
    'get_supported_frameworks',
    'validate_or_raise',
]