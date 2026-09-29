"""ID 生成工具测试.

验证确定性 ID、随机 ID、格式长度、键值编码和参数校验。

核心功能：
  - test_id_length_constant:
    验证 ID 主体长度常量
  - test_generate_id_returns_stable_result:
    验证相同输入始终生成相同 ID
  - test_generate_id_uses_expected_format:
    验证确定性 ID 的前缀和哈希格式
  - test_generate_id_changes_when_prefix_changes:
    验证前缀变化会生成不同 ID
  - test_generate_id_changes_when_key_changes:
    验证任一键值变化会生成不同 ID
  - test_generate_id_preserves_key_order:
    验证键值顺序参与 ID 计算
  - test_generate_id_avoids_delimiter_ambiguity:
    验证不同键值组合不会因分隔符产生歧义
  - test_generate_id_distinguishes_single_and_multiple_keys:
    验证单个组合键与多个独立键生成不同 ID
  - test_generate_id_supports_unicode_keys:
    验证支持中文及其他 Unicode 键值
  - test_generate_id_rejects_blank_prefix:
    验证确定性 ID 拒绝空白前缀
  - test_generate_id_rejects_empty_keys:
    验证确定性 ID 拒绝空键值元组
  - test_generate_random_id_uses_expected_format:
    验证随机 ID 的前缀和 UUID 格式
  - test_generate_random_id_uses_uuid4_each_time:
    验证每次生成随机 ID 都调用 UUID4
  - test_generate_random_id_rejects_blank_prefix:
    验证随机 ID 拒绝空白前缀
"""

import re
import uuid

import pytest

import datamind.utils.generator as generator_utils


def test_id_length_constant() -> None:
    """测试 ID 主体长度常量."""
    assert generator_utils.ID_LENGTH == 16


def test_generate_id_returns_stable_result() -> None:
    """测试相同输入始终生成相同 ID."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-001",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-001",
        ),
    )

    assert first == second


def test_generate_id_uses_expected_format() -> None:
    """测试确定性 ID 的前缀和哈希格式."""
    result = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-001",
        ),
    )

    assert re.fullmatch(
        r"ent_[0-9a-f]{16}",
        result,
    )


def test_generate_id_changes_when_prefix_changes() -> None:
    """测试前缀变化会生成不同 ID."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-001",
        ),
    )
    second = generator_utils.generate_id(
        prefix="evt",
        keys=(
            "group-a",
            "item-001",
        ),
    )

    assert first != second
    assert first.startswith(
        "ent_"
    )
    assert second.startswith(
        "evt_"
    )


def test_generate_id_changes_when_key_changes() -> None:
    """测试任一键值变化会生成不同 ID."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-001",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group-a",
            "item-002",
        ),
    )

    assert first != second


def test_generate_id_preserves_key_order() -> None:
    """测试键值顺序参与 ID 计算."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "a",
            "b",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "b",
            "a",
        ),
    )

    assert first != second


def test_generate_id_avoids_delimiter_ambiguity() -> None:
    """测试不同键值组合不会因分隔符产生歧义."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group:a",
            "item",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "group",
            "a:item",
        ),
    )

    assert first != second


def test_generate_id_distinguishes_single_and_multiple_keys() -> None:
    """测试单个组合键与多个独立键生成不同 ID."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "a:b",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "a",
            "b",
        ),
    )

    assert first != second


def test_generate_id_supports_unicode_keys() -> None:
    """测试支持中文及其他 Unicode 键值."""
    first = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "客户",
            "申请编号-001",
        ),
    )
    second = generator_utils.generate_id(
        prefix="ent",
        keys=(
            "客户",
            "申请编号-001",
        ),
    )

    assert first == second
    assert re.fullmatch(
        r"ent_[0-9a-f]{16}",
        first,
    )


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        " ",
        "   ",
        "\t",
        "\n",
    ],
)
def test_generate_id_rejects_blank_prefix(
        prefix: str,
) -> None:
    """测试确定性 ID 拒绝空白前缀."""
    with pytest.raises(
        ValueError,
        match="prefix 不能为空",
    ):
        generator_utils.generate_id(
            prefix=prefix,
            keys=(
                "key",
            ),
        )


def test_generate_id_rejects_empty_keys() -> None:
    """测试确定性 ID 拒绝空键值元组."""
    with pytest.raises(
        ValueError,
        match="keys 不能为空",
    ):
        generator_utils.generate_id(
            prefix="ent",
            keys=(),
        )


def test_generate_random_id_uses_expected_format(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试随机 ID 的前缀和 UUID 格式."""
    fixed_uuid = uuid.UUID(
        "12345678-90ab-cdef-1234-567890abcdef"
    )
    monkeypatch.setitem(
        vars(generator_utils.uuid),
        "uuid4",
        lambda: fixed_uuid,
    )

    result = generator_utils.generate_random_id(
        prefix="evt"
    )

    assert result == "evt_1234567890abcdef"


def test_generate_random_id_uses_uuid4_each_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试每次生成随机 ID 都调用 UUID4."""
    generated = iter(
        (
            uuid.UUID(
                "11111111-1111-1111-1111-111111111111"
            ),
            uuid.UUID(
                "22222222-2222-2222-2222-222222222222"
            ),
        )
    )
    call_count = 0

    def generate_uuid() -> uuid.UUID:
        nonlocal call_count

        call_count += 1
        return next(
            generated
        )

    monkeypatch.setitem(
        vars(generator_utils.uuid),
        "uuid4",
        generate_uuid,
    )

    first = generator_utils.generate_random_id(
        prefix="evt"
    )
    second = generator_utils.generate_random_id(
        prefix="evt"
    )

    assert first == "evt_1111111111111111"
    assert second == "evt_2222222222222222"
    assert first != second
    assert call_count == 2


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        " ",
        "   ",
        "\t",
        "\n",
    ],
)
def test_generate_random_id_rejects_blank_prefix(
        prefix: str,
) -> None:
    """测试随机 ID 拒绝空白前缀."""
    with pytest.raises(
        ValueError,
        match="prefix 不能为空",
    ):
        generator_utils.generate_random_id(
            prefix=prefix
        )
