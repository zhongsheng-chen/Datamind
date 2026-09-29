"""评分卡仓储测试.

验证评分卡详情的查询、创建和更新行为。

核心功能：
  - test_get_scorecard:
    验证按模型版本查询
  - test_create_scorecard:
    验证创建评分卡
  - test_update_scorecard:
    验证更新评分卡
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.db.models.scorecards import Scorecard
from datamind.db.repositories.scorecard import ScorecardRepository


@pytest.mark.asyncio
async def test_get_scorecard() -> None:
    """测试按模型版本查询评分卡."""
    expected = Scorecard(
        scorecard_id="scr_test",
        version_id="ver_test",
        details_version=1,
        details={},
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = expected
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    actual = await ScorecardRepository(session).get_scorecard("ver_test")

    assert actual is expected
    session.execute.assert_awaited_once()


def test_create_scorecard() -> None:
    """测试创建评分卡."""
    session = MagicMock()
    repository = ScorecardRepository(session)

    scorecard = repository.create_scorecard(
        scorecard_id="scr_test",
        version_id="ver_test",
        details={"variable_count": 8},
    )

    assert scorecard.scorecard_id == "scr_test"
    assert scorecard.version_id == "ver_test"
    assert scorecard.details == {"variable_count": 8}
    session.add.assert_called_once_with(scorecard)


def test_update_scorecard() -> None:
    """测试更新评分卡."""
    scorecard = Scorecard(
        scorecard_id="scr_test",
        version_id="ver_test",
        details_version=1,
        details={},
    )

    result = ScorecardRepository.update_scorecard(
        scorecard,
        details_version=2,
        details={"variable_count": 10},
    )

    assert result is scorecard
    assert scorecard.details_version == 2
    assert scorecard.details == {"variable_count": 10}
