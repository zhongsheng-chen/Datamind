"""评分任务配置测试

验证默认评分阈值、自定义评分阈值和非有限数值校验。

核心功能：
  - test_scoring_config_default_threshold:
    验证评分决策阈值默认值
  - test_scoring_config_accepts_threshold:
    验证接受自定义评分决策阈值
  - test_scoring_config_rejects_non_finite_threshold:
    验证拒绝非有限评分决策阈值
"""

import pytest
from pydantic import ValidationError

from datamind.config.scoring import ScoringConfig


def test_scoring_config_default_threshold() -> None:
    """测试默认评分阈值"""
    assert ScoringConfig().threshold == pytest.approx(600.0)


def test_scoring_config_accepts_threshold() -> None:
    """测试自定义评分阈值"""
    assert ScoringConfig(threshold=650).threshold == pytest.approx(650.0)


@pytest.mark.parametrize("threshold", [float("inf"), float("nan")])
def test_scoring_config_rejects_non_finite_threshold(
        threshold: float,
) -> None:
    """测试拒绝非有限评分阈值"""
    with pytest.raises(ValidationError, match="必须是有限数值"):
        ScoringConfig(threshold=threshold)
