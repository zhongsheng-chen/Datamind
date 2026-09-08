"""角色模型测试

验证角色表名称、字段定义、服务端默认值、索引、
检查约束、字段注释和字符串表示。

核心功能：
  - test_role_table_name:
    验证角色表名称
  - test_role_contains_mixin_columns:
    验证主键和时间戳混入字段
  - test_role_business_columns:
    验证角色业务字段集合
  - test_role_string_columns:
    验证字符串字段长度和可空性
  - test_role_description_column:
    验证角色说明字段
  - test_role_permissions_column:
    验证权限 JSON 字段
  - test_role_status_default:
    验证角色状态服务端默认值
  - test_role_indexes:
    验证普通索引和唯一索引
  - test_role_check_constraints:
    验证角色数据完整性约束
  - test_role_column_comments:
    验证关键字段注释
  - test_role_constructor:
    验证角色模型构造
  - test_role_allows_empty_optional_fields:
    验证可选字段允许省略
  - test_role_repr:
    验证角色字符串表示
"""

from typing import Any

import pytest
from sqlalchemy import (
    CheckConstraint,
    Index,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    TEXT,
)

from datamind.db.models.roles import Role


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


ROLE_TABLE = get_model_table(
    Role.__table__
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
    column = ROLE_TABLE.columns[
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
    """按名称获取角色表索引"""
    for index in ROLE_TABLE.indexes:
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
    """按基础名称获取角色表检查约束"""
    expected_name = (
        f"ck_{Role.__tablename__}_"
        f"{constraint_name}"
    )

    for constraint in ROLE_TABLE.constraints:
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

    for constraint in ROLE_TABLE.constraints:
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


def test_role_table_name() -> None:
    """验证角色表名称"""
    assert Role.__tablename__ == "roles"
    assert ROLE_TABLE.name == "roles"


def test_role_contains_mixin_columns() -> None:
    """验证主键和时间戳混入字段"""
    column_names = set(
        ROLE_TABLE.columns.keys()
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
        for column in ROLE_TABLE.primary_key.columns
    ]

    assert primary_key_columns == [
        "id"
    ]


def test_role_business_columns() -> None:
    """验证角色业务字段集合"""
    column_names = set(
        ROLE_TABLE.columns.keys()
    )

    assert {
        "role_id",
        "name",
        "description",
        "permissions",
        "status",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
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
            "role_id",
            64,
            False,
        ),
        (
            "name",
            64,
            False,
        ),
        (
            "status",
            20,
            False,
        ),
        (
            "created_by",
            64,
            True,
        ),
        (
            "updated_by",
            64,
            True,
        ),
    ],
)
def test_role_string_columns(
        column_name: str,
        expected_length: int,
        expected_nullable: bool,
) -> None:
    """验证字符串字段长度和可空性"""
    column = ROLE_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        String,
    )
    assert column.type.length == expected_length
    assert column.nullable is expected_nullable


def test_role_description_column() -> None:
    """验证角色说明字段"""
    column = ROLE_TABLE.columns[
        "description"
    ]

    assert isinstance(
        column.type,
        TEXT,
    )
    assert column.nullable is True


def test_role_permissions_column() -> None:
    """验证权限 JSON 字段"""
    column = ROLE_TABLE.columns[
        "permissions"
    ]

    assert isinstance(
        column.type,
        JSONB,
    )
    assert column.nullable is True


def test_role_status_default() -> None:
    """验证角色状态服务端默认值"""
    assert get_server_default(
        "status"
    ) == "'active'"


@pytest.mark.parametrize(
    (
        "index_name",
        "expected_columns",
        "expected_unique",
    ),
    [
        (
            "idx_roles_status",
            [
                "status"
            ],
            False,
        ),
        (
            "idx_roles_created_at",
            [
                "created_at"
            ],
            False,
        ),
        (
            "idx_roles_deleted_at",
            [
                "deleted_at"
            ],
            False,
        ),
        (
            "uk_roles_role_id",
            [
                "role_id"
            ],
            True,
        ),
        (
            "uk_roles_name",
            [
                "name"
            ],
            True,
        ),
    ],
)
def test_role_indexes(
        index_name: str,
        expected_columns: list[str],
        expected_unique: bool,
) -> None:
    """验证普通索引和唯一索引"""
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
            "name_not_blank",
            [
                "btrim(name) <> ''",
            ],
        ),
        (
            "status_valid",
            [
                "status IN",
                "'active'",
                "'inactive'",
            ],
        ),
        (
            "permissions_array",
            [
                "permissions IS NULL",
                (
                    "jsonb_typeof(permissions) "
                    "= 'array'"
                ),
            ],
        ),
    ],
)
def test_role_check_constraints(
        constraint_name: str,
        expected_fragments: list[str],
) -> None:
    """验证角色数据完整性约束"""
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
            "role_id",
            "角色 ID，角色的唯一标识",
        ),
        (
            "name",
            "角色名称",
        ),
        (
            "description",
            "角色说明",
        ),
        (
            "permissions",
            (
                "权限标识列表，JSON 数组。"
                "权限格式为 resource.operation"
            ),
        ),
        (
            "created_by",
            "创建用户 ID",
        ),
        (
            "updated_by",
            "更新用户 ID",
        ),
    ],
)
def test_role_column_comments(
        column_name: str,
        expected_comment: str,
) -> None:
    """验证关键字段注释"""
    column = ROLE_TABLE.columns[
        column_name
    ]

    assert column.comment == expected_comment


def test_role_constructor() -> None:
    """验证角色模型构造"""
    permissions = [
        "model.*",
        "deploy.*",
        "experiment.*",
        "user.*",
    ]
    role = Role(
        role_id="rol_0123456789abcdef",
        name="admin",
        description="系统管理员",
        permissions=permissions,
        status="active",
        created_by="usr_admin",
        updated_by="usr_operator",
    )

    assert role.role_id == (
        "rol_0123456789abcdef"
    )
    assert role.name == "admin"
    assert role.description == "系统管理员"
    assert role.permissions == permissions
    assert role.status == "active"
    assert role.created_by == "usr_admin"
    assert role.updated_by == "usr_operator"


# noinspection PyUnreachableCode
def test_role_allows_empty_optional_fields() -> None:
    """验证可选字段允许省略"""
    role = Role(
        role_id="rol_reader",
        name="reader",
        status="active",
    )

    assert role.description is None
    assert role.permissions is None
    assert role.created_by is None
    assert role.updated_by is None


def test_role_repr() -> None:
    """验证角色字符串表示"""
    permissions = [
        "model.*",
        "deploy.*",
    ]
    role = Role(
        role_id="rol_0123456789abcdef",
        name="admin",
        description="系统管理员",
        permissions=permissions,
        status="active",
    )

    representation = repr(
        role
    )

    assert representation == (
        "<Role("
        "role_id='rol_0123456789abcdef', "
        "name='admin', "
        "status='active'"
        ")>"
    )
    assert "permissions" not in representation
    assert "model.*" not in representation
    assert "系统管理员" not in representation
