# datamind/models/builder.py

"""模型构建器

负责将模型文件构建为可注册到 BentoML 的 Python 模型对象。

核心功能：
  - build: 从模型文件构建模型对象

使用示例：
  from datamind.models.builder import ModelBuilder

  model = ModelBuilder.build(
      framework="sklearn",
      model_path="./models/demo_scorecard.pkl",
  )
"""

from pathlib import Path
from typing import Any

from datamind.models.artifact import ModelArtifactLoader


class ModelBuilder:
    """模型构建器"""

    @classmethod
    def build(
        cls,
        *,
        framework: str,
        model_path: str,
    ) -> Any:
        """构建模型对象

        参数：
            framework: 模型框架
            model_path: 模型文件路径

        返回：
            Python 模型对象

        异常：
            FileNotFoundError: 模型文件不存在
        """
        path = Path(model_path)

        if not path.exists():
            raise FileNotFoundError(
                f"模型文件不存在: {model_path}"
            )

        data = path.read_bytes()

        return ModelArtifactLoader.load(
            framework=framework,
            data=data,
        )