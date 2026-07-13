"""模型组件

提供模型状态枚举、领域异常、状态守卫、模型解析、Schema 提取和模型产物加载能力。

核心功能：
  - ModelGuard: 校验模型、版本、部署和实验状态迁移
  - ModelResolver: 按标识或名称解析模型和版本
  - SchemaExtractor: 从支持的模型框架提取输入 Schema
  - ModelArtifactLoader: 从二进制模型产物加载模型对象
  - ModelArtifactRegister: 注册模型框架加载器

使用示例：
  from datamind.models import ModelGuard, ModelResolver, SchemaExtractor

  model = await ModelResolver(
      metadata_repo,
      version_repo,
  ).resolve_model(
      model_id="mdl_0123456789abcdef"
  )

  ModelGuard.validate_model_deployable(model.status)
  schema = SchemaExtractor.extract(
      model=model_object,
      framework=model.framework,
  )
"""

from importlib import import_module
from typing import Any, Final


_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    name: ("datamind.models.enums", name)
    for name in (
        "AssignmentStrategy",
        "BaseEnum",
        "DecisionStrategy",
        "DeploymentStatus",
        "ExperimentStatus",
        "ExperimentVariantStatus",
        "MetadataStatus",
        "RuntimeControlStatus",
        "VersionStatus",
    )
}
_EXPORTS.update({
    name: ("datamind.models.errors", name)
    for name in (
        "ArtifactError",
        "BackendError",
        "DeploymentError",
        "DeploymentNotFoundError",
        "ExperimentError",
        "InvalidDeploymentStateError",
        "InvalidExperimentConfigError",
        "InvalidExperimentStateError",
        "InvalidModelStateError",
        "ModelAlreadyExistsError",
        "ModelError",
        "ModelNotFoundError",
        "RuntimeRouteError",
        "VersionNotFoundError",
    )
})
_EXPORTS.update({
    "ModelArtifactLoader": (
        "datamind.models.artifact",
        "ModelArtifactLoader",
    ),
    "ModelArtifactRegister": (
        "datamind.models.artifact",
        "ModelArtifactRegister",
    ),
    "ModelGuard": ("datamind.models.guard", "ModelGuard"),
    "ModelResolver": ("datamind.models.resolver", "ModelResolver"),
    "SchemaExtractor": ("datamind.models.schema", "SchemaExtractor"),
})

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """按需加载包级公共对象"""
    export = _EXPORTS.get(name)

    if export is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = export
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value

    return value


def __dir__() -> list[str]:
    """返回包含延迟公共导出的模块属性列表"""
    return sorted({*globals(), *__all__})
