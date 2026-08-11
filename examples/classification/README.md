# 风险分类模型示例

本示例使用可复现的合成数据训练随机森林二分类模型。正类标签 `1` 表示高风险交易，运行时服务根据正类概率和分类阈值返回预测结果。

## 目录内容

- `train.py`：训练并保存示例模型。
- `input_schema.json`：模型输入 Schema。
- `deployment_config.json`：分类阈值配置。
- `predict_request.json`：单条预测请求示例。
- `artifacts/`：训练生成的模型制品，不纳入版本管理。

## 训练模型

```bash
python examples/classification/train.py
```

默认生成：

```text
examples/classification/artifacts/fraud.pkl
```

## 注册模型

```bash
datamind model register fraud \
  --version 1.0.0 \
  --model-path examples/classification/artifacts/fraud.pkl \
  --framework sklearn \
  --model-type random_forest \
  --task-type classification \
  --input-schema-file examples/classification/input_schema.json \
  --description "风险分类模型" \
  --version-description "风险分类模型 v1.0.0"
```

## 创建部署

激活模型及版本：

```bash
datamind model activate fraud --version 1.0.0
```

创建部署并配置分类阈值：

```bash
datamind deployment create fraud \
  --version 1.0.0 \
  --environment development \
  --config-file examples/classification/deployment_config.json
```

部署创建后，使用返回的 `deployment_id` 启用部署并提交模型加载请求：

```bash
datamind deployment enable <deployment_id>
datamind service load <deployment_id>
```

## 预测请求

`predict_request.json` 展示 `/predict` 接口的请求结构。调用前需将 `model_name` 替换为已注册模型的名称。
