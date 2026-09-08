"""数据库模型混入类测试

通过临时声明式模型验证 IdMixin 和 TimestampMixin
映射后的主键、时间戳、默认值和自动更新时间配置。

核心功能：
  - test_mixin_columns_are_mapped:
    验证混入字段已映射到数据表
  - test_id_mixin_column:
    验证自增主键字段
  - test_created_at_column:
    验证创建时间字段
  - test_updated_at_column:
    验证更新时间字段
  - test_timestamp_defaults_use_database_time:
    验证时间戳默认值使用数据库当前时间
  - test_updated_at_uses_onupdate:
    验证更新时间配置自动更新
  - test_mixin_model_primary_key_name:
    验证主键名称遵循元数据命名约定
  - test_mixin_model_uses_base_metadata:
    验证临时模型使用共享元数据
  - test_mixin_model_constructor:
    验证混入模型可以正常构造
"""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    String,
    Table,
)

from datamind.db.core.base import Base
from datamind.db.core.mixins import (
    IdMixin,
    TimestampMixin,
)


class MixinTestModel(
    IdMixin,
    TimestampMixin,
    Base,
):
    """混入类映射测试模型"""

    __tablename__ = "test_mixin_models"

    name = Column(
        String(100),
        nullable=False,
    )


def get_table(
        value: object,
) -> Table:
    """获取并校验数据表对象"""
    assert isinstance(
        value,
        Table,
    )

    return value


MIXIN_TABLE = get_table(
    MixinTestModel.__table__
)


@pytest.fixture(
    scope="module",
    autouse=True,
)
def cleanup_test_table() -> Iterator[None]:
    """测试完成后移除共享元数据中的临时表"""
    yield

    Base.metadata.remove(
        MIXIN_TABLE
    )


def normalize_default(
        value: Any,
) -> str:
    """规范化 SQL 默认值文本"""
    return " ".join(
        str(
            value
        ).replace(
            '"',
            "",
        ).split()
    ).lower()


def test_mixin_columns_are_mapped() -> None:
    """验证混入字段已映射到数据表"""
    assert set(
        MIXIN_TABLE.columns.keys()
    ) == {
        "id",
        "created_at",
        "updated_at",
        "name",
    }


def test_id_mixin_column() -> None:
    """验证自增主键字段"""
    column = MIXIN_TABLE.columns[
        "id"
    ]

    assert isinstance(
        column.type,
        BigInteger,
    )
    assert column.primary_key is True
    assert column.autoincrement is True
    assert column.nullable is False
    assert column.comment == "自增主键 ID"


def test_created_at_column() -> None:
    """验证创建时间字段"""
    column = MIXIN_TABLE.columns[
        "created_at"
    ]

    assert isinstance(
        column.type,
        DateTime,
    )
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.comment == "创建时间"
    assert column.server_default is not None
    assert column.onupdate is None


def test_updated_at_column() -> None:
    """验证更新时间字段"""
    column = MIXIN_TABLE.columns[
        "updated_at"
    ]

    assert isinstance(
        column.type,
        DateTime,
    )
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.comment == "更新时间"
    assert column.server_default is not None
    assert column.onupdate is not None


def test_timestamp_defaults_use_database_time() -> None:
    """验证时间戳默认值使用数据库当前时间"""
    created_at = MIXIN_TABLE.columns[
        "created_at"
    ]
    updated_at = MIXIN_TABLE.columns[
        "updated_at"
    ]

    created_default = created_at.server_default
    updated_default = updated_at.server_default

    assert created_default is not None
    assert updated_default is not None
    assert normalize_default(
        created_default.arg
    ) == "now()"
    assert normalize_default(
        updated_default.arg
    ) == "now()"


def test_updated_at_uses_onupdate() -> None:
    """验证更新时间配置自动更新"""
    updated_at = MIXIN_TABLE.columns[
        "updated_at"
    ]
    onupdate = updated_at.onupdate

    assert onupdate is not None
    assert normalize_default(
        onupdate.arg
    ) == "now()"


def test_mixin_model_primary_key_name() -> None:
    """验证主键名称遵循元数据命名约定"""
    primary_key = MIXIN_TABLE.primary_key

    assert primary_key.name == (
        "pk_test_mixin_models"
    )
    assert [
        column.name
        for column in primary_key.columns
    ] == [
        "id"
    ]


def test_mixin_model_uses_base_metadata() -> None:
    """验证临时模型使用共享元数据"""
    assert MIXIN_TABLE.metadata is Base.metadata
    assert (
        Base.metadata.tables[
            "test_mixin_models"
        ]
        is MIXIN_TABLE
    )


# noinspection PyUnreachableCode
def test_mixin_model_constructor() -> None:
    """验证混入模型可以正常构造"""
    model = MixinTestModel(
        name="example"
    )

    assert model.name == "example"
    assert model.id is None
    assert model.created_at is None
    assert model.updated_at is None
