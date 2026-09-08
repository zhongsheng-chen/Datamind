"""评分卡运行服务测试

验证单条与批量评分、特征评分明细、决策阈值和模型能力约束。

核心功能：
  - test_predict_uses_scorecard_points:
    验证单条预测使用评分卡分值表
  - test_predict_batch_uses_scorecard_points:
    验证批量预测使用评分卡分值表
  - test_predict_reuses_feature_frame:
    验证概率预测与评分复用特征表
  - test_real_scorecard_returns_features:
    验证真实评分卡的分箱命中、特征分与总分一致
  - test_predict_uses_probability_for_default_label:
    验证根据模型类别顺序提取违约概率
  - test_predict_rejects_invalid_probability_output:
    验证拒绝无效概率预测结果
  - test_score_below_threshold_is_rejected:
    验证低于阈值的分数被拒绝
  - test_service_exposes_scoring_capabilities:
    验证评分服务公开固定能力
  - test_rejects_model_without_score:
    验证拒绝不支持评分的模型
"""

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from optbinning import BinningProcess, Scorecard
from sklearn.linear_model import LogisticRegression

from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.scoring_service import ScoringService


class ScorecardStub:
    """OptBinning Scorecard 替身"""

    def __init__(self) -> None:
        """创建具有可核对分箱明细的评分卡替身"""
        self.estimator_ = SimpleNamespace(classes_=np.array([0, 1]))
        self._metric_special = "empirical"
        self._metric_missing = "empirical"
        self.intercept_ = 0.0
        self.scaling_method = None
        self.scaling_method_params = {}
        self.intercept_based = False
        self.reverse_scorecard = False
        self.rounding = False
        self.table = MagicMock(return_value=pd.DataFrame({
            "Variable": ["age"] * 5,
            "Bin id": list(range(5)),
            "Bin": ["(-inf, 30)", "[30, 40)", "[40, inf)", "Special", "Missing"],
            "Points": [580.0, 600.0, 601.0, 0.0, 0.0],
            "WoE": [5.8, 6.0, 6.01, 0.0, 0.0],
            "Coefficient": [100.0] * 5,
        }))
        self.binning_process_ = SimpleNamespace(
            variable_names=["age"],
            binning_transform_params=None,
            get_support=lambda **_kwargs: np.array(["age"]),
            summary=lambda: pd.DataFrame([{
                "name": "age", "dtype": "numerical", "selected": True,
            }]),
            get_binned_variable=lambda _name: SimpleNamespace(
                dtype="numerical", splits=np.array([30, 40]), special_codes=None,
            ),
            transform=MagicMock(side_effect=lambda X, **_kwargs: pd.DataFrame(
                {"age": np.array([5.8, 6.0, 6.01, 0.0, 0.0])[
                    np.where(X["age"].isna(), 4, np.digitize(X["age"].to_numpy(dtype=float), [30, 40]))
                ]}, index=X.index,
            )),
        )
        self.predict_proba = MagicMock(side_effect=lambda frame: [
            [0.8, 0.2] for _ in range(len(frame))
        ])
        self.score = MagicMock(side_effect=lambda frame: (
            np.array([580.0, 600.0, 601.0])[np.digitize(frame["age"], [30, 40])]
            + self.intercept_
        ))


def create_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        threshold: float = 600.0,
) -> tuple[ScoringService, ScorecardStub]:
    """创建评分服务"""
    monkeypatch.setattr(
        "datamind.runtime.serving.scoring_service.Scorecard",
        ScorecardStub,
    )
    monkeypatch.setattr("datamind.models.inspection.Scorecard", ScorecardStub)
    model = ScorecardStub()
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=model,
        metadata={},
    )
    service = ScoringService(
        runtime_model=runtime_model,
        feature_names=["age"],
        threshold=threshold,
    )
    return service, model


def test_predict_uses_scorecard_points(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单条评分从实际命中的评分表条目获取分值"""
    service, model = create_service(monkeypatch)

    result = service.predict({"age": 35})

    assert result["probability"] == pytest.approx(0.2)
    assert result["score"] == pytest.approx(600.0)
    assert result["decision"] == "approve"
    assert result["threshold"] == pytest.approx(600.0)
    assert result["score_intercept"] == 0.0
    assert result["features"] == {
        "age": {"value": 35, "bin": "[30, 40)", "woe": 6.0, "points": 600.0},
    }
    model.score.assert_not_called()


def test_predict_batch_uses_scorecard_points(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试批量评分按特征名称返回明细"""
    service, _ = create_service(monkeypatch)

    result = service.predict_batch([
        {"age": 35},
        {"age": 45},
    ])

    assert result["count"] == 2
    assert result["predictions"] == [
        {
            "probability": 0.2,
            "score": 600.0,
            "decision": "approve",
            "threshold": 600.0,
            "score_intercept": 0.0,
            "features": {
                "age": {"value": 35, "bin": "[30, 40)", "woe": 6.0, "points": 600.0},
            },
        },
        {
            "probability": 0.2,
            "score": 601.0,
            "decision": "approve",
            "threshold": 600.0,
            "score_intercept": 0.0,
            "features": {
                "age": {"value": 45, "bin": "[40, inf)", "woe": 6.01, "points": 601.0},
            },
        },
    ]


def test_predict_reuses_feature_frame(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试概率预测和评分复用同一个特征表"""
    service, model = create_service(monkeypatch)
    extract = MagicMock(wraps=service._extract_features)
    monkeypatch.setattr(service, "_extract_features", extract)

    service.predict({"age": 35})

    probability_frame = (
        model.predict_proba.call_args.args[0]
    )
    score_frame = extract.call_args.args[0]

    assert probability_frame is score_frame


def test_predict_uses_probability_for_default_label(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试根据模型类别顺序提取违约概率"""
    service, model = create_service(monkeypatch)
    model.estimator_.classes_ = np.array([1, 0])
    model.predict_proba.side_effect = None
    model.predict_proba.return_value = [
        [0.2, 0.8]
    ]

    result = service.predict({"age": 35})

    assert result["probability"] == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            [[0.8]],
            "评分卡概率预测结果形状不正确",
        ),
        (
            [[float("nan"), 0.2]],
            "必须是 0 到 1 之间的有限数值",
        ),
        (
            [[-0.1, 1.1]],
            "必须是 0 到 1 之间的有限数值",
        ),
    ],
)
def test_predict_rejects_invalid_probability_output(
        monkeypatch: pytest.MonkeyPatch,
        values: list[list[float]],
        message: str,
) -> None:
    """测试拒绝无效概率预测结果"""
    service, model = create_service(monkeypatch)
    model.predict_proba.side_effect = None
    model.predict_proba.return_value = values

    with pytest.raises(ValueError, match=message):
        service.predict({"age": 35})


def test_score_below_threshold_is_rejected(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试低于评分阈值时拒绝"""
    service, _ = create_service(
        monkeypatch,
        threshold=601.0,
    )

    result = service.predict({"age": 35})

    assert result["decision"] == "reject"


def test_service_exposes_scoring_capabilities(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分服务公开固定能力"""
    service, _ = create_service(monkeypatch)

    assert service.get_capabilities() == (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )


def test_rejects_model_without_score(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝非 Scorecard 模型"""
    monkeypatch.setattr(
        "datamind.runtime.serving.scoring_service.Scorecard",
        ScorecardStub,
    )
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=SimpleNamespace(),
        metadata={},
    )

    with pytest.raises(
            TypeError,
            match=(
                "模型类型不匹配："
                f"期望 {ScorecardStub.__name__}，"
                "实际 SimpleNamespace"
            ),
    ):
        ScoringService(
            runtime_model=runtime_model,
            feature_names=["age"],
        )


def fit_scorecard(
        *,
        intercept_based: bool = False,
        rounding: bool = False,
        reverse_scorecard: bool = False,
        scaling_method: str | None = "pdo_odds",
        transform_params: dict[str, Any] | None = None,
        metric_special: str | float = "empirical",
        metric_missing: str | float = "empirical",
) -> Scorecard:
    """拟合包含数值、类别、特殊值、缺失值和未入模特征的评分卡"""
    records = []
    labels = []
    for category_index, category in enumerate(
            ["salaried", "contract", "unemployed", "withheld", None],
    ):
        for age_index, age in enumerate([20.0, 35.0, 45.0, -999.0, -888.0, np.nan]):
            for repeat in range(12):
                records.append({"employment_type": category, "age": age, "unused": 1})
                labels.append(int(repeat < 2 + (category_index + age_index) % 8))
    process = BinningProcess(
        variable_names=["employment_type", "age", "unused"],
        categorical_variables=["employment_type"],
        fixed_variables=["employment_type", "age"],
        selection_criteria={"iv": {"min": 0.001}},
        binning_fit_params={
            "employment_type": {
                "user_splits": [["salaried"], ["contract", "unemployed"]],
                "user_splits_fixed": [True, True],
                "special_codes": ["withheld"],
                "monotonic_trend": None,
            },
            "age": {
                "user_splits": [30, 40],
                "user_splits_fixed": [True, True],
                "special_codes": {"Unavailable": [-999], "Refused": [-888]},
                "monotonic_trend": None,
            },
        },
        binning_transform_params=transform_params,
        n_jobs=1,
    )
    scaling_params = (
        {"pdo": 40, "odds": 45, "scorecard_points": 650}
        if scaling_method == "pdo_odds" else {"min": 300, "max": 850}
    )
    return Scorecard(
        binning_process=process,
        estimator=LogisticRegression(max_iter=1000),
        scaling_method=scaling_method,
        scaling_method_params=scaling_params if scaling_method is not None else None,
        intercept_based=intercept_based,
        rounding=rounding,
        reverse_scorecard=reverse_scorecard,
    ).fit(pd.DataFrame(records), np.asarray(labels),
          metric_special=metric_special, metric_missing=metric_missing)


@pytest.fixture(scope="module", params=[(False, False), (True, False), (True, True)])
def fitted_scorecard(request: pytest.FixtureRequest) -> Scorecard:
    """创建覆盖评分截距和取整配置的真实评分卡"""
    intercept_based, rounding = request.param
    return fit_scorecard(intercept_based=intercept_based, rounding=rounding)


def create_real_service(model: Scorecard) -> ScoringService:
    """创建使用真实评分卡的运行服务"""
    return ScoringService(runtime_model=RuntimeModel(
        deployment_id="dep_real", model_id="mdl_real", version_id="ver_real",
        framework="sklearn", model=model, metadata={},
    ))


def test_real_scorecard_returns_features(fitted_scorecard: Scorecard) -> None:
    """测试真实评分明细覆盖边界、类别组、缺失和特殊值且可严格序列化"""
    service = create_real_service(fitted_scorecard)
    records = [
        {"age": 30, "employment_type": "salaried", "unused": 1},
        {"age": 40, "employment_type": "contract", "unused": 1},
        {"age": None, "employment_type": "unemployed", "unused": 1},
        {"age": -999, "employment_type": "withheld", "unused": 1},
        {"age": 20, "employment_type": None, "unused": 1},
        {"age": -888, "employment_type": "salaried", "unused": 1},
    ]
    frame = pd.DataFrame(records)
    expected_scores = fitted_scorecard.score(frame)
    expected_points = fitted_scorecard.transform(frame)
    expected_woe = fitted_scorecard.binning_process_.transform(
        frame, metric=None, metric_missing="empirical", metric_special="empirical",
    )
    result = service.predict_batch(records)
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    for index, prediction in enumerate(result["predictions"]):
        assert prediction["score"] == pytest.approx(expected_scores[index])
        assert prediction["score_intercept"] == fitted_scorecard.intercept_
        assert list(prediction["features"]) == [
            "employment_type", "age",
        ]
        for name, item in prediction["features"].items():
            assert set(item) == {"value", "bin", "woe", "points"}
            assert item["value"] == records[index][name]
            assert item["points"] == pytest.approx(expected_points[name].iloc[index])
            assert item["woe"] == pytest.approx(expected_woe[name].iloc[index])
            assert "np.str_" not in item["bin"]
        assert prediction["score"] == pytest.approx(
            sum(item["points"] for item in prediction["features"].values())
            + prediction["score_intercept"],
        )
        single = service.predict(records[index])
        for key, value in prediction.items():
            assert single[key] == value
    predictions = result["predictions"]
    assert predictions[0]["features"]["age"]["bin"] == "[30.00, 40.00)"
    assert predictions[1]["features"]["age"]["bin"] == "[40.00, inf)"
    assert predictions[1]["features"]["employment_type"]["bin"] == "contract, unemployed"
    assert predictions[2]["features"]["age"]["bin"] == "Missing"
    assert predictions[3]["features"]["age"]["bin"] == "Unavailable"
    assert predictions[3]["features"]["employment_type"]["bin"] == "Special"
    assert predictions[4]["features"]["employment_type"]["bin"] == "Missing"
    assert predictions[5]["features"]["age"]["bin"] == "Refused"


@pytest.mark.parametrize("cat_unknown", [None, 0.0, 0.25])
def test_unknown_category_uses_woe_fallback(
        fitted_scorecard: Scorecard, cat_unknown: float | None,
) -> None:
    """测试未知类别按 WoE 回退评分，不读取最后一个分箱"""
    model = deepcopy(fitted_scorecard)
    model.binning_process_.get_binned_variable("employment_type").set_params(cat_unknown=cat_unknown)
    service = create_real_service(model)
    result = service.predict({"age": 35, "employment_type": "freelance", "unused": 1})
    item = result["features"]["employment_type"]
    assert item["bin"] == "Unknown"
    assert item["value"] == "freelance"
    assert item["woe"] == pytest.approx(cat_unknown or 0.0, abs=1e-12)
    table = model.table(style="detailed").query('Variable == "employment_type"')
    factor = 40 / np.log(2)
    offset = 650 - factor * np.log(45)
    coefficient = table["Coefficient"].iloc[0]
    base = (offset - factor * float(model.estimator_.intercept_[0])) / 2
    expected = base - factor * coefficient * item["woe"]
    if model.intercept_based:
        expected -= (base - factor * coefficient * table["WoE"]).min()
    if model.rounding:
        expected = np.rint(expected)
    assert item["points"] == pytest.approx(expected)
    assert result["score"] == pytest.approx(
        sum(item["points"] for item in result["features"].values()) + result["score_intercept"],
    )


@pytest.mark.parametrize("metric", ["indices", "event_rate", "bins"])
def test_rejects_non_woe_transform(
        fitted_scorecard: Scorecard, metric: str,
) -> None:
    """测试非 WoE 转换不会被误报为 WoE 明细"""
    model = deepcopy(fitted_scorecard)
    model.binning_process_.binning_transform_params = {"age": {"metric": metric}}
    with pytest.raises(ValueError, match="必须使用 WoE 转换"):
        create_real_service(model)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_rejects_invalid_score_intercept(
        fitted_scorecard: Scorecard, value: float,
) -> None:
    """测试拒绝非有限评分截距"""
    model = deepcopy(fitted_scorecard)
    model.intercept_ = value
    with pytest.raises(ValueError, match="评分截距必须是有限数值"):
        create_real_service(model)


@pytest.mark.parametrize(
    ("values", "error", "message"),
    [
        (pd.DataFrame({"age": [np.nan]}), ValueError, "WoE 必须是有限数值"),
        (pd.DataFrame({"age": [np.inf]}), ValueError, "WoE 必须是有限数值"),
        (pd.DataFrame({"age": [1, 2]}), RuntimeError, "WoE 转换结果与特征表不匹配"),
        (pd.DataFrame({"other": [1]}), RuntimeError, "WoE 转换结果与特征表不匹配"),
        (pd.DataFrame({"age": [1]}, index=[3]), RuntimeError, "WoE 转换结果与特征表不匹配"),
    ],
)
def test_rejects_invalid_woe(
        monkeypatch: pytest.MonkeyPatch, values: pd.DataFrame,
        error: type[Exception], message: str,
) -> None:
    """测试无效 WoE 不能进入评分明细或关联到错误样本"""
    service, model = create_service(monkeypatch)
    model.binning_process_.transform.side_effect = None
    model.binning_process_.transform.return_value = values
    with pytest.raises(error, match=message):
        service.predict({"age": 35})


@pytest.mark.parametrize(
    ("points", "message"),
    [
        (float("nan"), "分值必须是有限数值"),
        (float("inf"), "分值必须是有限数值"),
        (999.0, "评分表与模型刻度不一致"),
    ],
)
def test_rejects_invalid_scorecard_points(
        monkeypatch: pytest.MonkeyPatch, points: float, message: str,
) -> None:
    """测试加载时拒绝无效或与模型刻度不一致的评分表"""
    service, model = create_service(monkeypatch)
    model.table.return_value.loc[1, "Points"] = points
    with pytest.raises(ValueError, match=message):
        service._prepare_scorecard()


def test_empty_batch_does_not_run_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试空批次不调用模型预测和分箱转换"""
    service, model = create_service(monkeypatch)
    result = service.predict_batch([])
    assert result["predictions"] == []
    assert result["count"] == 0
    model.predict_proba.assert_not_called()
    model.score.assert_not_called()
    model.binning_process_.transform.assert_not_called()


@pytest.mark.parametrize("metric", [None, "woe"])
def test_woe_configuration_does_not_override_bin_matching(metric: str | None) -> None:
    """测试显式 WoE 配置不影响分箱命中且不改写原模型"""
    params = {
        name: {"metric": metric, "metric_missing": "empirical", "metric_special": "empirical"}
        for name in ("employment_type", "age", "unused")
    }
    model = fit_scorecard(transform_params=params)
    before_params = deepcopy(model.binning_process_.binning_transform_params)
    before_coefficients = model.estimator_.coef_.copy()
    service = create_real_service(model)
    records = [
        {"age": 35, "employment_type": "salaried", "unused": 1},
        {"age": 45, "employment_type": "contract", "unused": 1},
        {"age": None, "employment_type": "freelance", "unused": 1},
    ]
    frame = pd.DataFrame(records)
    original_probabilities = model.predict_proba(frame)[:, 1]
    result = service.predict_batch(records)
    for row, probability in zip(result["predictions"], original_probabilities):
        assert row["probability"] == pytest.approx(probability)
        factor = 40 / np.log(2)
        expected = 650 - factor * np.log(45) - factor * np.log(probability / (1 - probability))
        assert row["score"] == pytest.approx(expected)
    assert result["predictions"][0]["features"]["age"]["bin"] == "[30.00, 40.00)"
    assert result["predictions"][1]["features"]["age"]["bin"] == "[40.00, inf)"
    assert result["predictions"][2]["features"]["employment_type"]["bin"] == "Unknown"
    assert model.binning_process_.binning_transform_params == before_params
    np.testing.assert_array_equal(model.estimator_.coef_, before_coefficients)


@pytest.mark.parametrize("overrides", [False, True])
@pytest.mark.parametrize("metric_special,metric_missing", [(0.0, 0.0), (-0.4, 0.3)])
def test_custom_missing_and_special_woe(
        overrides: bool,
        metric_special: float,
        metric_missing: float,
) -> None:
    """测试全局及变量级缺失值、特殊值 WoE 与概率预测保持一致"""
    params = {
        "age": {"metric": "woe", "metric_missing": 0.25, "metric_special": -0.5},
    } if overrides else None
    model = fit_scorecard(
        transform_params=params,
        metric_missing=metric_missing,
        metric_special=metric_special,
    )
    records = [
        {"age": None, "employment_type": None, "unused": 1},
        {"age": -999, "employment_type": "withheld", "unused": 1},
    ]
    result = create_real_service(model).predict_batch(records)
    assert result["predictions"][0]["features"]["age"]["woe"] == (
        0.25 if overrides else metric_missing
    )
    assert result["predictions"][1]["features"]["age"]["woe"] == (
        -0.5 if overrides else metric_special
    )
    for row in result["predictions"]:
        probability = row["probability"]
        factor = 40 / np.log(2)
        assert row["score"] == pytest.approx(
            650 - factor * np.log(45) - factor * np.log(probability / (1 - probability)),
        )


def test_partial_variable_transform_params_override_global_metrics() -> None:
    """测试变量级缺失和特殊值配置在未显式设置 metric 时仍覆盖全局配置"""
    model = fit_scorecard(
        transform_params={
            "age": {
                "metric_missing": "empirical",
            },
        },
        metric_missing=0.0,
        metric_special=0.0,
    )
    records = [{"age": None, "employment_type": "salaried", "unused": 1}]
    frame = pd.DataFrame(records)

    result = create_real_service(model).predict_batch(records)
    expected_woe = model.binning_process_.transform(
        frame,
        metric=None,
        metric_missing=0.0,
        metric_special=0.0,
    )

    for index, row in enumerate(result["predictions"]):
        assert row["features"]["age"]["woe"] == pytest.approx(
            expected_woe["age"].iloc[index]
        )
        probability = row["probability"]
        factor = 40 / np.log(2)
        assert row["score"] == pytest.approx(
            650 - factor * np.log(45) - factor * np.log(probability / (1 - probability))
        )


@pytest.mark.parametrize("method,intercept_based,rounding,reverse", [
    (method, intercept_based, rounding, reverse)
    for method in (None, "pdo_odds", "min_max")
    for intercept_based, rounding, reverse in (
        (False, False, False), (True, False, True), (False, True, True), (True, True, False),
    )
    if method is not None or not rounding
])
def test_scaling_preserves_fitted_bin_points(
        method: str | None, intercept_based: bool, rounding: bool, reverse: bool,
) -> None:
    """测试各种刻度、方向、评分截距及取整配置沿用已拟合分箱的分值"""
    model = fit_scorecard(
        scaling_method=method, intercept_based=intercept_based,
        rounding=rounding, reverse_scorecard=reverse,
    )
    records = [
        {"age": 20, "employment_type": "salaried", "unused": 1},
        {"age": 40, "employment_type": "contract", "unused": 1},
        {"age": None, "employment_type": None, "unused": 1},
        {"age": -888, "employment_type": "withheld", "unused": 1},
    ]
    frame = pd.DataFrame(records)
    expected_points = model.transform(frame)
    expected_scores = model.score(frame)
    result = create_real_service(model).predict_batch(records)
    for index, row in enumerate(result["predictions"]):
        assert row["score"] == pytest.approx(expected_scores[index])
        for name, item in row["features"].items():
            assert item["points"] == pytest.approx(expected_points[name].iloc[index])


def test_min_max_rounding_rejects_undefined_fallback() -> None:
    """测试联合整数刻度不会为训练时不存在的分箱猜测分值"""
    model = fit_scorecard(scaling_method="min_max", rounding=True)
    service = create_real_service(model)
    with pytest.raises(ValueError, match="min_max 整数评分卡无法确定回退分值"):
        service.predict({"age": 35, "employment_type": "freelance", "unused": 1})


@pytest.mark.parametrize("value,expected", [
    (np.int64(35), 35), (np.float64(35.0), 35.0), (None, None), (float("nan"), None),
])
def test_feature_values_are_json_scalars(
        monkeypatch: pytest.MonkeyPatch, value: Any, expected: int | float | None,
) -> None:
    """测试原始标量类型得到保留，缺失值可严格序列化为 null"""
    service, _ = create_service(monkeypatch)
    result = service.predict({"age": value})
    actual = result["features"]["age"]["value"]
    assert actual == expected
    assert type(actual) is type(expected)
    assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.parametrize("value", [float("inf"), -float("inf"), [35]])
def test_rejects_non_json_feature_values(value: Any) -> None:
    """测试不会将无穷值或非标量输入伪装为有效特征值"""
    with pytest.raises(ValueError):
        ScoringService._convert_feature_value(value)
