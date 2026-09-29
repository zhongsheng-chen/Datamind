"""数据库声明式基类测试.

验证共享元数据和数据库对象命名约定，
确保主键、外键、唯一约束、检查约束和索引
生成稳定且可供 Alembic 使用的名称。

核心功能：
  - test_naming_convention:
    验证数据库对象命名约定
  - test_base_uses_shared_metadata:
    验证声明式基类使用共享元数据
  - test_models_are_registered_in_shared_metadata:
    验证模型表注册到共享元数据
  - test_primary_key_naming:
    验证主键名称
  - test_unique_constraint_naming:
    验证唯一约束名称
  - test_check_constraint_naming:
    验证检查约束名称
  - test_foreign_key_constraint_naming:
    验证外键约束名称
  - test_index_naming:
    验证索引名称
  - test_unnamed_check_constraint_is_rejected:
    验证检查约束必须显式命名
"""

from collections.abc import Iterator
from typing import (
    TypeAlias,
    overload,
)

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.exc import InvalidRequestError

from datamind.db.core.base import (
    Base,
    metadata,
    naming_convention,
)


class BaseParentModel(
    Base
):
    """命名约定测试父模型."""

    __tablename__ = "test_base_parents"

    __table_args__ = (
        UniqueConstraint(
            "code",
        ),
        CheckConstraint(
            "btrim(code) <> ''",
            name="code_not_blank",
        ),
        Index(
            None,
            "name",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code = Column(
        String(50),
        nullable=False,
    )

    name = Column(
        String(100),
        nullable=False,
    )


class BaseChildModel(
    Base
):
    """命名约定测试子模型."""

    __tablename__ = "test_base_children"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    parent_id = Column(
        ForeignKey(
            "test_base_parents.id"
        ),
        nullable=False,
    )


SupportedConstraint: TypeAlias = (
    UniqueConstraint
    | CheckConstraint
    | ForeignKeyConstraint
)


def get_table(
        value: object,
) -> Table:
    """获取并校验数据表对象."""
    assert isinstance(
        value,
        Table,
    )

    return value


PARENT_TABLE = get_table(
    BaseParentModel.__table__
)
CHILD_TABLE = get_table(
    BaseChildModel.__table__
)


@pytest.fixture(
    scope="module",
    autouse=True,
)
def cleanup_test_tables() -> Iterator[None]:
    """测试完成后移除共享元数据中的临时表."""
    yield

    metadata.remove(
        CHILD_TABLE
    )
    metadata.remove(
        PARENT_TABLE
    )


@overload
def get_constraint(
        table: Table,
        constraint_type: type[UniqueConstraint],
) -> UniqueConstraint:
    ...


@overload
def get_constraint(
        table: Table,
        constraint_type: type[CheckConstraint],
) -> CheckConstraint:
    ...


@overload
def get_constraint(
        table: Table,
        constraint_type: type[ForeignKeyConstraint],
) -> ForeignKeyConstraint:
    ...


def get_constraint(
        table: Table,
        constraint_type: type[SupportedConstraint],
) -> SupportedConstraint:
    """按类型获取数据表约束."""
    matching_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(
            constraint,
            constraint_type,
        )
    ]

    assert len(
        matching_constraints
    ) == 1

    constraint = matching_constraints[
        0
    ]

    assert isinstance(
        constraint,
        (
            UniqueConstraint,
            CheckConstraint,
            ForeignKeyConstraint,
        ),
    )

    return constraint


def get_constraint_name(
        constraint: object,
) -> str:
    """获取并校验数据库对象名称."""
    name = getattr(
        constraint,
        "name",
        None,
    )

    assert isinstance(
        name,
        str,
    )

    return name


def test_naming_convention() -> None:
    """测试数据库对象命名约定."""
    assert naming_convention == {
        "ix": "ix_%(column_0_label)s",
        "uq": (
            "uq_%(table_name)s_"
            "%(column_0_name)s"
        ),
        "ck": (
            "ck_%(table_name)s_"
            "%(constraint_name)s"
        ),
        "fk": (
            "fk_%(table_name)s_"
            "%(column_0_name)s_"
            "%(referred_table_name)s"
        ),
        "pk": "pk_%(table_name)s",
    }


def test_base_uses_shared_metadata() -> None:
    """测试声明式基类使用共享元数据."""
    assert isinstance(
        metadata,
        MetaData,
    )
    assert Base.metadata is metadata
    assert (
        metadata.naming_convention
        == naming_convention
    )


def test_models_are_registered_in_shared_metadata() -> None:
    """测试模型表注册到共享元数据."""
    assert PARENT_TABLE.metadata is metadata
    assert CHILD_TABLE.metadata is metadata

    assert (
        metadata.tables[
            "test_base_parents"
        ]
        is PARENT_TABLE
    )
    assert (
        metadata.tables[
            "test_base_children"
        ]
        is CHILD_TABLE
    )


def test_primary_key_naming() -> None:
    """测试主键名称."""
    assert get_constraint_name(
        PARENT_TABLE.primary_key
    ) == "pk_test_base_parents"

    assert get_constraint_name(
        CHILD_TABLE.primary_key
    ) == "pk_test_base_children"


def test_unique_constraint_naming() -> None:
    """测试唯一约束名称."""
    constraint = get_constraint(
        PARENT_TABLE,
        UniqueConstraint,
    )

    assert get_constraint_name(
        constraint
    ) == "uq_test_base_parents_code"

    assert [
        column.name
        for column in constraint.columns
    ] == [
        "code"
    ]


def test_check_constraint_naming() -> None:
    """测试检查约束名称."""
    constraint = get_constraint(
        PARENT_TABLE,
        CheckConstraint,
    )

    assert get_constraint_name(
        constraint
    ) == (
        "ck_test_base_parents_"
        "code_not_blank"
    )

    assert str(
        constraint.sqltext
    ) == "btrim(code) <> ''"


def test_foreign_key_constraint_naming() -> None:
    """测试外键约束名称."""
    constraint = get_constraint(
        CHILD_TABLE,
        ForeignKeyConstraint,
    )

    assert get_constraint_name(
        constraint
    ) == (
        "fk_test_base_children_"
        "parent_id_"
        "test_base_parents"
    )

    foreign_keys = list(
        constraint.elements
    )

    assert len(
        foreign_keys
    ) == 1
    assert foreign_keys[
        0
    ].parent.name == "parent_id"
    assert foreign_keys[
        0
    ].target_fullname == (
        "test_base_parents.id"
    )


def test_index_naming() -> None:
    """测试索引名称."""
    indexes = list(
        PARENT_TABLE.indexes
    )

    assert len(
        indexes
    ) == 1

    index = indexes[
        0
    ]

    assert get_constraint_name(
        index
    ) == "ix_test_base_parents_name"

    expression_names: list[str] = []

    for expression in index.expressions:
        if isinstance(
                expression,
                str,
        ):
            expression_names.append(
                expression
            )
            continue

        expression_name = getattr(
            expression,
            "name",
            None,
        )

        assert isinstance(
            expression_name,
            str,
        )

        expression_names.append(
            expression_name
        )

    assert expression_names == [
        "name"
    ]


def test_unnamed_check_constraint_is_rejected() -> None:
    """测试检查约束必须显式命名."""
    isolated_metadata = MetaData(
        naming_convention=naming_convention
    )

    with pytest.raises(
            InvalidRequestError,
            match=(
                "constraint_name.*"
                "explicitly named"
            ),
    ):
        Table(
            "test_unnamed_checks",
            isolated_metadata,
            Column(
                "value",
                Integer,
                nullable=False,
            ),
            CheckConstraint(
                "value >= 0"
            ),
        )
