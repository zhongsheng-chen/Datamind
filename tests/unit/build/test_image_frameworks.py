"""模型框架依赖配置测试.

验证 Python extras 与 Docker 镜像构建选项保持一致，并确认核心模块无需安装
可选模型框架。

核心功能：
  - test_image_frameworks_and_extras_are_aligned:
    验证镜像框架选项与 Python extra 对齐
  - test_full_extra_covers_framework_extras:
    验证 full extra 覆盖全部框架依赖
  - test_dockerfile_uses_framework_extra_without_dependency_matrix:
    验证 Dockerfile 复用 Python extra 定义
  - test_core_imports_do_not_require_optional_frameworks:
    验证核心入口不依赖可选模型框架
"""

from pathlib import Path
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement

from datamind.constants import Framework
from build_support.docker import (
    DEFAULT_FRAMEWORK,
    SUPPORTED_FRAMEWORKS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_FRAMEWORKS = {framework.value for framework in Framework}


def optional_dependencies() -> dict[str, list[str]]:
    """读取项目可选依赖."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    return document["project"]["optional-dependencies"]


def test_image_frameworks_and_extras_are_aligned() -> None:
    """测试镜像框架选项与 Python extra 保持一致."""
    extras = optional_dependencies()

    assert SUPPORTED_FRAMEWORKS == MODEL_FRAMEWORKS | {"full"}
    assert SUPPORTED_FRAMEWORKS <= extras.keys()
    assert DEFAULT_FRAMEWORK == "full"


def test_full_extra_covers_framework_extras() -> None:
    """测试 full extra 覆盖全部专用框架依赖."""
    extras = optional_dependencies()
    framework_dependencies = {
        dependency
        for framework in MODEL_FRAMEWORKS
        for dependency in extras[framework]
    }

    assert framework_dependencies <= set(extras["full"])


def test_scorecard_dependency_uses_supported_version_range() -> None:
    """测试评分卡依赖使用已验证的版本范围."""
    requirement = next(
        Requirement(dependency)
        for dependency in optional_dependencies()["sklearn"]
        if dependency.startswith("optbinning")
    )

    assert requirement.marker is None
    assert str(requirement.specifier) == "<2.0.0,>=1.0.0"


def test_dockerfile_uses_framework_extra_without_dependency_matrix() -> None:
    """测试 Dockerfile 仅消费受控 extra，不复制框架依赖清单."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert '"${wheel_path}[${DATAMIND_PYTHON_EXTRA}]"' in content
    assert "io.github.zhongsheng-chen.datamind.framework" in content

    for dependency in ("scikit-learn", "xgboost", "lightgbm", "catboost"):
        assert dependency not in content


def test_core_imports_do_not_require_optional_frameworks() -> None:
    """测试 Datamind 核心入口不依赖可选模型框架."""
    script = """
import importlib.abc
import sys

blocked = {"sklearn", "xgboost", "lightgbm", "catboost", "optbinning", "joblib"}

class BlockFrameworkImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise ModuleNotFoundError(
                f"No module named {fullname!r}",
                name=fullname.split(".", 1)[0],
            )
        return None

sys.meta_path.insert(0, BlockFrameworkImports())
from datamind.core.inference.adapters.factory import ModelAdapterFactory
import datamind.core.inference.adapters
import datamind.runtime
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=True,
        timeout=60,
    )
