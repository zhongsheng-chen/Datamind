"""用户表模型测试

验证仅支持 LOCAL 认证后的用户表字段、索引、约束和对象行为。

核心功能：
  - test_user_table_name:
    验证用户表名称
  - test_user_business_columns:
    验证用户表业务字段完整
  - test_password_hash_is_required:
    验证所有用户必须保存密码哈希
  - test_user_status_defaults_to_active:
    验证用户状态默认值
  - test_break_glass_defaults_to_false:
    验证应急账户标识默认值
  - test_user_indexes:
    验证用户表索引
  - test_user_check_constraints:
    验证用户表检查约束
  - test_user_constructor:
    验证用户对象构造
  - test_user_repr:
    验证用户字符串表示不泄露密码"""

from sqlalchemy import (
    CheckConstraint,
    Index,
    String,
    Table,
)

from datamind.db.models.users import User


def get_model_table(
        value: object,
) -> Table:
    """获取并校验模型数据表"""
    assert isinstance(value, Table)
    return value


TABLE = get_model_table(
    User.__table__
)


def test_user_table_name() -> None:
    """验证用户表名称"""
    assert TABLE.name == "users"


def test_user_business_columns() -> None:
    """验证用户表业务字段完整"""
    assert set(TABLE.columns.keys()) >= {
        "user_id",
        "username",
        "password_hash",
        "display_name",
        "email",
        "status",
        "is_break_glass",
        "failed_login_count",
        "locked_until",
        "last_login_at",
        "password_changed_at",
        "created_by",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
    }


def test_password_hash_is_required() -> None:
    """验证所有用户必须保存密码哈希"""
    column = TABLE.columns[
        "password_hash"
    ]

    assert isinstance(
        column.type,
        String,
    )
    assert column.type.length == 512
    assert column.nullable is False
    assert column.comment == "密码哈希"


def test_user_status_defaults_to_active() -> None:
    """验证用户状态默认值"""
    column = TABLE.columns[
        "status"
    ]

    assert column.nullable is False
    assert str(column.server_default.arg) == "'active'"


def test_break_glass_defaults_to_false() -> None:
    """验证应急账户标识默认值"""
    column = TABLE.columns[
        "is_break_glass"
    ]

    assert column.nullable is False
    assert str(column.server_default.arg) == "false"


def test_user_indexes() -> None:
    """验证用户表索引"""
    indexes: dict[str, Index] = {
        index.name: index
        for index in TABLE.indexes
        if index.name is not None
    }

    assert set(indexes) >= {
        "idx_users_status",
        "idx_users_created_at",
        "idx_users_deleted_at",
        "uk_users_user_id",
        "uk_users_username",
        "uk_users_email",
    }
    assert indexes["uk_users_user_id"].unique is True
    assert indexes["uk_users_username"].unique is True
    assert indexes["uk_users_email"].unique is True


def test_user_check_constraints() -> None:
    """验证用户表检查约束"""
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

    assert "ck_users_status_valid" in constraints
    assert "ck_users_failed_login_count_non_negative" in constraints
    assert "ck_users_username_not_blank" in constraints
    assert "ck_users_password_hash_not_blank" in constraints
    assert "ck_users_email_not_blank" in constraints
    assert "btrim(password_hash) <> ''" in constraints[
        "ck_users_password_hash_not_blank"
    ]


def test_user_constructor() -> None:
    """验证用户对象构造"""
    user = User(
        user_id="usr_test",
        username="admin",
        password_hash="$argon2id$test",
        status="active",
        is_break_glass=False,
    )

    assert user.user_id == "usr_test"
    assert user.username == "admin"
    assert user.password_hash == "$argon2id$test"
    assert user.status == "active"
    assert user.is_break_glass is False


def test_user_repr() -> None:
    """验证用户字符串表示不泄露密码"""
    user = User(
        user_id="usr_test",
        username="admin",
        password_hash="secret-hash",
        status="active",
        is_break_glass=True,
    )

    result = repr(user)

    assert "user_id='usr_test'" in result
    assert "username='admin'" in result
    assert "status='active'" in result
    assert "is_break_glass=True" in result
    assert "secret-hash" not in result
