"""模型枚举测试

验证模型生命周期、部署、实验和决策枚举的稳定取值。

核心功能：
  - test_enum_values_match_contract:
    验证各枚举的公共取值契约
  - test_base_enum_returns_string_value:
    验证字符串枚举转换结果
  - test_enum_uses_string_dictionary_semantics:
    验证枚举与字符串的字典键语义
"""

import pytest

from datamind.models.enums import (
    AssignmentStrategy,
    ArtifactStatus,
    BaseEnum,
    DecisionResult,
    DecisionStrategy,
    DeploymentRole,
    DeploymentStatus,
    ExperimentStatus,
    ExperimentVariantStatus,
    ExecutionStatus,
    ExecutionType,
    MetadataStatus,
    RolloutType,
    RuntimeControlStatus,
    VersionStatus,
)


ENUM_CONTRACTS: list[
    tuple[type[BaseEnum], set[str]]
] = [
    (
        MetadataStatus,
        {"active", "deprecated", "inactive", "archived"},
    ),
    (
        VersionStatus,
        {"active", "deprecated", "inactive", "archived"},
    ),
    (
        ArtifactStatus,
        {"active", "retired", "purge_pending", "purged", "purge_failed"},
    ),
    (
        DeploymentStatus,
        {"active", "inactive"},
    ),
    (
        RolloutType,
        {"full", "canary", "shadow"},
    ),
    (
        DeploymentRole,
        {"champion", "challenger", "shadow"},
    ),
    (
        RuntimeControlStatus,
        {"loaded", "unloaded"},
    ),
    (
        ExperimentStatus,
        {"draft", "running", "paused", "stopped", "completed", "archived"},
    ),
    (
        ExperimentVariantStatus,
        {"active", "inactive", "archived"},
    ),
    (
        AssignmentStrategy,
        {"hash", "manual"},
    ),
    (
        DecisionStrategy,
        {"experiment", "routing", "deployment", "shadow", "manual"},
    ),
    (
        DecisionResult,
        {"approve", "reject"},
    ),
    (
        ExecutionType,
        {"primary", "shadow"},
    ),
    (
        ExecutionStatus,
        {
            "queued",
            "running",
            "success",
            "failed",
            "timeout",
            "cancelled",
        },
    ),
]


@pytest.mark.parametrize(
    ("enum_type", "expected_values"),
    ENUM_CONTRACTS,
)
def test_enum_values_match_contract(
        enum_type: type[BaseEnum],
        expected_values: set[str],
) -> None:
    """测试模型枚举取值符合公共契约"""
    assert {
        member.value
        for member in enum_type
    } == expected_values


@pytest.mark.parametrize(
    "member",
    [
        enum_type(next(iter(expected_values)))
        for enum_type, expected_values in ENUM_CONTRACTS
    ],
)
def test_base_enum_returns_string_value(
        member: BaseEnum,
) -> None:
    """测试字符串枚举转换为原始取值"""
    assert str(member) == member.value


def test_enum_uses_string_dictionary_semantics() -> None:
    """测试枚举与字符串共享字典键语义"""
    values: dict[str, str] = {
        MetadataStatus.ACTIVE: "matched"
    }

    assert values["active"] == "matched"
