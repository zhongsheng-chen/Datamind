# datamind/core/scoring/base.py

"""评分组件基类

定义评分组件统一接口规范。

核心功能：
    - get_capabilities: 获取评分能力集
    - has_capability: 检查评分能力
    - require_capability: 校验评分能力

使用示例：
    from datamind.core.scoring.base import BaseScorer
    from datamind.core.capability import ScorecardCapability

    class MyScorer(BaseScorer):
        SUPPORTED_CAPABILITIES = (
            ScorecardCapability.SCORECARD_LOGIT
            | ScorecardCapability.SCORECARD_TOTAL_SCORE
        )

    scorer = MyScorer()
    if scorer.has_capability(ScorecardCapability.SCORECARD_LOGIT):
        logit = scorer.get_logit(features)
"""

from abc import ABC

from datamind.core.capability import ScorecardCapability


class BaseScorer(ABC):
    """评分组件基类

    属性：
        SUPPORTED_CAPABILITIES: 类级别能力声明
        capabilities: 实例能力集
    """

    SUPPORTED_CAPABILITIES = ScorecardCapability.NONE

    def __init__(self):
        """初始化评分组件"""
        self.capabilities = self.SUPPORTED_CAPABILITIES

    def get_capabilities(self) -> ScorecardCapability:
        """获取评分能力集

        返回：
            ScorecardCapability 位掩码
        """
        return self.capabilities

    def has_capability(self, capability: ScorecardCapability) -> bool:
        """检查是否支持指定评分能力

        参数：
            capability: 评分能力

        返回：
            支持返回 True，否则返回 False
        """
        return bool(self.capabilities & capability)

    def require_capability(self, capability: ScorecardCapability) -> None:
        """校验评分能力

        参数：
            capability: 所需评分能力

        异常：
            NotImplementedError: 不支持该能力
        """
        if not self.has_capability(capability):
            raise NotImplementedError(
                f"{self.__class__.__name__} 不支持能力: {capability.name}"
            )
