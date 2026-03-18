# Datamind/datamind/core/domain/__init__.py

"""领域模型模块

包含所有领域枚举、值对象和验证函数。
提供核心业务规则的统一入口。
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