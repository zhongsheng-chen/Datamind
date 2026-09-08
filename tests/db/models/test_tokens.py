"""认证令牌模型测试

验证认证令牌表名称、字段定义、服务端默认值、索引、
检查约束、字段注释和字符串表示。

核心功能：
  - test_token_table_name:
    验证认证令牌表名称
  - test_token_contains_mixin_columns:
    验证主键和时间戳混入字段
  - test_token_business_columns:
    验证认证令牌业务字段集合
  - test_token_string_columns:
    验证字符串字段长度和可空性
  - test_token_text_columns:
    验证文本字段定义
  - test_token_datetime_columns:
    验证时间字段定义
  - test_token_status_server_default:
    验证令牌状态服务端默认值
  - test_token_indexes:
    验证普通索引、联合索引和唯一索引
  - test_token_check_constraints:
    验证认证令牌数据完整性约束
  - test_token_column_comments:
    验证关键字段注释
  - test_active_token_constructor:
    验证有效刷新令牌模型构造
  - test_revoked_token_constructor:
    验证已撤销刷新令牌模型构造
  - test_token_allows_empty_optional_fields:
    验证可选字段允许省略
  - test_token_repr:
    验证认证令牌字符串表示和敏感信息隐藏
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
from sqlalchemy.dialects.postgresql import TEXT

from datamind.db.models.tokens import Token


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TOKEN_TABLE = get_model_table(
    Token.__table__
)

EXPIRES_AT = datetime(
    2026,
    8,
    2,
    8,
    30,
    tzinfo=timezone.utc,
)

LAST_USED_AT = datetime(
    2026,
    7,
    26,
    8,
    45,
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

TOKEN_HASH = (
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
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
    column = TOKEN_TABLE.columns[
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
    """按名称获取认证令牌表索引"""
    for index in TOKEN_TABLE.indexes:
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
    """按基础名称获取认证令牌表检查约束"""
    expected_name = (
        f"ck_{Token.__tablename__}_"
        f"{constraint_name}"
    )

    for constraint in TOKEN_TABLE.constraints:
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

    for constraint in TOKEN_TABLE.constraints:
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


def test_token_table_name() -> None:
    """验证认证令牌表名称"""
    assert Token.__tablename__ == "tokens"
    assert TOKEN_TABLE.name == "tokens"


def test_token_contains_mixin_columns() -> None:
    """验证主键和时间戳混入字段"""
    column_names = set(
        TOKEN_TABLE.columns.keys()
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
        for column in TOKEN_TABLE.primary_key.columns
    ]

    assert primary_key_columns == [
        "id"
    ]


def test_token_business_columns() -> None:
    """验证认证令牌业务字段集合"""
    column_names = set(
        TOKEN_TABLE.columns.keys()
    )

    assert {
        "token_id",
        "user_id",
        "token_hash",
        "status",
        "expires_at",
        "last_used_at",
        "revoked_at",
        "revoked_by",
        "revoke_reason",
        "ip",
        "hostname",
        "user_agent",
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
            "token_id",
            64,
            False,
        ),
        (
            "user_id",
            64,
            False,
        ),
        (
            "token_hash",
            128,
            False,
        ),
        (
            "status",
            20,
            False,
        ),
        (
            "revoked_by",
            64,
            True,
        ),
        (
            "ip",
            64,
            True,
        ),
        (
            "hostname",
            128,
            True,
        ),
    ],
)
def test_token_string_columns(
        column_name: str,
        expected_length: int,
        expected_nullable: bool,
) -> None:
    """验证字符串字段长度和可空性"""
    column = TOKEN_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        String,
    )
    assert column.type.length == expected_length
    assert column.nullable is expected_nullable


@pytest.mark.parametrize(
    "column_name",
    [
        "revoke_reason",
        "user_agent",
    ],
)
def test_token_text_columns(
        column_name: str,
) -> None:
    """验证文本字段定义"""
    column = TOKEN_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        TEXT,
    )
    assert column.nullable is True


@pytest.mark.parametrize(
    (
        "column_name",
        "expected_nullable",
    ),
    [
        (
            "expires_at",
            False,
        ),
        (
            "last_used_at",
            True,
        ),
        (
            "revoked_at",
            True,
        ),
    ],
)
def test_token_datetime_columns(
        column_name: str,
        expected_nullable: bool,
) -> None:
    """验证时间字段定义"""
    column = TOKEN_TABLE.columns[
        column_name
    ]

    assert isinstance(
        column.type,
        DateTime,
    )
    assert column.type.timezone is True
    assert column.nullable is expected_nullable


def test_token_status_server_default() -> None:
    """验证令牌状态服务端默认值"""
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
            "idx_tokens_user_id",
            [
                "user_id"
            ],
            False,
        ),
        (
            "idx_tokens_status",
            [
                "status"
            ],
            False,
        ),
        (
            "idx_tokens_expires_at",
            [
                "expires_at"
            ],
            False,
        ),
        (
            "idx_tokens_last_used_at",
            [
                "last_used_at"
            ],
            False,
        ),
        (
            "idx_tokens_user_status",
            [
                "user_id",
                "status",
            ],
            False,
        ),
        (
            "uk_tokens_token_id",
            [
                "token_id"
            ],
            True,
        ),
        (
            "uk_tokens_token_hash",
            [
                "token_hash"
            ],
            True,
        ),
    ],
)
def test_token_indexes(
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
            "token_hash_not_blank",
            [
                "btrim(token_hash) <> ''",
            ],
        ),
        (
            "expires_at_after_created_at",
            [
                "expires_at > created_at",
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
        (
            "revoked_by_not_blank",
            [
                "revoked_by IS NULL",
                "btrim(revoked_by) <> ''",
            ],
        ),
    ],
)
def test_token_check_constraints(
        constraint_name: str,
        expected_fragments: list[str],
) -> None:
    """验证认证令牌数据完整性约束"""
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
            "token_id",
            "令牌 ID，刷新令牌记录的唯一标识",
        ),
        (
            "user_id",
            "用户 ID",
        ),
        (
            "token_hash",
            "刷新令牌哈希",
        ),
        (
            "status",
            (
                "令牌状态，可选值："
                "active / revoked"
            ),
        ),
        (
            "expires_at",
            "令牌过期时间",
        ),
        (
            "last_used_at",
            "最近使用时间",
        ),
        (
            "revoked_at",
            "撤销时间",
        ),
        (
            "revoked_by",
            "撤销用户 ID",
        ),
        (
            "revoke_reason",
            "撤销原因",
        ),
        (
            "ip",
            "登录客户端 IP 地址",
        ),
        (
            "hostname",
            "登录客户端主机名称",
        ),
        (
            "user_agent",
            "登录客户端 User-Agent",
        ),
    ],
)
def test_token_column_comments(
        column_name: str,
        expected_comment: str,
) -> None:
    """验证关键字段注释"""
    column = TOKEN_TABLE.columns[
        column_name
    ]

    assert column.comment == expected_comment


# noinspection PyUnreachableCode
def test_active_token_constructor() -> None:
    """验证有效刷新令牌模型构造"""
    token_record = Token(
        token_id="tok_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        status="active",
        expires_at=EXPIRES_AT,
        last_used_at=LAST_USED_AT,
        ip="192.168.1.100",
        hostname="client",
        user_agent="Datamind CLI",
    )

    assert token_record.token_id == (
        "tok_0123456789abcdef"
    )
    assert token_record.user_id == (
        "usr_0123456789abcdef"
    )
    assert token_record.token_hash == TOKEN_HASH
    assert token_record.status == "active"
    assert token_record.expires_at == EXPIRES_AT
    assert token_record.last_used_at == (
        LAST_USED_AT
    )
    assert token_record.revoked_at is None
    assert token_record.revoked_by is None
    assert token_record.revoke_reason is None
    assert token_record.ip == "192.168.1.100"
    assert token_record.hostname == "client"
    assert token_record.user_agent == (
        "Datamind CLI"
    )


def test_revoked_token_constructor() -> None:
    """验证已撤销刷新令牌模型构造"""
    token_record = Token(
        token_id="tok_revoked",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        status="revoked",
        expires_at=EXPIRES_AT,
        last_used_at=LAST_USED_AT,
        revoked_at=REVOKED_AT,
        revoked_by="usr_admin",
        revoke_reason="logout",
    )

    assert token_record.status == "revoked"
    assert token_record.revoked_at == REVOKED_AT
    assert token_record.revoked_by == "usr_admin"
    assert token_record.revoke_reason == "logout"


# noinspection PyUnreachableCode
def test_token_allows_empty_optional_fields() -> None:
    """验证可选字段允许省略"""
    token_record = Token(
        token_id="tok_minimum",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        status="active",
        expires_at=EXPIRES_AT,
    )

    assert token_record.last_used_at is None
    assert token_record.revoked_at is None
    assert token_record.revoked_by is None
    assert token_record.revoke_reason is None
    assert token_record.ip is None
    assert token_record.hostname is None
    assert token_record.user_agent is None


def test_token_repr() -> None:
    """验证认证令牌字符串表示和敏感信息隐藏"""
    token_record = Token(
        token_id="tok_0123456789abcdef",
        user_id="usr_0123456789abcdef",
        token_hash=TOKEN_HASH,
        status="active",
        expires_at=EXPIRES_AT,
        ip="192.168.1.100",
        hostname="client",
        user_agent="Datamind CLI",
    )

    representation = repr(
        token_record
    )

    assert representation == (
        "<Token("
        "token_id='tok_0123456789abcdef', "
        "user_id='usr_0123456789abcdef', "
        "status='active', "
        f"expires_at='{EXPIRES_AT}'"
        ")>"
    )
    assert TOKEN_HASH not in representation
    assert "token_hash" not in representation
    assert "192.168.1.100" not in representation
    assert "Datamind CLI" not in representation
