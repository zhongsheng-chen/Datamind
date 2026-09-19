"""模型制品格式

集中维护各模型框架允许注册的文件扩展名。

核心功能：
  - SUPPORTED_ARTIFACT_EXTENSIONS: 框架与支持扩展名的映射
  - artifact_extension_capabilities: 获取可序列化的格式能力
  - validate_artifact_extension: 校验模型文件扩展名

使用示例：
  from datamind.constants import Framework
  from datamind.models.artifact.formats import validate_artifact_extension

  validate_artifact_extension(
      framework=Framework.SKLEARN,
      path="./models/scorecard.pkl",
  )
"""

from pathlib import Path
from typing import Final

from datamind.constants.framework import Framework
from datamind.models.errors import ArtifactError


SUPPORTED_ARTIFACT_EXTENSIONS: Final[
    dict[Framework, tuple[str, ...]]
] = {
    Framework.SKLEARN: (".pkl", ".pickle", ".joblib"),
    Framework.XGBOOST: (".json", ".ubj", ".model"),
    Framework.LIGHTGBM: (".txt", ".model"),
    Framework.CATBOOST: (".cbm",),
}


def artifact_extension_capabilities() -> dict[str, list[str]]:
    """获取可序列化的模型制品格式能力

    返回：
        以框架名称为键、支持扩展名列表为值的字典
    """
    return {
        framework.value: list(extensions)
        for framework, extensions in SUPPORTED_ARTIFACT_EXTENSIONS.items()
    }


def validate_artifact_extension(
        *,
        framework: Framework,
        path: str | Path,
) -> None:
    """校验模型文件扩展名

    参数：
        framework: 模型框架
        path: 模型文件路径

    异常：
        ArtifactError: 模型文件扩展名不受所选框架支持
    """
    suffix = Path(path).suffix.lower()
    supported = SUPPORTED_ARTIFACT_EXTENSIONS[framework]

    if suffix in supported:
        return

    formats = "、".join(supported)

    if not suffix:
        raise ArtifactError(
            f"框架 {framework.value} 的模型文件缺少扩展名；"
            f"支持格式：{formats}"
        )

    raise ArtifactError(
        f"框架 {framework.value} 不支持模型文件后缀 {suffix}；"
        f"支持格式：{formats}"
    )
