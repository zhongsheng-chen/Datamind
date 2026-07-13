# 信用评分模型示例

本示例使用可复现的合成数据训练二分类逻辑回归模型，用于演示模型注册和评分配置。

## 目录内容

- `train.py`：训练并保存示例模型。
- `input_schema.json`：模型输入 Schema。
- `scoring_config.json`：评分参数配置。
- `route_rules.json`：路由规则示例。
- `artifacts/`：训练生成的模型制品，不纳入版本管理。

## 训练模型

```bash
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

## 注册模型

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --input-schema-file examples/scorecard/input_schema.json \
  --description "信用评分模型" \
  --version-description "信用评分模型 v1.0.0"
```

训练与注册相互独立：训练脚本只生成本地制品，模型注册由 CLI 显式执行。
