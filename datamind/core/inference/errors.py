"""推理错误定义.

统一定义模型推理过程中的异常类型。

核心功能：
  - FrameworkDependencyError: 模型框架依赖缺失
"""

from datamind.constants import Framework


class FrameworkDependencyError(RuntimeError):
    """模型框架运行依赖缺失."""

    def __init__(
            self,
            framework: Framework | str,
            dependency: str,
    ) -> None:
        """初始化模型框架依赖异常.

        参数：
            framework: 模型框架
            dependency: 缺失的 Python 依赖
        """
        self.framework = str(framework)
        self.dependency = dependency
        self.message = (
            f"{self.framework} 模型运行时缺少依赖 {dependency!r}；"
            f"请安装 datamind[{self.framework}] 可选依赖"
        )
        super().__init__(self.message)
