"""管理控制台写操作结构

定义浏览器管理操作使用的请求结构，统一完成字段校验与空白处理。

核心功能：
  - ModelRegistrationMetadata: 模型注册参数
  - ModelUpdateRequest: 模型信息更新参数
  - VersionUpdateRequest: 模型版本信息更新参数
  - DeploymentCreateRequest: 部署创建参数
  - RoutingCreateRequest: 路由创建参数
  - ExperimentCreateRequest: 实验创建参数
  - VariantCreateRequest: 分组创建参数
  - UserCreateRequest: 用户创建参数
  - UserUpdateRequest: 用户更新参数
  - RoleCreateRequest: 角色创建参数
  - RoleUpdateRequest: 角色权限更新参数
  - PasswordChangeRequest: 当前用户密码修改参数
  - PasswordResetRequest: 密码重置参数
  - ResourceActionRequest: 资源操作参数
"""

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from datamind.constants.version import (
    SUPPORTED_MODEL_VERSION_PATTERN,
)
from datamind.constants.model_name import SUPPORTED_MODEL_NAME_PATTERN


class _ConsoleRequest(BaseModel):
    """控制台请求基类"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ModelRegistrationMetadata(_ConsoleRequest):
    """模型注册参数"""

    name: str = Field(
        min_length=1,
        max_length=63,
        pattern=SUPPORTED_MODEL_NAME_PATTERN,
    )
    display_name: str | None = Field(default=None, max_length=100)
    version: str = Field(
        min_length=1,
        max_length=64,
        pattern=SUPPORTED_MODEL_VERSION_PATTERN,
    )
    framework: str = Field(min_length=1, max_length=64)
    model_type: str = Field(min_length=1, max_length=64)
    task_type: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    version_description: str | None = Field(default=None, max_length=2000)
    params: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    force: bool = False


class ModelUpdateRequest(_ConsoleRequest):
    """模型信息更新参数"""

    display_name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class VersionUpdateRequest(_ConsoleRequest):
    """模型版本信息更新参数"""

    description: str | None = Field(default=None, max_length=2000)


class DeploymentCreateRequest(_ConsoleRequest):
    """部署创建参数"""

    model_id: str = Field(min_length=1, max_length=64)
    version_id: str = Field(min_length=1, max_length=64)
    rollout_type: str = Field(default="full", min_length=1, max_length=32)
    role: str = Field(default="champion", min_length=1, max_length=32)
    threshold: float | None = None
    description: str | None = Field(default=None, max_length=2000)


class DeploymentUpdateRequest(_ConsoleRequest):
    """部署更新参数"""

    rollout_type: str | None = Field(default=None, min_length=1, max_length=32)
    role: str | None = Field(default=None, min_length=1, max_length=32)
    threshold: float | None = None
    description: str | None = Field(default=None, max_length=2000)


class RulesMetadataRequest(_ConsoleRequest):
    """规则文件信息，上传时间由服务端记录"""

    name: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0)


class RoutingCreateRequest(_ConsoleRequest):
    """路由创建参数"""

    name: str = Field(min_length=1, max_length=128)
    deployment_id: str = Field(min_length=1, max_length=64)
    traffic_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = False
    rules: dict[str, Any] | None = None
    rules_metadata: RulesMetadataRequest | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class RoutingUpdateRequest(_ConsoleRequest):
    """路由更新参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    traffic_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    rules: dict[str, Any] | None = None
    rules_metadata: RulesMetadataRequest | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class ExperimentGroupRequest(_ConsoleRequest):
    """分组创建参数"""

    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    deployment_id: str = Field(min_length=1, max_length=64)
    weight: float = Field(gt=0.0, le=1.0)
    is_control: bool = False


class ExperimentCreateRequest(_ConsoleRequest):
    """实验创建参数"""

    model_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    strategy: str = Field(default="hash", min_length=1, max_length=32)
    traffic_ratio: float = Field(default=1.0, gt=0.0, le=1.0)
    bucket_key: str = Field(default="subject_key", min_length=1, max_length=128)
    groups: list[ExperimentGroupRequest] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    manual_assignments: dict[str, str] | None = None
    effective_from: str | None = None
    effective_to: str | None = None


class ExperimentUpdateRequest(_ConsoleRequest):
    """实验更新参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    strategy: str | None = Field(default=None, min_length=1, max_length=32)
    traffic_ratio: float | None = Field(default=None, gt=0.0, le=1.0)
    bucket_key: str | None = Field(default=None, min_length=1, max_length=128)
    manual_assignments: dict[str, str] | None = None
    description: str | None = Field(default=None, max_length=2000)
    effective_from: str | None = None
    effective_to: str | None = None


class VariantCreateRequest(_ConsoleRequest):
    """实验分组创建参数"""

    name: str = Field(min_length=1, max_length=128)
    deployment_id: str = Field(min_length=1, max_length=64)
    weight: float = Field(gt=0.0, le=1.0)
    is_control: bool = False
    description: str | None = Field(default=None, max_length=2000)
    config: dict[str, Any] | None = None


class VariantUpdateRequest(_ConsoleRequest):
    """实验分组更新参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    weight: float | None = Field(default=None, gt=0.0, le=1.0)
    is_control: bool | None = None
    config: dict[str, Any] | None = None
    description: str | None = Field(default=None, max_length=2000)


class UserCreateRequest(_ConsoleRequest):
    """用户创建参数"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=254)
    roles: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("roles")
    @classmethod
    def _validate_roles(
            cls,
            roles: list[str],
    ) -> list[str]:
        """规范化角色名称"""
        normalized = [
            role.strip()
            for role in roles
            if role.strip()
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError("角色不能重复")

        return normalized


class UserUpdateRequest(_ConsoleRequest):
    """用户更新参数"""

    username: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=254)
    roles: list[str] | None = Field(default=None, max_length=100)

    @field_validator("roles")
    @classmethod
    def _validate_roles(
            cls,
            roles: list[str] | None,
    ) -> list[str] | None:
        """规范化角色名称"""
        if roles is None:
            return None

        normalized = [
            role.strip()
            for role in roles
            if role.strip()
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError("角色不能重复")

        return normalized


class RoleCreateRequest(_ConsoleRequest):
    """角色创建参数"""

    name: str = Field(min_length=1, max_length=64)
    permissions: list[str] = Field(default_factory=list, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class RoleUpdateRequest(_ConsoleRequest):
    """角色资料与权限更新参数"""

    description: str | None = Field(max_length=2000)
    permissions: list[str] = Field(min_length=1, max_length=200)

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(
            cls,
            permissions: list[str],
    ) -> list[str]:
        """规范化权限标识"""
        normalized = [
            permission.strip()
            for permission in permissions
            if permission.strip()
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError("权限不能重复")

        return normalized


class PasswordChangeRequest(_ConsoleRequest):
    """当前用户密码修改参数"""

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequest(_ConsoleRequest):
    """密码重置参数"""

    password: str = Field(min_length=1, max_length=1024)


class ResourceActionRequest(_ConsoleRequest):
    """资源操作参数"""

    reason: str | None = Field(default=None, max_length=2000)
