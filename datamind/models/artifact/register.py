# datamind/models/artifact/register.py

"""模型产物注册器

提供模型加载器的注册和获取功能。

核心功能：
  - register: 注册模型加载器
  - get_handler: 获取模型加载器

使用示例：
  # 注册模型加载器
  from datamind.models.artifact.register import ModelArtifactRegister, get_handler

  @ModelArtifactRegister.register("sklearn")
  def load_sklearn(data: bytes):
      ...

  # 获取模型加载器
  handler = get_handler("sklearn")
  model = handler(data)
"""

from typing import Any, Callable, Dict


_HANDLERS: Dict[str, Callable[[bytes], Any]] = {}


def _normalize(framework: str) -> str:
    """规范化框架名称

    参数：
        framework: 模型框架名称

    返回：
        规范化后的框架名称（小写、去空格）
    """
    return framework.strip().lower()


class ModelArtifactRegister:
    """模型产物注册器"""

    @classmethod
    def register(cls, framework: str):
        """注册模型加载器

        参数：
            framework: 模型框架
        """
        def decorator(func: Callable[[bytes], Any]) -> Callable[[bytes], Any]:
            _HANDLERS[_normalize(framework)] = func
            return func

        return decorator


def get_handler(framework: str) -> Callable[[bytes], Any]:
    """获取模型加载器

    参数：
        framework: 模型框架

    返回：
        模型加载函数

    异常：
        KeyError: 不支持的框架
    """
    framework = _normalize(framework)

    handler = _HANDLERS.get(framework)
    if handler is None:
        raise KeyError(f"不支持的框架: {framework}")

    return handler