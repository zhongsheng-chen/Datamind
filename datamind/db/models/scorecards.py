"""评分卡表.

存储模型版本对应的评分卡刻度、变量质量和分箱明细。

核心功能：
  - Scorecard: 评分卡记录

使用示例：
  from datamind.db.models.scorecards import Scorecard

  scorecard = Scorecard(
      scorecard_id="scr_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      details_version=1,
      details={
          "scaling": {
              "method": "pdo_odds",
          },
          "variables": [],
      },
  )
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Scorecard(
    IdMixin,
    TimestampMixin,
    Base,
):
    """评分卡表."""

    __tablename__ = "scorecards"

    __table_args__ = (
        Index(
            "uk_scorecards_scorecard_id",
            "scorecard_id",
            unique=True,
        ),
        Index(
            "uk_scorecards_version_id",
            "version_id",
            unique=True,
        ),
        CheckConstraint(
            "details_version >= 1",
            name="details_version_positive",
        ),
        CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name="details_object",
        ),
    )

    scorecard_id = Column(
        String(64),
        nullable=False,
        comment="评分卡 ID",
    )

    version_id = Column(
        String(64),
        nullable=False,
        comment="模型版本 ID",
    )

    details_version = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="评分卡详情结构版本",
    )

    details = Column(
        JSONB(
            none_as_null=True
        ),
        nullable=False,
        comment="评分卡详情，JSON 对象",
    )
