# Datamind

Datamind 是一个面向银行信贷等场景的模型交付与在线推理平台，用于把 Python 训练得到的模型从“模型文件”推进到可管理、可部署、可调用、可审计的生产服务。

平台负责模型注册、版本管理、部署、路由、在线推理、批量预测、实验、运行状态和审计；**不承担授信审批或业务决策本身**。评分任务输出模型分数、违约概率和特征分，最终业务决策由下游系统完成。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 模型管理 | 模型注册、版本管理、制品修订、激活、停用、弃用、删除与恢复 |
| 模型部署 | 创建部署，支持全量、金丝雀和影子发布 |
| 流量路由 | 按部署配置流量比例、规则和生效时间 |
| 在线推理 | 基于 BentoML 提供统一 Runtime Service |
| 批量预测 | 基于 Celery + Redis 执行异步批量预测和分片重试 |
| 评分任务 | 返回总分、违约概率、特征分和截距分，不直接输出授信决策 |
| 分类任务 | 返回分类预测和概率结果 |
| A/B 实验 | 实验、分组、流量分配、结果回流和效果分析 |
| 管理控制台 | 浏览器管理模型、部署、路由、实验、用户、角色和运行状态 |
| 权限与审计 | 本地用户、角色权限、JWT 会话、操作审计和结构化日志 |
| 模型存储 | 支持本地文件系统和 MinIO |
| 运行治理 | 模型装载、卸载、重载、Worker 状态和健康检查 |

## 支持范围

### 任务类型

Datamind 当前支持两类任务：

| 任务 | 说明 |
| --- | --- |
| `classification` | 通用分类模型预测 |
| `scoring` | 信用评分卡模型评分 |

评分任务目前仅支持逻辑回归评分卡：

```text
framework   = sklearn
model_type  = logistic_regression
task_type   = scoring
```

评分卡模型以真实模型对象作为部署制品，当前 E2E 使用 `optbinning.Scorecard` 验证完整评分链路。

### 模型框架与类型

| Framework | Model Type |
| --- | --- |
| `sklearn` | `logistic_regression` / `decision_tree` / `random_forest` |
| `xgboost` | `xgboost` |
| `lightgbm` | `lightgbm` |
| `catboost` | `catboost` |

> [!NOTE]
> `logistic_regression` 既可以用于分类任务，也可以用于评分任务；其他模型类型只支持分类任务。

## 核心对象

Datamind 的主要资源关系如下：

```text
Model
  └─ Version
      └─ Artifact
          └─ Deployment
              └─ Routing
                  └─ Runtime
```

实验体系独立管理实验与分组，并在运行时参与流量分配；每次预测会形成 Request、Decision、Execution 和 Audit 等可追踪记录。

## 快速开始

### 环境要求

开发环境建议：

- Python 3.12–3.14
- PostgreSQL
- Node.js 24（构建管理控制台时需要）
- Redis（批量预测和异步任务需要）
- MinIO（使用对象存储时需要）

### 安装

安装完整模型运行依赖：

```bash
pip install -e ".[full]"
```

确认 CLI：

```bash
datamind --version
datamind --help
```

如需运行管理控制台，先构建前端资源：

```bash
npm ci
npm run build:console
```

### 配置

复制环境变量模板。

Linux：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

开发环境至少确认：

```dotenv
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/datamind
```

默认使用本地模型存储：

```dotenv
DATAMIND_STORAGE_TYPE=local
DATAMIND_STORAGE_LOCAL_BASE_DIR=./data
```

如果启用认证，还需要配置：

```dotenv
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=<long-random-secret>
```

预发布和生产环境启用本地认证时，还应配置允许访问的服务器地址或内网网段。

### 初始化数据库

执行数据库迁移：

```bash
alembic upgrade head
```

首次启用认证前，设置初始管理员：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=<strong-password>
```

执行一次性初始化：

```bash
datamind init
```

初始化完成后，应从运行环境中移除初始管理员密码。

### 登录

认证开启时：

```bash
datamind login --username admin
datamind whoami
```

CLI 会保存本地会话并自动处理访问令牌续期。开发或测试环境关闭认证时，CLI 使用本地 `system` 身份执行允许的操作。

## 从模型到在线服务

下面展示一条最小模型上线流程。

### 注册评分卡

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --display-name "信用评分卡"
```

注册完成后，Datamind 会生成并维护 `model_id`、`version_id`、`artifact_id` 等内部标识。调用方不需要自行生成模型 ID。

### 激活版本

```bash
datamind model activate scorecard --version 1.0.0
```

### 创建部署

全量发布：

```bash
datamind deployment create scorecard \
  --version 1.0.0 \
  --rollout full \
  --threshold 600
```

支持的发布方式：

| 发布方式 | 说明 |
| --- | --- |
| `full` | 全量发布，部署角色自动为 `champion` |
| `canary` | 金丝雀发布，需要指定 `champion` 或 `challenger` |
| `shadow` | 影子发布，部署角色自动为 `shadow` |

### 启用部署并创建路由

```bash
datamind deployment enable <deployment_id>

datamind route create <deployment_id> \
  --name scorecard-route \
  --traffic-ratio 1.0 \
  --enabled
```

### 启动 Runtime

```bash
datamind service run
```

默认 Runtime Service 地址：

```text
http://127.0.0.1:8700
```

Runtime 支持单笔预测、批量预测、批次状态查询、取消与重试、业务结果回流，以及模型装载、卸载、重载和运行状态查询。

## 管理控制台

启动管理控制台：

```bash
datamind console run
```

默认访问地址：

```text
http://127.0.0.1:8701
```

控制台用于管理：

- 模型与版本
- 部署与路由
- A/B 实验与实验分组
- 用户与角色
- Runtime 状态
- 审计与运行信息

界面中的写操作会经过权限校验，并记录审计信息。

## Docker 部署

生产或集成环境推荐使用 Docker Compose。

当前 Compose 负责运行：

| Service | 作用 | 默认端口 |
| --- | --- | ---: |
| `runtime` | 模型推理 API | `8700` |
| `console` | 管理控制台 | `8701` |
| `batch-worker-1` | 批量预测 Worker | - |
| `batch-worker-2` | 批量预测 Worker | - |
| `shadow-worker` | 影子预测 Worker | - |

PostgreSQL、Redis 和 MinIO 作为外部基础设施提供，不由当前 Compose 创建。

### 准备配置

```bash
cp docker/.env.example docker/.env.docker
```

至少配置：

```text
DATAMIND_DATABASE_URL
DATAMIND_TASK_QUEUE_BROKER_URL
DATAMIND_STORAGE_MINIO_*
DATAMIND_AUTH_SECRET_KEY
```

容器访问宿主机服务时，应使用 `host.docker.internal`，不要使用 `localhost`。

### 构建镜像

安装发布与构建工具依赖：

```bash
pip install -e ".[release]"
```

Linux：

```bash
  export DATAMIND_BUILD_COMMIT="$(git rev-parse HEAD)"
  export DATAMIND_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python -m scripts.build_docker
export DATAMIND_IMAGE_TAG=$(python -c "from scripts.build_docker import load_docker_metadata; print(load_docker_metadata().version)")
```

Windows PowerShell：

```powershell
$env:DATAMIND_BUILD_COMMIT = (git rev-parse HEAD).Trim()
$env:DATAMIND_BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  python -m scripts.build_docker
$env:DATAMIND_IMAGE_TAG = (python -c "from scripts.build_docker import load_docker_metadata; print(load_docker_metadata().version)").Trim()
```

  构建入口默认支持全部模型框架，并生成
  `docker.io/zhongshengchen/datamind:<project.version>`。单框架 Docker 镜像
  通过受控的 `--framework` 参数构建：

  ```bash
  python -m scripts.build_docker --framework sklearn
  python -m scripts.build_docker --framework xgboost
  python -m scripts.build_docker --framework lightgbm
  python -m scripts.build_docker --framework catboost
  python -m scripts.build_docker --framework full
  ```

  | Framework | Python extra | 默认镜像标签 |
  | --- | --- | --- |
  | `full` | `datamind[full]` | `docker.io/zhongshengchen/datamind:<version>` |
  | `sklearn` | `datamind[sklearn]` | `docker.io/zhongshengchen/datamind:<version>-sklearn` |
  | `xgboost` | `datamind[xgboost]` | `docker.io/zhongshengchen/datamind:<version>-xgboost` |
  | `lightgbm` | `datamind[lightgbm]` | `docker.io/zhongshengchen/datamind:<version>-lightgbm` |
  | `catboost` | `datamind[catboost]` | `docker.io/zhongshengchen/datamind:<version>-catboost` |

  `full` 使用纯版本标签，供混合框架 Runtime 使用；单框架部署选择对应专用
  标签。`--tag` 可以覆盖默认标签，Compose 继续通过 `DATAMIND_IMAGE_TAG`
  显式选择已构建镜像，并可通过 `DATAMIND_IMAGE_REPOSITORY` 覆盖默认仓库。
  镜像以
  `io.github.zhongsheng-chen.datamind.framework` 标注支持的模型框架。

  构建入口从 `pyproject.toml` 读取项目元数据与对应 extra，不维护第二份依赖
  清单。最终 Docker 镜像只安装构建出的 Wheel，不复制仓库源码作为运行目录。

### 数据库迁移与初始化

```bash
cd docker

docker compose --profile tools run --rm migrate
docker compose --profile tools run --rm init
```

首次初始化前请在 `.env.docker` 中设置管理员用户名和强密码，初始化完成后删除管理员初始密码。

### 启动

```bash
docker compose up -d
docker compose ps
```

访问：

```text
Runtime API   http://localhost:8700
Console       http://localhost:8701
```

查看日志：

```bash
docker compose logs --tail=100 -f
```

停止：

```bash
docker compose down
```

外部 PostgreSQL、Redis 和 MinIO 不会被该命令删除。

## 技术架构

Datamind 采用分层结构，将模型生命周期管理与在线推理解耦。

| 层 | 主要职责 |
| --- | --- |
| CLI / Console | 用户操作入口 |
| Services | 模型、部署、路由、实验等业务生命周期 |
| Runtime | 路由、模型装载、预测执行和运行协调 |
| Model / Artifact | 模型制品识别、校验、加载和 BentoML 管理 |
| Storage | Local / MinIO 模型制品存储 |
| DB | SQLAlchemy Repository、Unit of Work 和持久化模型 |
| Config | Pydantic Settings 与统一 Config Provider |
| Auth / Audit / Logging | 权限、安全、审计和可观测性 |

主要技术组件：

```text
Python
BentoML
PostgreSQL + SQLAlchemy + Alembic
Redis + Celery
MinIO
Typer
Starlette
Vite
pytest
```

## 项目结构

```text
datamind/
├── ab_test/       # A/B 实验
├── audit/         # 审计
├── auth/          # 认证与权限
├── cli/           # 命令行工具
├── config/        # 配置模型与 Provider
├── console/       # 管理控制台
├── constants/     # 公共枚举与常量
├── context/       # 请求上下文
├── core/          # 模型能力等核心逻辑
├── db/            # ORM、Repository、Unit of Work
├── logging/       # 结构化日志
├── models/        # 模型、制品与生命周期领域逻辑
├── runtime/       # 在线推理、路由、任务队列
├── services/      # 业务服务
├── storage/       # Local / MinIO 存储
└── utils/         # 公共工具

docker/            # Docker 镜像与 Compose
examples/          # 使用示例
frontend-tests/    # 前端测试
migrations/        # Alembic 迁移
tests/             # Python 测试
```

## 开发与测试

安装测试依赖：

```bash
pip install -e ".[test,full,release]"
```

运行快速测试：

```bash
pytest tests/unit
pytest tests/services
pytest tests/cli
pytest tests/console
npm run test:frontend
```

运行真实基础设施测试：

```bash
pytest -m integration
pytest tests/e2e
```

完整测试设计、隔离策略和 CI 说明见 [tests/README.md](tests/README.md)。

## 文档导航

- [CLI 使用说明](datamind/cli/README.md)
- [测试指南](tests/README.md)
- [环境变量模板](.env.example)
- [Docker 环境变量模板](docker/.env.example)
- [Docker Compose](docker/docker-compose.yml)
- [示例代码](examples/)

## 设计边界

Datamind 聚焦于模型交付和生产推理，而不是业务规则或授信审批决策。

```text
模型开发
   ↓
Datamind
   ├─ 注册
   ├─ 版本
   ├─ 部署
   ├─ 路由
   ├─ 推理
   ├─ 实验
   └─ 审计
   ↓
下游业务系统
   └─ 授信审批 / 业务决策
```

评分任务提供模型层面的分数、概率和特征分；分类任务提供模型层面的分类结果和概率。最终业务决策、额度策略和规则判断应由下游系统负责。
