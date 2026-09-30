"""Validate documentation source descriptions and missing-field diagnostics."""

from types import SimpleNamespace

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings

from scripts.generate_docs_reference import config_description, documented_attributes


def test_documented_attributes_reads_multiline_environment_descriptions():
    """Read both attribute and environment entries without duplicating defaults."""
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
    monkeypatch, field_description, class_doc, module_doc, expected
):
    """Prefer explicit field metadata and support source docstring fallbacks."""

    class ExampleConfig(BaseSettings):
        """A documentation-only configuration fixture."""

        model_config = {"env_prefix": "DOCS_TEST_"}
        value: str = Field(default="", description=field_description)

    ExampleConfig.__doc__ = class_doc
    monkeypatch.setattr(
        "scripts.generate_docs_reference.inspect.getmodule",
        lambda cls: SimpleNamespace(__doc__=module_doc),
    )
    assert (
        config_description(ExampleConfig, "value", ExampleConfig.model_fields["value"])
        == expected
    )


def test_new_undocumented_config_field_fails_generation(monkeypatch):
    """Prevent future fields from silently generating a blank description."""

    class UndocumentedConfig(BaseSettings):
        """No attribute descriptions."""

        model_config = {"env_prefix": "DOCS_TEST_"}
        value: str = ""

    monkeypatch.setattr(
        "scripts.generate_docs_reference.inspect.getmodule",
        lambda cls: SimpleNamespace(__doc__=None),
    )
    with pytest.raises(ValueError, match=r"UndocumentedConfig\.value"):
        config_description(
            UndocumentedConfig, "value", UndocumentedConfig.model_fields["value"]
        )
