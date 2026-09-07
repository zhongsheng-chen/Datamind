# tests/models/test_inspection.py

"""模型信息检查测试

验证评分卡刻度、变量质量和分箱明细的提取结果。

核心功能：
  - test_scorecard_inspector_extracts_details: 验证评分卡详情提取
  - test_scorecard_inspector_rejects_other_models: 验证模型类型校验
"""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

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


def test_scorecard_inspector_rejects_other_models() -> None:
    """测试拒绝非评分卡模型"""
    with pytest.raises(TypeError, match="评分任务模型类型不匹配"):
        ScorecardInspector.extract(object())
