# Datamind

**开放式模型服务管理平台，连接模型交付与生产服务，让模型注册、版本管理、
部署上线、API 调用、实验评估与审计追踪更加简单可靠。**

[快速开始](#快速开始) ·
[模型支持](#模型支持) ·
[Docker](#docker) ·
[CLI 文档](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/README.md) ·
[示例](https://github.com/zhongsheng-chen/Datamind/tree/main/examples)

Datamind 管理模型从制品到在线服务的交付链路：

```text
模型制品 → 注册与版本 → 部署与路由 → 在线推理 → 实验与审计
```

> PyPI 发行包名为 `pydatamind`，Python 导入名和命令行入口均为
> `datamind`。

## 为什么使用 Datamind

- **统一模型交付**：集中管理模型、版本、制品和部署状态。
- **渐进式上线**：支持全量、金丝雀和影子发布，并通过路由控制流量。
- **一致的推理服务**：为分类模型和信用评分卡提供统一 Runtime Service。
- **在线与批量任务**：同时支持实时调用、批量预测、取消、重试和结果回流。
- **实验评估**：管理 A/B 实验、实验分组、流量分配和效果分析。
- **生产治理**：提供权限控制、操作审计、健康检查和运行状态管理。
- **开放存储与框架**：支持本地文件系统、MinIO 及主流树模型框架。

Datamind 输出模型预测结果，不承担授信审批、额度策略或其他业务决策。

## 快速开始

Datamind 支持 Python 3.12、3.13 和 3.14，并使用 PostgreSQL 保存平台数据。

### 安装

按模型框架安装对应的 extra。以下示例安装 scikit-learn 与评分卡支持：

```bash
python -m pip install "pydatamind[sklearn]"
```

安装全部框架：

```bash
python -m pip install "pydatamind[full]"
```

确认 CLI 可用：

```bash
datamind --version
datamind --help
```

### 配置与初始化

在工作目录创建 `.env`：

```dotenv
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/datamind

DATAMIND_STORAGE_TYPE=local
DATAMIND_STORAGE_LOCAL_BASE_DIR=./data

DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=<long-random-secret>
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=<strong-password>
```

创建数据库结构并初始化系统：

```bash
alembic upgrade head
datamind init
datamind login --username admin
```

初始化完成后，应从运行环境中移除 `DATAMIND_INIT_ADMIN_PASSWORD`。
所有配置项见
[环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example)。

### 交付模型

注册已经训练好的 scikit-learn 分类模型：

```bash
datamind model register credit-model \
  --version 1.0.0 \
  --model-path ./models/model.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type classification \
  --display-name "Credit Model"
```

激活模型版本：

```bash
datamind model activate credit-model --version 1.0.0
```

创建并启用全量部署：

```bash
datamind deployment create credit-model \
  --version 1.0.0 \
  --rollout full

datamind deployment enable <deployment_id>
```

将全部流量路由到该部署：

```bash
datamind route create <deployment_id> \
  --name credit-model-route \
  --traffic-ratio 1.0 \
  --enabled
```

没有现成模型时，可以运行仓库中的可复现训练示例：

```bash
python examples/classification/logistic_regression/train.py
```

更多模型见
[examples](https://github.com/zhongsheng-chen/Datamind/tree/main/examples)。

### 启动服务

启动 Runtime Service：

```bash
datamind service run
```

Runtime 默认监听 `http://127.0.0.1:8700`。

启动管理控制台：

```bash
datamind console run
```

管理控制台默认监听 `http://127.0.0.1:8701`。

完整命令和参数见
[CLI 文档](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/README.md)。

## 模型支持

选择与模型框架对应的 Python extra：

| Extra | Framework | Model Type |
| --- | --- | --- |
| `sklearn` | scikit-learn | `logistic_regression`、`decision_tree`、`random_forest` |
| `xgboost` | XGBoost | `xgboost` |
| `lightgbm` | LightGBM | `lightgbm` |
| `catboost` | CatBoost | `catboost` |
| `full` | 全部框架 | 全部模型类型 |

Datamind 支持以下任务：

- `classification`：返回分类结果和概率。
- `scoring`：返回信用评分、违约概率、特征分和截距分。

评分任务目前支持基于 scikit-learn 的逻辑回归评分卡；其他模型类型用于分类任务。

## Docker

正式镜像发布至 Docker Hub：

```text
docker.io/zhongshengchen/datamind:<version>
```

纯版本标签包含全部模型框架。单框架镜像使用 `-sklearn`、`-xgboost`、
`-lightgbm` 或 `-catboost` 后缀。

Docker Compose 启动 Runtime、管理控制台、批量任务 Worker 和影子任务
Worker。PostgreSQL、Redis 和 MinIO 由外部基础设施提供。

```bash
cd docker
cp .env.example .env.docker
export DATAMIND_IMAGE_TAG=<version>

docker compose --profile tools run --rm migrate
docker compose --profile tools run --rm init
docker compose up -d
```

容器访问宿主机服务时应使用 `host.docker.internal`。完整配置见
[Docker 环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.example)
和
[Docker Compose](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.yml)。

## 工作方式

Datamind 将控制面与运行面分开：

- **CLI / Console** 管理模型、部署、路由、实验、用户和角色。
- **Services** 处理资源生命周期与业务约束。
- **Runtime** 负责路由、模型装载、预测执行和任务协调。
- **Storage** 保存本地或 MinIO 模型制品。
- **Database** 使用 SQLAlchemy、Alembic 和 PostgreSQL 持久化平台状态。
- **Auth / Audit** 提供身份认证、权限控制和操作追踪。

核心资源按以下关系组织：

```text
Model
  └─ Version
      └─ Artifact
          └─ Deployment
              └─ Routing
                  └─ Runtime
```

## 开发

安装开发依赖：

```bash
python -m pip install -e ".[test,full,release]"
npm ci
```

运行快速测试：

```bash
pytest tests/unit tests/services tests/cli tests/console
npm run test:frontend
```

集成测试和端到端测试需要真实基础设施：

```bash
pytest -m integration
pytest tests/e2e
```

详细说明见：

- [CLI 文档](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/README.md)
- [测试指南](https://github.com/zhongsheng-chen/Datamind/blob/main/tests/README.md)
- [发布指南](https://github.com/zhongsheng-chen/Datamind/blob/main/RELEASING.md)

## License

Datamind 使用
[Apache License 2.0](https://github.com/zhongsheng-chen/Datamind/blob/main/LICENSE)。
