"""参考文档模板测试.

验证占位符完整性和替换值中的字面文本保留。

核心功能：
  - test_template_requires_all_placeholders:
    模板缺少上下文时立即失败，避免发布未填充的占位符
  - test_template_preserves_literal_dollar_in_values:
    源码说明中的美元符号和模板语法不会被二次替换
"""

import pytest

from doc_support.common import render_template


def test_template_requires_all_placeholders() -> None:
    """模板缺少上下文时立即失败，避免发布未填充的占位符."""
    with pytest.raises(KeyError, match="guide"):
        render_template("cli-group", title="模型管理")


def test_template_preserves_literal_dollar_in_values() -> None:
    """源码说明中的美元符号和模板语法不会被二次替换."""
    title = "${literal} costs $5"
    text = render_template("cli-group", title=title, guide="guide.md", commands="")
    assert text.startswith(f"# {title}\n")
