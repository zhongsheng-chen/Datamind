"""配置参考文档测试.

验证源码说明读取、来源优先级、缺失说明诊断和校验消息提取。

核心功能：
  - test_documented_attributes_reads_multiline_environment_descriptions:
    测试属性和环境变量说明的读取及默认值描述去重
  - test_config_description_source_priority:
    测试字段说明的来源优先级及源码文档字符串回退
  - test_new_undocumented_config_field_fails_generation:
    测试配置字段缺少说明时生成失败
  - test_config_validators_extracts_static_messages:
    校验消息保留静态文本，忽略动态插值并清理当前值说明
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings

from doc_support.config import (
    config_description,
    config_validators,
    documented_attributes,
)


def test_documented_attributes_reads_multiline_environment_descriptions() -> None:
    """测试属性和环境变量说明的读取及默认值描述去重."""
    result = documented_attributes(
        """Configuration.

        Attributes:
          - interval: 协调间隔（秒）
        Environment:
          - DATAMIND_DOCS_ENABLED:
            是否启用，默认 false
          - empty:
          - other: 其他说明
        """
    )
    assert result == {
        "interval": "协调间隔（秒）",
        "DATAMIND_DOCS_ENABLED": "是否启用",
        "other": "其他说明",
    }


@pytest.mark.parametrize(
    ("field_description", "class_doc", "module_doc", "expected"),
    [
        ("字段说明", "- value: 类说明", "- value: 模块说明", "字段说明。"),
        (None, "- value: 类说明", "- value: 模块说明", "类说明。"),
        (None, None, "- value: 模块说明", "模块说明。"),
        (None, None, "- DOCS_TEST_VALUE:\n    环境变量说明", "环境变量说明。"),
    ],
)
def test_config_description_source_priority(
    monkeypatch: pytest.MonkeyPatch,
    field_description: str | None,
    class_doc: str | None,
    module_doc: str | None,
    expected: str,
) -> None:
    """测试字段说明的来源优先级及源码文档字符串回退."""

    class ExampleConfig(BaseSettings):
        """仅用于文档生成测试的配置."""

        model_config = {"env_prefix": "DOCS_TEST_"}
        value: str = Field(default="", description=field_description)

    ExampleConfig.__doc__ = class_doc
    monkeypatch.setattr(
        "doc_support.config.inspect.getmodule",
        lambda cls: SimpleNamespace(__doc__=module_doc),
    )
    assert (
        config_description(ExampleConfig, "value", ExampleConfig.model_fields["value"])
        == expected
    )


def test_new_undocumented_config_field_fails_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试配置字段缺少说明时生成失败."""

    class UndocumentedConfig(BaseSettings):
        """不提供属性说明."""

        model_config = {"env_prefix": "DOCS_TEST_"}
        value: str = ""

    monkeypatch.setattr(
        "doc_support.config.inspect.getmodule",
        lambda cls: SimpleNamespace(__doc__=None),
    )
    with pytest.raises(ValueError, match=r"UndocumentedConfig\.value"):
        config_description(
            UndocumentedConfig, "value", UndocumentedConfig.model_fields["value"]
        )


def test_config_validators_extracts_static_messages(
    tmp_path: Path, load_source: Callable[[Path], ModuleType]
) -> None:
    """校验消息保留静态文本，忽略动态插值并清理当前值说明."""
    source = tmp_path / "settings.py"
    source.write_text(
        """class Settings:
    def validate(self):
        raise ValueError("固定错误")
        raise ValueError(f"范围错误，当前值：{self.value}")
        raise ValueError(f"字段 {self.field} 无效")
        raise ValueError(123)
        raise ValueError("固定错误")
""",
        encoding="utf-8",
    )
    module = load_source(source)
    assert config_validators(module.Settings) == ["固定错误", "范围错误", "字段  无效"]
