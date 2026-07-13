# datamind/core/scoring/base.py

"""评分组件基类

定义评分组件统一的能力声明、能力查询和能力校验行为。

核心功能：
  - capabilities: 获取评分能力集
  - get_capabilities: 获取评分能力集
  - has_capability: 检查评分能力
  - require_capability: 校验评分能力

使用示例：
  from datamind.core.capability import ScorecardCapability
  from datamind.core.scoring.base import BaseScorer

  class CustomScorer(BaseScorer):
      SUPPORTED_CAPABILITIES = (
          ScorecardCapability.SCORECARD_LOGIT
          | ScorecardCapability.SCORECARD_TOTAL_SCORE
      )

  scorer = CustomScorer()

  supported = scorer.has_capability(
      ScorecardCapability.SCORECARD_TOTAL_SCORE
  )

  scorer.require_capability(
      ScorecardCapability.SCORECARD_LOGIT
      | ScorecardCapability.SCORECARD_TOTAL_SCORE
  )
"""

from typing import ClassVar

from datamind.core.capability import (
    ScorecardCapability,
    get_scorecard_capability_list,
    has_all_scorecard_capabilities,
)


class BaseScorer:
    """评分组件基类"""

    SUPPORTED_CAPABILITIES: ClassVar[
        ScorecardCapability
    ] = ScorecardCapability.NONE

    @property
    def capabilities(
            self,
    ) -> ScorecardCapability:
        """获取评分能力集"""
        return self.SUPPORTED_CAPABILITIES

    def get_capabilities(
            self,
    ) -> ScorecardCapability:
        """获取评分能力集"""
        return self.capabilities

    def has_capability(
            self,
            capability: ScorecardCapability,
    ) -> bool:
        """检查是否包含全部指定评分能力"""
        if not isinstance(
                capability,
                ScorecardCapability,
        ):
            raise TypeError(
                "capability 必须是 "
                "ScorecardCapability 枚举"
            )

        return has_all_scorecard_capabilities(
            self.capabilities,
            capability,
        )

    def require_capability(
            self,
            capability: ScorecardCapability,
    ) -> None:
        """校验是否包含全部指定评分能力"""
        if self.has_capability(
                capability
        ):
            return

        capability_names = (
            get_scorecard_capability_list(
                capability
            )
        )

        capability_text = (
            ", ".join(
                capability_names
            )
            if capability_names
            else "NONE"
        )

        raise NotImplementedError(
            f"{self.__class__.__name__} "
            f"不支持能力: {capability_text}"
        )
