"""评分卡数据库模型测试

验证评分卡表结构、唯一索引和数据约束。

核心功能：
  - test_scorecard_table_and_columns: 验证表名和字段
  - test_scorecard_indexes_and_constraints: 验证索引和约束
"""

from sqlalchemy import Table

from datamind.db.models.scorecards import Scorecard


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    Scorecard.__table__
)


def test_scorecard_table_and_columns() -> None:
    """测试评分卡表名和字段定义"""
    assert TABLE.name == "scorecards"
    assert set(TABLE.columns.keys()) == {
        "id",
        "scorecard_id",
        "version_id",
        "details_version",
        "details",
        "created_at",
        "updated_at",
    }
    assert TABLE.c.details.nullable is False
    assert TABLE.c.details_version.nullable is False


def test_scorecard_indexes_and_constraints() -> None:
    """测试评分卡唯一索引和数据约束"""
    indexes = {index.name: index for index in TABLE.indexes}
    assert indexes["uk_scorecards_scorecard_id"].unique is True
    assert indexes["uk_scorecards_version_id"].unique is True
    constraints = {constraint.name for constraint in TABLE.constraints}
    assert "ck_scorecards_details_version_positive" in constraints
    assert "ck_scorecards_details_object" in constraints
