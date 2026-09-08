"""管理控制台写操作结构测试

验证控制台请求的空白处理、列表规范化和字段边界。

核心功能：
  - test_console_request_strips_string_fields: 验证字符串空白处理
  - test_user_roles_are_normalized: 验证用户角色规范化
  - test_duplicate_user_roles_are_rejected: 验证重复角色拒绝
  - test_role_permissions_are_normalized: 验证角色权限规范化
  - test_invalid_model_registration_is_rejected: 验证模型注册字段约束
  - test_extra_fields_are_rejected: 验证未知字段拒绝
"""

import pytest
from pydantic import ValidationError

from datamind.console.schemas import (
    ModelRegistrationMetadata,
    ResourceActionRequest,
    RoleUpdateRequest,
    RoutingCreateRequest,
    RoutingUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
)


def test_routing_create_defaults_to_disabled() -> None:
    """测试新路由默认保持停用。"""
    request = RoutingCreateRequest(
        name="scorecard-route",
        deployment_id="dep_test",
    )

    assert request.enabled is False
    assert request.name == "scorecard-route"


def test_routing_requests_accept_effective_window() -> None:
    """测试路由创建和更新请求接受生效区间。"""
    created = RoutingCreateRequest(
        name="scorecard-route",
        deployment_id="dep_test",
        effective_from="2026-08-29T08:00",
        effective_to="2026-08-30T08:00",
    )
    updated = RoutingUpdateRequest(
        effective_from="2026-08-30T08:00",
        effective_to=None,
    )

    assert created.effective_from == "2026-08-29T08:00"
    assert created.effective_to == "2026-08-30T08:00"
    assert updated.effective_from == "2026-08-30T08:00"
    assert updated.effective_to is None


def test_console_request_strips_string_fields() -> None:
    """测试请求字符串自动移除首尾空白"""
    request = UserCreateRequest(
        username="  alice  ",
        password="secret",
        display_name="  Alice  ",
    )

    assert request.username == "alice"
    assert request.display_name == "Alice"


def test_user_roles_are_normalized() -> None:
    """测试用户角色移除空值并规范化空白"""
    created = UserCreateRequest(
        username="alice",
        password="secret",
        roles=[
            " viewer ",
            "",
            "operator",
        ],
    )
    updated = UserUpdateRequest(
        username="alice",
        roles=[
            " viewer ",
        ],
    )

    assert created.roles == [
        "viewer",
        "operator",
    ]
    assert updated.roles == [
        "viewer"
    ]


@pytest.mark.parametrize(
    "request_type, payload",
    [
        (
            UserCreateRequest,
            {
                "username": "alice",
                "password": "secret",
                "roles": ["viewer", " viewer "],
            },
        ),
        (
            UserUpdateRequest,
            {
                "username": "alice",
                "roles": ["viewer", " viewer "],
            },
        ),
    ],
)
def test_duplicate_user_roles_are_rejected(
        request_type,
        payload: dict[str, object],
) -> None:
    """测试规范化后重复的用户角色被拒绝"""
    with pytest.raises(
            ValidationError,
            match="角色不能重复",
    ):
        request_type(**payload)


def test_role_permissions_are_normalized() -> None:
    """测试角色权限移除空值并拒绝重复值"""
    request = RoleUpdateRequest(
        description="模型开发角色",
        permissions=[
            " model.read ",
            "",
            "model.write",
        ]
    )

    assert request.permissions == [
        "model.read",
        "model.write",
    ]

    with pytest.raises(
            ValidationError,
            match="权限不能重复",
    ):
        RoleUpdateRequest(
            description="模型开发角色",
            permissions=[
                "model.read",
                " model.read ",
            ]
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("name", "中文模型"),
        ("version", "release"),
    ],
)
def test_invalid_model_registration_is_rejected(
        field: str,
        value: str,
) -> None:
    """测试模型名称和版本不符合约束时被拒绝"""
    payload = {
        "name": "scorecard",
        "version": "1.0.0",
        "framework": "sklearn",
        "model_type": "logistic_regression",
        "task_type": "scoring",
        field: value,
    }

    with pytest.raises(ValidationError):
        ModelRegistrationMetadata(**payload)


def test_extra_fields_are_rejected() -> None:
    """测试控制台请求拒绝未声明字段"""
    with pytest.raises(
            ValidationError,
            match="Extra inputs are not permitted",
    ):
        ResourceActionRequest.model_validate(
            {
                "reason": "测试",
                "unexpected": True,
            }
        )
