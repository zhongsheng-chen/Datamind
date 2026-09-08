"""模型信息检查测试

验证评分卡刻度、变量质量和分箱明细的提取结果。

核心功能：
  - test_scorecard_inspector_extracts_details: 验证评分卡详情提取
  - test_scorecard_inspector_formats_bin_labels: 验证分箱标签格式化
  - test_scorecard_inspector_rejects_other_models: 验证模型类型校验
"""

import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from optbinning import Scorecard

from datamind.models.inspection import ScorecardInspector


def create_scorecard() -> Scorecard:
    """创建评分卡测试对象"""
    summary = pd.DataFrame([{
        "name": "age",
        "dtype": "numerical",
        "status": "OPTIMAL",
        "selected": True,
        "n_bins": 2,
        "iv": 0.2,
        "js": 0.03,
        "gini": 0.4,
        "quality_score": 0.7,
    }])
    scorecard = MagicMock(spec=Scorecard)
    scorecard.binning_process_ = SimpleNamespace(summary=lambda: summary)
    scorecard.scaling_method = "pdo_odds"
    scorecard.scaling_method_params = {
        "pdo": 40,
        "odds": 45,
        "scorecard_points": 650,
    }
    scorecard.intercept_based = False
    scorecard.reverse_scorecard = False
    scorecard.rounding = False
    scorecard.estimator_ = SimpleNamespace(classes_=[0, 1])
    scorecard.intercept_ = 0.25
    scorecard.table.return_value = pd.DataFrame([
        {"Variable": "age", "Bin": "(-inf, 30)", "Points": 100.0},
        {"Variable": "age", "Bin": "[30, inf)", "Points": 200.0},
    ])
    return cast(Scorecard, scorecard)


def test_scorecard_inspector_extracts_details() -> None:
    """测试提取评分卡刻度、质量和分箱明细"""
    details = ScorecardInspector.extract(create_scorecard())

    assert details["variable_count"] == 1
    assert details["selected_variable_count"] == 1
    assert details["scaling"]["minimum_score"] == 100.0
    assert details["scaling"]["maximum_score"] == 200.0
    assert details["variables"][0]["iv"] == 0.2
    assert details["variables"][0]["bins"][0]["Bin"] == "(-inf, 30)"


@pytest.mark.parametrize("selected", [True, False], ids=["selected", "unselected"])
@pytest.mark.parametrize(
    ("bin_value", "expected"),
    [
        pytest.param([np.str_("salaried")], "salaried", id="numpy-string-list"),
        pytest.param(
            [np.str_("contract"), np.str_("unemployed")],
            "contract, unemployed",
            id="grouped-numpy-strings",
        ),
        pytest.param(np.array(["salaried"]), "salaried", id="single-array"),
        pytest.param(
            np.array(["contract", "unemployed"]),
            "contract, unemployed",
            id="grouped-array",
        ),
        pytest.param(np.array("salaried"), "salaried", id="scalar-array"),
        pytest.param((np.str_("salaried"),), "salaried", id="tuple"),
        pytest.param([np.int64(1), np.int64(2)], "1, 2", id="numeric-categories"),
        pytest.param(
            [np.str_("a, b"), np.str_("O'Reilly"), np.str_("合同工")],
            "a, b, O'Reilly, 合同工",
            id="category-content",
        ),
        pytest.param(
            [np.str_("np.str_('salaried')")],
            "np.str_('salaried')",
            id="literal-category",
        ),
        pytest.param("[30, inf)", "[30, inf)", id="numerical-interval"),
        pytest.param("Special", "Special", id="special"),
        pytest.param("Missing", "Missing", id="missing"),
        pytest.param(None, None, id="null"),
    ],
)
def test_scorecard_inspector_formats_bin_labels(
        selected: bool,
        bin_value: Any,
        expected: str | None,
) -> None:
    """测试入模与未入模变量的分箱标签可读且不改变原始数据"""
    scorecard = create_scorecard()
    summary = pd.DataFrame([{
        "name": "employment_type",
        "dtype": "categorical",
        "selected": selected,
    }])
    frame = pd.DataFrame([{
        "Variable": "employment_type",
        "Bin": bin_value,
        "Points": np.float64(100.0),
        "Count": np.int64(4),
    }])
    binned_variable = SimpleNamespace(
        binning_table=SimpleNamespace(build=lambda **_kwargs: frame),
    )
    scorecard.binning_process_ = SimpleNamespace(
        summary=lambda: summary,
        get_binned_variable=lambda _name: binned_variable,
    )
    with patch.object(
            scorecard, "table",
            return_value=frame if selected else frame.iloc[:0],
    ):
        details = ScorecardInspector.extract(scorecard)

    variable = details["variables"][0]
    assert variable["selected"] is selected
    assert variable["bins"][0]["Bin"] == expected
    assert variable["bins"][0]["Points"] == 100.0
    assert variable["bins"][0]["Count"] == 4
    assert json.loads(json.dumps(details, allow_nan=False)) == details
    np.testing.assert_equal(frame.at[0, "Bin"], bin_value)


def test_scorecard_inspector_rejects_other_models() -> None:
    """测试拒绝非评分卡模型"""
    with pytest.raises(TypeError, match="评分任务模型类型不匹配"):
        ScorecardInspector.extract(object())
