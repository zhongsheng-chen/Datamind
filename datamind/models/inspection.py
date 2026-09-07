# datamind/models/inspection.py

"""模型信息提取器

提取注册模型中适合持久化展示的解释与诊断信息。

核心功能：
  - extract: 提取评分卡信息

返回格式示例：
    {
        "scaling": {
            "method": "pdo_odds",
            "parameters": {
                "pdo": 40.0,
                "odds": 45.0,
                "scorecard_points": 650.0
            },
            "minimum_score": 228.50,
            "maximum_score": 729.91
        },
        "estimator": {
            "class_name": "LogisticRegression",
            "classes": [0, 1],
            "intercept": -1.25
        },
        "variable_count": 8,
        "selected_variable_count": 8,
        "variables": [
            {
                "name": "age",
                "dtype": "numerical",
                "status": "OPTIMAL",
                "selected": true,
                "n_bins": 5,
                "iv": 0.07,
                "bins": []
            }
        ]
    }

使用示例：
  from datamind.models.inspection import ScorecardInspector

  details = ScorecardInspector.extract(
      model
  )
"""

import math
from typing import Any

from optbinning import Scorecard


class ScorecardInspector:
    """评分卡信息提取器"""

    @classmethod
    def extract(cls, model: Any) -> dict[str, Any]:
        """提取已拟合评分卡信息

        参数：
            model: 已拟合的评分卡模型

        返回：
            包含评分刻度、估计器、变量质量和分箱明细的字典

        异常：
            TypeError: 模型不是评分卡
        """
        if not isinstance(model, Scorecard):
            raise TypeError(
                "评分任务模型类型不匹配："
                f"期望 {Scorecard.__name__}，实际 {type(model).__name__}"
            )
        binning_process = model.binning_process_
        summaries = cls._records(binning_process.summary())
        scorecard_rows = cls._records(model.table(style="detailed"))
        scorecard_by_variable: dict[str, list[dict[str, Any]]] = {}
        for row in scorecard_rows:
            scorecard_by_variable.setdefault(
                str(row["Variable"]),
                [],
            ).append(row)

        variables = []
        for summary in summaries:
            name = str(summary["name"])
            rows = scorecard_by_variable.get(name)
            if rows is None:
                binned_variable = binning_process.get_binned_variable(name)
                rows = cls._records(
                    binned_variable.binning_table.build(
                        show_digits=4,
                        add_totals=False,
                    )
                )
            variables.append({
                "name": name,
                "dtype": summary.get("dtype"),
                "status": summary.get("status"),
                "selected": bool(summary.get("selected")),
                "n_bins": summary.get("n_bins"),
                "iv": summary.get("iv"),
                "js": summary.get("js"),
                "gini": summary.get("gini"),
                "quality_score": summary.get("quality_score"),
                "bins": rows,
            })

        points_by_variable: dict[str, list[float]] = {}
        for row in scorecard_rows:
            points = row.get("Points")
            if not isinstance(points, (int, float)):
                continue
            points_by_variable.setdefault(
                str(row["Variable"]),
                [],
            ).append(float(points))

        scaling_parameters = {
            str(key): cls._value(value)
            for key, value in (model.scaling_method_params or {}).items()
        }
        estimator = model.estimator_
        return {
            "scaling": {
                "method": model.scaling_method,
                "parameters": scaling_parameters,
                "intercept_based": bool(model.intercept_based),
                "reverse_scorecard": bool(model.reverse_scorecard),
                "rounding": bool(model.rounding),
                "minimum_score": sum(
                    min(points) for points in points_by_variable.values()
                ),
                "maximum_score": sum(
                    max(points) for points in points_by_variable.values()
                ),
            },
            "estimator": {
                "class_name": type(estimator).__name__,
                "classes": [
                    cls._value(item)
                    for item in getattr(estimator, "classes_", [])
                ],
                "intercept": cls._value(getattr(model, "intercept_", None)),
            },
            "variable_count": len(variables),
            "selected_variable_count": sum(
                variable["selected"] for variable in variables
            ),
            "variables": variables,
        }

    @staticmethod
    def _value(value: Any) -> Any:
        """将值转换为 JSON 兼容类型

        参数：
            value: 原始值

        返回：
            JSON 兼容值
        """
        if hasattr(value, "item"):
            try:
                value = value.item()
            except (TypeError, ValueError):
                pass
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @classmethod
    def _records(cls, frame: Any) -> list[dict[str, Any]]:
        """转换 DataFrame 记录

        参数：
            frame: pandas DataFrame 对象

        返回：
            由 JSON 兼容值组成的记录列表
        """
        return [
            {
                str(key): cls._value(value)
                for key, value in record.items()
            }
            for record in frame.to_dict(orient="records")
        ]
