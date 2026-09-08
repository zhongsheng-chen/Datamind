"""评分卡仓储

提供评分卡的查询、创建和更新能力。

核心功能：
  - get_scorecard: 获取评分卡
  - create_scorecard: 创建评分卡
  - update_scorecard: 更新评分卡

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.scorecard import (
      ScorecardRepository,
  )

  async with UnitOfWork() as uow:
      repository = ScorecardRepository(
          uow.session
      )
      scorecard = await repository.get_scorecard(
          "ver_0123456789abcdef"
      )
"""

from sqlalchemy import select

from datamind.db.models.scorecards import Scorecard
from datamind.db.repositories.base import BaseRepository


class ScorecardRepository(BaseRepository):
    """评分卡仓储"""

    async def get_scorecard(
            self,
            version_id: str,
    ) -> Scorecard | None:
        """获取评分卡

        参数：
            version_id: 模型版本 ID

        返回：
            评分卡记录，不存在时返回 None
        """
        result = await self.session.execute(
            select(
                Scorecard
            ).where(
                Scorecard.version_id
                == version_id
            )
        )

        return result.scalar_one_or_none()

    def create_scorecard(
            self,
            *,
            scorecard_id: str,
            version_id: str,
            details: dict,
            details_version: int = 1,
    ) -> Scorecard:
        """创建评分卡

        参数：
            scorecard_id: 评分卡 ID
            version_id: 模型版本 ID
            details: 评分卡详情
            details_version: 评分卡详情结构版本

        返回：
            创建后的评分卡记录
        """
        scorecard = Scorecard(
            scorecard_id=scorecard_id,
            version_id=version_id,
            details_version=details_version,
            details=details,
        )
        self.add(
            scorecard
        )

        return scorecard

    @staticmethod
    def update_scorecard(
            scorecard: Scorecard,
            *,
            details: dict,
            details_version: int = 1,
    ) -> Scorecard:
        """更新评分卡

        参数：
            scorecard: 评分卡记录
            details: 评分卡详情
            details_version: 评分卡详情结构版本

        返回：
            更新后的评分卡记录
        """
        scorecard.details_version = details_version
        scorecard.details = details

        return scorecard
