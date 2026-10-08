# 快速上手

本教程以评分卡模型为例，介绍从模型训练、注册和部署到在线预测的完整流程。完成后，你将能够通过 HTTP 接口调用模型，并在管理控制台中查看预测记录。

## 开始前

请确认已完成以下准备：

- 按照[安装](installation.md)准备 Python 环境，并克隆源码仓库以运行示例训练脚本。使用源码运行管理控制台时，还需完成前端资源构建。
- 完成[配置与初始化](configuration.md)，创建管理员账号并登录 CLI。
- 在执行命令的各个终端中使用同一 Python 环境，并进入项目根目录，以读取相同的配置。

本教程使用默认服务端口。若已修改端口，请相应调整请求地址。`<deployment_id>` 和 `<access_token>` 等尖括号标记的内容为占位符，执行命令前请替换为实际值。

## 步骤 1：训练并注册模型

安装 scikit-learn 和评分卡所需依赖：

```bash
python -m pip install -e ".[sklearn]"
```

运行训练脚本：

```bash
python examples/scorecard/train.py \
  --output examples/scorecard/artifacts/scorecard_demo.pkl
```

脚本使用合成信贷数据训练评分卡，并将模型保存到 `examples/scorecard/artifacts/scorecard_demo.pkl`。

将模型注册为 `scorecard-demo` 的 `1.0.0` 版本：

```bash
datamind model register scorecard-demo \
  --display-name "评分卡示例模型" \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

注册完成后，激活该版本：

```bash
datamind model activate scorecard-demo --version 1.0.0
```

## 步骤 2：创建并启用部署

为已激活的版本创建全量部署：

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout full
```

复制命令输出中的部署 ID，替换 `<deployment_id>`，然后启用部署：

```bash
datamind deployment enable <deployment_id>
```

启用部署后，预测服务会在启动时加载模型。部署配置与实际加载状态的区别，请参阅[部署与运行](../deployment/index.md)。

## 步骤 3：配置路由

为该部署创建并启用路由：

```bash
datamind route create <deployment_id> \
  --name scorecard-demo-main \
  --traffic-ratio 1 \
  --enabled
```

本例将流量比例设为 `1`，让该部署接收全部主预测流量。`--enabled` 用于立即启用路由；省略时，路由创建后保持停用状态。

## 步骤 4：启动服务

启动预测服务：

```bash
datamind service run --host 127.0.0.1 --port 8700
```

在另外一个终端启动管理控制台：

```bash
datamind console run --host 127.0.0.1 --port 8701
```

启动完成后，在浏览器中访问 `http://localhost:8701`，使用初始化时创建的管理员账号和密码登录。更多操作请参阅[管理控制台](../guides/console.md)。

以上两个命令均通过 `--host` 指定监听地址、`--port` 指定监听端口。本教程使用本机地址；如需从其他机器访问，将 `--host` 改为 `0.0.0.0`，并通过服务器 IP 访问。更改端口时，请同步调整后续请求和浏览器中的访问地址。

## 步骤 5：获取访问令牌

使用管理员账号和密码获取访问令牌。默认用户名和密码均为 `admin`；如已修改，请使用实际账号和密码：

```bash
curl -sS http://localhost:8700/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin"
  }'
```

## 步骤 6：发起在线预测

调用 `/predict` 接口发起预测请求，将 `<access_token>` 替换为获取的访问令牌：

```bash
curl -sS http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "request": {
      "model_name": "scorecard-demo",
      "subject_key": "borrower-001",
      "subject_type": "borrower",
      "features": {
        "age": 45,
        "annual_income": 240000,
        "debt_to_income_ratio": 0.1,
        "credit_utilization_ratio": 0.1,
        "delinquency_count": 0,
        "credit_history_years": 20,
        "employment_type": "salaried",
        "residence_status": "owner"
      }
    }
  }'
```

请求成功后，接口返回响应：

```jsonc
{
  "success": true,
  "task_type": "scoring",
  "score": 680.1729095023757,
  "probability": 0.013002585872582427,
  "decision": "approve",
  "threshold": 600.0,
  "score_intercept": 0.0,
  "features": {
    "age": {
      "value": 45,
      "bin": "[40.00, 50.00)",
      "woe": 0.04071375518752225,
      "points": 66.28438957991956
    }
    // ... 为简洁起见，省略部分字段
  },
  "request_id": "req_374596385a614b3b"
}
```

本次评分约为 680.17，违约概率约为 1.30%。评分高于阈值 600，因此决策结果为 `approve`。实际结果取决于模型和输入，响应字段说明见[预测 API](../reference/runtime-api.md)。

## 检查结果

完成以上步骤后，请确认：

- 已启用的部署至少有一个状态为 `running` 的运行实例。
- 预测接口返回 HTTP 200，响应中的 `success` 为 `true`，且 `request_id` 非空。
- 响应任务类型为 `scoring`，并包含评分结果。
- 在管理控制台中，可通过 `request_id` 查询本次请求及其主执行记录。

## 常见问题

- **部署已启用，但模型未加载**：确认预测服务已启动，且与部署使用相同的环境配置。若运行实例状态为 `failed`，查看错误信息和服务日志，检查模型文件是否可访问、所需依赖是否已安装。
- **没有可用部署**：确认部署已启用，且与预测服务使用相同的环境配置，并检查部署是否处于生效时间内。
- **请求返回 401 或 403**：检查访问令牌是否有效，并确认账号具有 `prediction.invoke` 权限。

运行问题的排查步骤，请参阅[常见故障排查](../deployment/production.md#troubleshooting)。

