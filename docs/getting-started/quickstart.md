# 快速上手

使用评分卡示例模型完成一次服务发布：训练制品、注册版本、启用部署，然后发起预测。开始前请完成[安装](installation.md)和[配置与初始化](configuration.md)，并克隆源码仓库以运行训练脚本。

## 1. 训练并注册模型

在仓库根目录安装 sklearn extra，运行训练脚本：

```bash
python -m pip install -e ".[sklearn]"
python examples/scorecard/train.py \
  --output examples/scorecard/artifacts/scorecard_demo.pkl
```

训练脚本生成 `examples/scorecard/artifacts/scorecard_demo.pkl`。

完成 `datamind login --username admin` 后，注册并激活版本：

```bash
datamind model register scorecard-demo \
  --display-name "评分卡示例模型" \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring

datamind model activate scorecard-demo --version 1.0.0
```

## 2. 启用部署

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout full
```

复制输出中的部署（`Deployment`） ID，在后续命令中替换 `<deployment_id>`：

```bash
datamind deployment enable <deployment_id>
```

注册、激活和启用部署是不同步骤，职责见[部署与预测服务（`Runtime`）](../deployment/index.md)。

## 3. 配置路由

```bash
datamind route create <deployment_id> \
  --name scorecard-demo-main \
  --traffic-ratio 1 \
  --enabled
```

路由（`Routing`）创建默认不启用。本例显式使用 `--enabled`，让该路由分配全部主流量。

## 4. 启动服务

在一个终端启动预测服务：

```bash
datamind service run
```

在另一个终端、同一配置目录中启动 Console：

```bash
datamind console run
```

预测服务默认端口为 8700，Console 默认端口为 8701。打开 `http://127.0.0.1:8701` 登录管理控制台，核对部署、路由和运行状态。逐屏操作见[Console 手册](../guides/console.md)。

本例在线预测无需 Redis Worker。使用批量或影子执行时需另外启动[任务 Worker](../deployment/processes.md)。

## 5. 获取 HTTP 访问令牌

CLI 登录不会自动向 HTTP 客户端提供令牌。以初始化时的管理员凭据调用预测服务：

```bash
curl -sS http://127.0.0.1:8700/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<初始化时设置的密码>"}'
```

复制响应中的 `access_token`，替换下一步的 `<access_token>`。

## 6. 完成第一次预测

```bash
curl -sS http://127.0.0.1:8700/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "request": {
      "model_name": "scorecard-demo",
      "subject_key": "borrower-001",
      "subject_type": "borrower",
      "features": {
        "age": 35,
        "annual_income": 120000,
        "debt_to_income_ratio": 0.3,
        "credit_utilization_ratio": 0.4,
        "delinquency_count": 0,
        "credit_history_years": 8,
        "employment_type": "salaried",
        "residence_status": "mortgage"
      }
    }
  }'
```

`features` 必须与训练脚本的输入特征一致。本例使用年龄、年收入、负债收入比、信用额度使用率、历史逾期次数、信用历史年数、就业类型和居住状态八个特征，数据为合成信贷数据。

成功响应包含 `success`=true 和 `request_id`，同时返回 `probability`、`score`、`decision`、`threshold` 及逐特征的分箱、WoE 和分值。具体数值取决于制品和输入，`decision` 表达评分阈值判断，实际审批由业务系统处理。

在 Console 的“API 调用”与“执行记录”中按 `request_id` 查找这次预测，确认命中的部署和版本。

## 下一步

在 [Console](../guides/console.md) 中查看模型与调用记录，使用[批量预测](../guides/batch-prediction.md)处理多条输入，或通过[A/B 测试](../experiments/index.md)比较新旧版本。需要逐步接入候选版本时，继续阅读[金丝雀发布](../deployment/canary.md)。
