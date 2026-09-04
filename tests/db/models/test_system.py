# tests/db/models/test_system.py

"""系统状态表模型测试

验证系统状态表字段、索引、约束和对象行为。

核心功能：
  - test_system_state_table_name:
    验证系统状态表名称
  - test_system_state_business_columns:
    验证系统状态表业务字段完整
  - test_system_state_defaults_to_uninitialized:
    验证系统状态默认未初始化
  - test_system_state_indexes:
    验证系统状态表唯一索引
  - test_system_state_check_constraints:
    验证系统状态表检查约束
  - test_system_state_constructor_and_repr:
    验证系统状态对象构造与字符串表示"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Table,
)

from datamind.db.models.system import SystemState


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    SystemState.__table__
)


def test_system_state_table_name() -> None:
    """验证系统状态表名称"""
    assert TABLE.name == "systems"


def test_system_state_business_columns() -> None:
    """验证系统状态表业务字段完整"""
    assert set(TABLE.columns.keys()) >= {
        "system_id",
        "initialized",
        "initialized_at",
        "initialized_by",
    }
    assert isinstance(
        TABLE.columns["system_id"].type,
        String,
    )
    assert isinstance(
        TABLE.columns["initialized"].type,
        Boolean,
    )
    assert isinstance(
        TABLE.columns["initialized_at"].type,
        DateTime,
    )


def test_system_state_defaults_to_uninitialized() -> None:
    """验证系统状态默认未初始化"""
    column = TABLE.columns[
        "initialized"
    ]

    assert column.nullable is False
    assert str(column.server_default.arg) == "false"


def test_system_state_indexes() -> None:
    """验证系统状态表唯一索引"""
    indexes: dict[str, Index] = {
        index.name: index
        for index in TABLE.indexes
        if index.name is not None
    }

    assert set(indexes) == {
        "uk_systems_system_id"
    }
    assert indexes[
        "uk_systems_system_id"
    ].unique is True


def test_system_state_check_constraints() -> None:
    """验证系统状态表检查约束"""
    constraints = {
        constraint.name: str(
            constraint.sqltext
        )
        for constraint in TABLE.constraints
        if isinstance(
            constraint,
            CheckConstraint,
        )
    }

    assert "ck_systems_system_id_valid" in constraints
    assert (
        "ck_systems_initialization_state_valid"
        in constraints
    )
    assert "system_id = 'datamind'" in constraints[
        "ck_systems_system_id_valid"
    ]


def test_system_state_constructor_and_repr() -> None:
    """验证系统状态对象构造与字符串表示"""
    state = SystemState(
        system_id="datamind",
        initialized=False,
    )

    assert state.system_id == "datamind"
    assert state.initialized is False
    assert repr(state) == (
        "<SystemState("
        "system_id='datamind', "
        "initialized=False)>"
    )
