# tests/db/models/test_grants.py

"""角色授予模型测试

验证角色授予表名称、字段定义、服务端默认值、索引、
检查约束、字段注释和字符串表示。

核心功能：
  - test_grant_table_name:
    验证角色授予表名称
  - test_grant_contains_mixin_columns:
    验证主键和时间戳混入字段
  - test_grant_business_columns:
    验证角色授予业务字段集合
  - test_grant_string_columns:
    验证字符串字段长度和可空性
  - test_grant_datetime_columns:
    验证授予和撤销时间字段
  - test_grant_status_server_default:
    验证状态服务端默认值
  - test_granted_at_server_default:
    验证授予时间服务端默认值
  - test_grant_indexes:
    验证普通索引、联合索引和唯一索引
  - test_grant_check_constraints:
    验证角色授予数据完整性约束
  - test_grant_column_comments:
    验证关键字段注释
  - test_active_grant_constructor:
    验证有效角色授予模型构造
  - test_revoked_grant_constructor:
    验证已撤销角色授予模型构造
  - test_grant_allows_empty_optional_fields:
    验证可选字段允许省略
  - test_grant_repr:
    验证角色授予字符串表示
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Any

import pytest
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
    Table,
)

from datamind.db.models.grants import Grant


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


GRANT_TABLE = get_model_table(
    Grant.__table__
)

GRANTED_AT = datetime(
    2026,
    7,
    26,
    8,
    30,
    tzinfo=timezone.utc,
)

REVOKED_AT = datetime(
    2026,
    7,
    26,
    9,
    30,
    tzinfo=timezone.utc,
)


def normalize_sql(
        value: Any,
) -> str:
    """规范化 SQL 文本，便于断言"""
    return " ".join(
        str(
            value
        ).replace(
            '"',
            "",
        ).split()
    )


def get_server_default(
        column_name: str,
) -> str | None:
    """获取字段的服务端默认值"""
    column = GRANT_TABLE.columns[
        column_name
    ]
    server_default = column.server_default

    if server_default is None:
        return None

    return normalize_sql(
        server_default.arg
    )


def get_index(
        index_name: str,
) -> Index:
    """按名称获取角色授予表索引"""
    for index in GRANT_TABLE.indexes:
        if index.name == index_name:
            return index

    raise AssertionError(
        f"未找到索引: {index_name}"
    )


def get_index_column_names(
        index: Index,
) -> list[str]:
    """获取索引字段名称"""
    actual_columns: list[str] = []

    for expression in index.expressions:
        if isinstance(
                expression,
                str,
        ):
            actual_columns.append(
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

        actual_columns.append(
            expression_name
        )

    return actual_columns


def get_constraint(
        constraint_name: str,
) -> CheckConstraint:
    """按基础名称获取角色授予表检查约束"""
    expected_name = (
        f"ck_{Grant.__tablename__}_"
        f"{constraint_name}"
    )

    for constraint in GRANT_TABLE.constraints:
        if (
                isinstance(
                    constraint,
                    CheckConstraint,
                )
                and constraint.name
                == expected_name
        ):
            return constraint

    actual_names: list[str] = []

    for constraint in GRANT_TABLE.constraints:
        if not isinstance(
                constraint,
                CheckConstraint,
        ):
            continue

        actual_name = constraint.name

        if isinstance(
                actual_name,
                str,
        ):
            actual_names.append(
                actual_name
            )

    actual_names.sort()

    raise AssertionError(
        "未找到检查约束: "
        f"{expected_name}；"
        f"实际约束: {actual_names}"
    )


def test_grant_table_name() -> None:
    """验证角色授予表名称"""
    assert Grant.__tablename__ == "grants"
    assert GRANT_TABLE.name == "grants"


def test_grant_contains_mixin_columns() -> None:
    """验证主键和时间戳混入字段"""
    column_names = set(
        GRANT_TABLE.columns.keys()
    )

    assert {
        "id",
        "created_at",
        "updated_at",
    }.issubset(
        column_names
    )

    primary_key_columns = [
        column.name
        for column in GRANT_TABLE.primary_key.columns
    ]

    assert primary_key_columns == [
        "id"
    ]


def test_grant_business_columns() -> None:
    """验证角色授予业务字段集合"""
    column_names = set(
        GRANT_TABLE.columns.keys()
    )

    assert {
        "grant_id",
        "user_id",
        "role_id",
        "status",
        "granted_by",
        "granted_at",
        "revoked_by",
        "revoked_at",
    }.issubset(
        column_names
    )


@pytest.mark.parametrize(
    (
        "column_name",
        "expected_length",
        "expected_nullable",
    ),
    [
        (
            "grant_id",
            64,
            False,
        ),
        (
            "user_id",
            64,
            False,
        ),
        (
            "role_id",
            64,
            False,
        ),
        (
            "status",
            20,
            False,
        ),
        (
            "granted_by",
            64,
            True,
        ),
        (
            "revoked_by",
            64,
            True,
        ),
    ],
)
def test_grant_string_columns(
        column_name: str,
        expected_length: int,
        expected_nullable: bool,
) -> None:
    """验证字符串字段长度和可空性"""
    column = GRANT_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        String,
    )
    assert column.type.length == expected_length
    assert column.nullable is expected_nullable


@pytest.mark.parametrize(
    (
        "column_name",
        "expected_nullable",
    ),
    [
        (
            "granted_at",
            False,
        ),
        (
            "revoked_at",
            True,
        ),
    ],
)
def test_grant_datetime_columns(
        column_name: str,
        expected_nullable: bool,
) -> None:
    """验证授予和撤销时间字段"""
    column = GRANT_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        DateTime,
    )
    assert column.type.timezone is True
    assert column.nullable is expected_nullable


def test_grant_status_server_default() -> None:
    """验证授予状态服务端默认值"""
    assert get_server_default(
        "status"
    ) == "'active'"


def test_granted_at_server_default() -> None:
    """验证授予时间由数据库生成"""
    default_sql = get_server_default(
        "granted_at"
    )

    assert default_sql is not None
    assert default_sql.lower() == "now()"


@pytest.mark.parametrize(
    (
        "index_name",
        "expected_columns",
        "expected_unique",
    ),
    [
        (
            "idx_grants_user_id",
            [
                "user_id"
            ],
            False,
        ),
        (
            "idx_grants_role_id",
            [
                "role_id"
            ],
            False,
        ),
        (
            "idx_grants_status",
            [
                "status"
            ],
            False,
        ),
        (
            "idx_grants_granted_at",
            [
                "granted_at"
            ],
            False,
        ),
        (
            "idx_grants_user_status",
            [
                "user_id",
                "status",
            ],
            False,
        ),
        (
            "idx_grants_role_status",
            [
                "role_id",
                "status",
            ],
            False,
        ),
        (
            "uk_grants_grant_id",
            [
                "grant_id"
            ],
            True,
        ),
        (
            "uk_grants_user_role",
            [
                "user_id",
                "role_id",
            ],
            True,
        ),
    ],
)
def test_grant_indexes(
        index_name: str,
        expected_columns: list[str],
        expected_unique: bool,
) -> None:
    """验证普通索引、联合索引和唯一索引"""
    index = get_index(
        index_name
    )

    assert (
        get_index_column_names(
            index
        )
        == expected_columns
    )
    assert bool(
        index.unique
    ) is expected_unique


@pytest.mark.parametrize(
    (
        "constraint_name",
        "expected_fragments",
    ),
    [
        (
            "status_valid",
            [
                "status IN",
                "'active'",
                "'revoked'",
            ],
        ),
        (
            "user_id_not_blank",
            [
                "btrim(user_id) <> ''",
            ],
        ),
        (
            "role_id_not_blank",
            [
                "btrim(role_id) <> ''",
            ],
        ),
        (
            "granted_by_not_blank",
            [
                "granted_by IS NULL",
                "btrim(granted_by) <> ''",
            ],
        ),
        (
            "revoked_by_not_blank",
            [
                "revoked_by IS NULL",
                "btrim(revoked_by) <> ''",
            ],
        ),
        (
            "revocation_state_valid",
            [
                "status = 'active'",
                "revoked_at IS NULL",
                "status = 'revoked'",
                "revoked_at IS NOT NULL",
            ],
        ),
    ],
)
def test_grant_check_constraints(
        constraint_name: str,
        expected_fragments: list[str],
) -> None:
    """验证角色授予数据完整性约束"""
    constraint = get_constraint(
        constraint_name
    )
    constraint_sql = normalize_sql(
        constraint.sqltext
    )

    for fragment in expected_fragments:
        assert fragment in constraint_sql


@pytest.mark.parametrize(
    (
        "column_name",
        "expected_comment",
    ),
    [
        (
            "grant_id",
            "授予 ID，角色授予记录的唯一标识",
        ),
        (
            "user_id",
            "用户 ID",
        ),
        (
            "role_id",
            "角色 ID",
        ),
        (
            "status",
            (
                "授予状态，可选值："
                "active / revoked"
            ),
        ),
        (
            "granted_by",
            "授予用户 ID",
        ),
        (
            "granted_at",
            "授予时间",
        ),
        (
            "revoked_by",
            "撤销用户 ID",
        ),
        (
            "revoked_at",
            "撤销时间",
        ),
    ],
)
def test_grant_column_comments(
        column_name: str,
        expected_comment: str,
) -> None:
    """验证关键字段注释"""
    column = GRANT_TABLE.columns[
        column_name
    ]

    assert column.comment == expected_comment


# noinspection PyUnreachableCode
def test_active_grant_constructor() -> None:
    """验证有效角色授予模型构造"""
    grant = Grant(
        grant_id="grt_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status="active",
        granted_by="usr_admin",
        granted_at=GRANTED_AT,
    )

    assert grant.grant_id == (
        "grt_0123456789abcdef"
    )
    assert grant.user_id == (
        "usr_0123456789abcdef"
    )
    assert grant.role_id == (
        "rol_0123456789abcdef"
    )
    assert grant.status == "active"
    assert grant.granted_by == "usr_admin"
    assert grant.granted_at == GRANTED_AT
    assert grant.revoked_by is None
    assert grant.revoked_at is None


def test_revoked_grant_constructor() -> None:
    """验证已撤销角色授予模型构造"""
    grant = Grant(
        grant_id="grt_revoked",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status="revoked",
        granted_by="usr_admin",
        granted_at=GRANTED_AT,
        revoked_by="usr_operator",
        revoked_at=REVOKED_AT,
    )

    assert grant.status == "revoked"
    assert grant.granted_at == GRANTED_AT
    assert grant.revoked_by == "usr_operator"
    assert grant.revoked_at == REVOKED_AT


# noinspection PyUnreachableCode
def test_grant_allows_empty_optional_fields() -> None:
    """验证可选字段允许省略"""
    grant = Grant(
        grant_id="grt_minimum",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status="active",
        granted_at=GRANTED_AT,
    )

    assert grant.granted_by is None
    assert grant.revoked_by is None
    assert grant.revoked_at is None


def test_grant_repr() -> None:
    """验证角色授予字符串表示"""
    grant = Grant(
        grant_id="grt_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        role_id="rol_0123456789abcdef",
        status="active",
        granted_by="usr_admin",
        granted_at=GRANTED_AT,
    )

    representation = repr(
        grant
    )

    assert representation == (
        "<Grant("
        "grant_id='grt_0123456789abcdef', "
        "user_id='usr_0123456789abcdef', "
        "role_id='rol_0123456789abcdef', "
        "status='active'"
        ")>"
    )
    assert "granted_by" not in representation
    assert "revoked_by" not in representation
    assert GRANTED_AT.isoformat() not in representation
