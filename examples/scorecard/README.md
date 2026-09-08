# 信用评分模型示例

本示例使用可复现的合成信贷数据训练评分卡模型，用于演示真实的
WOE 分箱、逻辑回归、模型验证、评分转换和模型注册。

最终制品是一个 OptBinning 原生 `Scorecard`：

```text
原始数值/类别特征
  → OptBinning BinningProcess（最优分箱和 WOE 转换）
  → OptBinning Scorecard（内含 LogisticRegression、概率和分值）
  → joblib scorecard.pkl
```

训练数据同时包含申请日期、数值变量、类别变量、缺失值和特殊值。1 表示
违约，0 表示正常；申请日期不作为模型特征，而是用于跨时间切分。
最早 75% 样本用于训练，最新 25% 样本用于验证，分箱只在训练集
拟合，避免随机切分和数据泄漏导致效果虚高。

## 目录内容

- `train.py`：生成演示数据、训练、验证并保存原生 Scorecard。
- `scoring_config.json`：评分参数配置。
- `route_rules.json`：路由规则示例。
- `artifacts/`：训练生成的模型制品，不纳入版本管理。

## 训练模型

```bash
pip install -e ".[sklearn]"
python examples/scorecard/train.py
```

默认生成：

```text
examples/scorecard/artifacts/scorecard.pkl
```

也可以指定输出路径：

```bash
python examples/scorecard/train.py --output ./scorecard.pkl
```

还可以调整样本数量和随机种子：

```bash
python examples/scorecard/train.py \
  --sample-size 10000 \
  --random-seed 42 \
  --train-size 0.75 \
  --test-size 0.25 \
  --n-jobs -1
```

训练完成后会输出：

- 留出集坏样本率、AUC、Gini 和 KS；
- 示例客户的违约概率和信用分；
- 每个变量的类型、求解状态、箱数、IV 和质量分；
- 已回读验证的 `scorecard.pkl` 文件路径。

模型将 `annual_income` 和 `credit_history_years` 的缺失值作为独立
信息处理；`employment_type` 和 `residence_status` 使用类别分箱。
`credit_utilization_ratio` 包含两种互斥的特殊状态，通过变量级
`special_codes` 分别分箱：

- `-999`：无信用卡账户，分箱名称为 `No credit card`，生成概率为 12%。
- `-888`：有信用卡账户但总授信额度为零，分箱名称为 `Zero credit limit`，
  在有信用卡账户的样本中以 5% 的概率生成。

两种状态下利用率均无法按正常比例计算，不等于正常利用率 `0`，
也不是缺失值；其他贷款相关指标仍可有值。
生成标签时不将特殊编码代入数值计算，而是分别设置对应状态的风险项。
发生比例和风险系数仅用于合成数据演示，不代表实际业务结论。
部署后可分别传入 `"credit_utilization_ratio": -999` 和
`"credit_utilization_ratio": -888` 验证各自的特殊值分箱与特征分。
线上加载该 `.pkl` 时必须安装与训练环境兼容的 `optbinning` 和
`scikit-learn`。

训练使用 WoE 转换，缺失值和特殊值采用经验 WoE。未知类别使用默认
配置 `cat_unknown=None`，在 WoE 转换时取值为 0。
用于评分明细的命中分箱编号不是逻辑回归的训练输入，不应为获取分箱编号
将训练指标改为 `metric="indices"`。

## 注册模型

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --description "信用评分模型" \
  --version-description "信用评分模型 v1.0.0"
```

训练与注册相互独立：训练脚本只生成本地制品，模型注册由 CLI 显式执行。

## 评分响应

单条评分及批量评分中的每条 `predictions` 均包含：

- `success`、`request_id`：处理状态和本条请求的追踪标识。
- `probability`、`score`、`decision`、`threshold`：概率、信用分、决策和阈值。
- `score_intercept`：评分截距，来自制品的 `Scorecard.intercept_`，
  不是逻辑回归截距，也不是 PDO 参数中的基准分。
- `features`：以入模特征名称为键的明细字典，不包含未入模特征。
  每项包含原始特征值 `value`、可读分箱标签 `bin`、
  概率预测实际使用的 `woe` 和特征分值 `points`。

示例明细结构：

```json
{
  "features": {
    "employment_type": {
      "value": "salaried",
      "bin": "salaried",
      "woe": 0.1890232960921429,
      "points": 74.93396000778203
    }
  }
}
```

总分满足 `score = score_intercept + sum(item["points"] for item in features.values())`。
WoE 和分值保留原始精度，不为展示提前四舍五入。特征值中的 NumPy 标量
转为 JSON 标量，缺失值统一返回 `null`。缺失值和特殊值使用实际命中
分箱；未知类别返回 `bin: "Unknown"`，按模型的实际回退 WoE 和已有
评分刻度计算分值，不将未知类别误报为命中普通分箱或缺失分箱。

已有分箱直接采用制品评分表中的分值，包括训练时的取整结果。
`min_max` 整数评分卡可能采用联合整数优化；如果实际 WoE 没有对应的
评分表条目（例如未知类别），服务会明确报错，不猜测分值或套用缺失箱。

明细直接来自运行时制品，不依赖数据库中用于版本详情展示的评分卡数据。
新增字段会随响应及执行记录保存，不补写已有请求历史。

对外响应只包含业务结果和 `request_id`，不返回模型、版本、部署、决策、
实验分配或 Worker 等内部 ID，也不返回 `route`、`framework`、
`service_type` 和 `environment`。这些信息仍保存在内部决策、执行记录及日志中，
可从控制台按请求关联查看。延迟业务结果可以使用 `request_id` 回流，
服务端会自动补齐决策和实验关联信息。

批量接口返回 `success`、`count`、`predictions` 和批次级 `request_id`。
每项 `predictions` 都包含自身的 `request_id`，不再使用顶层的
`request_ids`、`decision_ids` 并列数组。回传某条业务结果时应使用该项的
`request_id`，而不是批次 ID。

更新评分运行服务代码后需重启模型服务（`datamind service run`），
而不只是重启控制台。服务更新不会自动改写已注册模型或现有部署。

## 复现分箱索引冲突

OptBinning 0.21.0 中，变量级 `metric="woe"` 可以覆盖原生 `score()`
请求的分箱索引转换，导致 WoE 被写入整数索引数组后查错分箱。
运行独立的最小复现脚本：

```bash
python -X utf8 examples/scorecard/reproduce_metric_conflict.py
```

脚本仅依赖 OptBinning 及其训练依赖，在内存中创建单变量评分卡，
不调用 Datamind 服务，不读写 `.pkl` 或数据库；输出以当前依赖版本为准。

评分服务根据已拟合规则独立定位分箱，保留原模型的 WoE 配置及概率预测，
不再调用存在上述冲突的 `Scorecard.score()`。因此受该问题影响的模型，
修复后的总分和决策可能与旧服务不同，需要在正式切换前核对样本结果。
