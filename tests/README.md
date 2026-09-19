# Datamind 测试指南

Datamind 的测试用于验证系统行为是否符合预期，并确认代码变更不会破坏既有功能。测试按验证范围分层组织，从局部行为验证逐步扩展到跨组件交互、完整运行链路和发布产物验证。

> [!NOTE]
> 核心原则：在尽可能低的测试层级验证行为，只在需要验证真实组件边界时引入外部基础设施。

## 目录

- [快速开始](#快速开始)
- [测试架构](#测试架构)
- [目录结构](#目录结构)
- [如何选择测试层级](#如何选择测试层级)
- [测试分层](#测试分层)
- [运行测试](#运行测试)
- [测试环境与隔离](#测试环境与隔离)
- [持续集成](#持续集成)
- [故障排查](#故障排查)

---

## 快速开始

安装完整 Python 测试依赖：

```shell
pip install -e ".[test,full,release]"
```

其中 `test` 提供通用测试依赖，`full` 提供全部模型框架，`release` 提供
Wheel、sdist 与 Docker 构建工具。Datamind Runtime 依赖不包含发布工具。

安装前端依赖：

```shell
npm install
```

运行快速测试：

```shell
pytest tests/unit
pytest tests/services
pytest tests/cli
pytest tests/console
npm run test:frontend
```

运行需要真实基础设施的测试：

```shell
pytest -m integration
pytest -m e2e
```

Wheel Smoke 默认不执行真实发布验证，需要显式启用：

```powershell
$env:DATAMIND_RUN_WHEEL_SMOKE = "1"
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
.\.venv\Scripts\python.exe -m pytest tests/smoke/test_wheel.py
```

---

## 测试架构

Datamind 将测试分为快速反馈、真实集成、完整业务链路和发布验证四类。不同层级验证不同责任，避免重复覆盖同一行为。

| 层级 | 目录 | 关注点 | 真实基础设施 |
| --- | --- | --- | :---: |
| Unit | `tests/unit/` | 纯逻辑、转换、解析、校验、组件内部行为 | 否 |
| Service | `tests/services/` | 业务逻辑、生命周期、状态转换、领域约束 | 否 |
| CLI | `tests/cli/` | 参数、权限、Service 调用、退出码、终端输出 | 否 |
| Console | `tests/console/` | HTTP 接口、认证、权限、SSE、写操作、静态资源 | 否 |
| Integration | `tests/integration/` | PostgreSQL、Redis、Celery、MinIO、模型制品、Runtime 等真实边界 | 是 |
| Backend E2E | `tests/e2e/` | 不经过浏览器的完整后端业务链路 | 是 |
| Smoke | `tests/smoke/` | 发布产物安装、启动和最低可用性 | 是 |
| Frontend Unit | `frontend-tests/unit/` | 前端逻辑和 DOM 行为 | 否 |
| Browser E2E | `frontend-tests/e2e/` | 浏览器用户流程 | 是 |

---

## 目录结构

```text
tests/
├── unit/
├── services/
├── cli/
├── console/
├── integration/
│   ├── celery/
│   ├── db/
│   ├── inference/
│   ├── redis/
│   ├── runtime/
│   └── storage/
├── e2e/
│   ├── test_classification_flow.py
│   ├── test_scoring_flow.py
│   └── test_canary_flow.py
├── smoke/
│   ├── test_docker.py
│   └── test_wheel.py
├── conftest.py
└── README.md

frontend-tests/
├── unit/
└── e2e/
```


---

## 如何选择测试层级

新增测试时，优先使用能够验证目标行为的最低层级：

```text
纯逻辑、转换、解析、校验或组件内部行为？
  └─► tests/unit/

业务逻辑、生命周期、状态转换或领域约束？
  └─► tests/services/

CLI 参数、命令、退出码或终端输出？
  └─► tests/cli/

Console HTTP 接口、认证、权限或 SSE？
  └─► tests/console/

需要验证 PostgreSQL、Redis、Celery、MinIO、模型制品或 Runtime 等真实集成边界？
  └─► tests/integration/

需要验证跨多个组件的完整后端业务链路？
  └─► tests/e2e/

需要验证构建出的发行包能否安装、启动并提供最低服务能力？
  └─► tests/smoke/
```

> [!IMPORTANT]
> 不要根据生产代码所在目录决定测试目录。例如，`datamind/runtime/` 中的代码既可能由 Unit 测试验证，也可能属于 Integration 测试，取决于测试是否跨越真实运行边界。

---

## 测试分层

### Unit

`tests/unit/` 验证无外部基础设施依赖的代码行为。

典型内容包括：

- 参数转换与数据校验；
- 解析与格式化逻辑；
- 配置加载、转换与校验；
- 模型适配逻辑；
- 可以通过 Mock 隔离外部边界的组件。

Unit 测试应满足：

- 快速；
- 确定性；
- 无外部状态；
- 可并行、可重复执行。

### Service

`tests/services/` 验证业务逻辑、生命周期、状态转换和领域约束，例如：

- 模型注册与版本生命周期；
- 部署状态转换；
- 路由规则；
- 实验生命周期；
- 权限与业务约束。

Service 测试可以通过 Mock 隔离 Repository、Runtime 或其他外部边界，但不应 Mock 被测试的业务逻辑。

### CLI

`tests/cli/` 验证 CLI 命令及其交互行为，包括：

- 命令与参数是否正确暴露；
- 参数校验；
- Service 调用；
- 权限处理；
- 退出码；
- 用户可见终端输出。

CLI 使用 Typer / Click / Rich。Rich 可能在命令行参数名称内部插入 ANSI 控制字符，因此帮助信息或带参数名称的错误输出应先归一化：

```python
from click import unstyle

output = unstyle(result.output)
assert "--startup-timeout" in output
```

> [!NOTE]
> `pytest --color=no` 只控制 pytest 自身日志颜色，不能替代 `click.unstyle()`。

### Console

`tests/console/` 验证 Console HTTP 接口行为，包括：

- HTTP 状态码；
- 请求和响应结构；
- 身份认证与权限；
- SSE；
- 写操作；
- 静态资源入口。

Console 测试不负责验证 PostgreSQL、Redis 或 MinIO 的真实交互；这些边界属于 Integration。

### Integration

`tests/integration/` 验证 Datamind 与真实运行组件之间的集成边界。

当前覆盖：

- `db/`：真实 PostgreSQL、Repository、Unit of Work；
- `redis/`：真实 Redis 行为；
- `celery/`：真实 Redis Broker 与 Celery Worker；
- `storage/`：真实 MinIO 与模型制品存取；
- `inference/`：真实模型制品序列化、加载和推理兼容性；
- `runtime/`：RuntimeManager、ModelLoader、BentoML Model Store 等运行边界。

Integration 测试使用：

```python
@pytest.mark.integration
```

如果声明要验证的真实基础设施不可用，应明确 `skip`；不得通过 Mock 把缺失的真实边界伪装成已验证。

### Backend E2E

`tests/e2e/` 验证多个真实组件组合后的完整后端业务链路。

当前覆盖：

- Classification Flow；
- Scoring Flow；
- Canary Flow。

典型链路：

```text
模型制品
  ↓
模型注册 / 激活
  ↓
Deployment
  ↓
Routing
  ↓
Runtime
  ↓
Prediction / Scoring
  ↓
Request / Decision / Execution / Audit
```

Backend E2E 使用：

```python
@pytest.mark.e2e
```

E2E 关注系统行为，不重复验证单个组件内部实现。

### Smoke

`tests/smoke/` 验证发布产物的最低可用性。

当前 Wheel Smoke 流程：

```text
Build Wheel
  ↓
创建全新 Python 虚拟环境
  ↓
安装 Wheel
  ↓
datamind --help
  ↓
启动 Console
  ↓
GET /
  ↓
HTTP 200
```

它回答的问题是：

> 当前构建出的 Datamind Wheel 能否在一个干净环境中安装、启动并提供最低服务能力？

Docker Smoke 真实构建 multi-stage Docker 镜像，并验证：

- `datamind --version` 中的 Version、Commit 和 Build Date；
- `datamind` 从 `site-packages` 导入，不来自仓库工作树；
- OCI Image Metadata；
- Console 最小启动与首页健康路径。

> [!IMPORTANT]
> Smoke 测试不承担 Classification、Scoring、Canary 等完整业务流程验证。

---

## 运行测试

### Python

运行全部 Python 测试：

```shell
pytest
```

按层级运行：

```shell
pytest tests/unit
pytest tests/services
pytest tests/cli
pytest tests/console
pytest tests/integration
pytest tests/e2e
pytest tests/smoke
```

按 Marker 运行：

```shell
pytest -m integration
pytest -m e2e
pytest -m smoke
```

运行单个文件或测试：

```shell
pytest tests/services/model/test_registration.py
pytest tests/services/model/test_registration.py::test_register_model
```

### Coverage

```shell
pytest --cov=datamind --cov-branch --cov-report=term-missing
```

### Frontend

```shell
npm run test:frontend
npm run test:e2e
```

---

## 测试环境与隔离

### Integration 基础设施

Integration 测试通过专用的 `DATAMIND_TEST_*` 环境变量配置测试基础设施。

| 环境变量 | 用途 |
| --- | --- |
| `DATAMIND_TEST_DATABASE_URL` | 设置测试数据库连接地址 |
| `DATAMIND_TEST_REDIS_URL` | 设置 Redis 连接地址 |
| `DATAMIND_TEST_MINIO_ENDPOINT` | 设置 MinIO 服务地址 |
| `DATAMIND_TEST_MINIO_ACCESS_KEY` | 设置 MinIO Access Key |
| `DATAMIND_TEST_MINIO_SECRET_KEY` | 设置 MinIO Secret Key |
| `DATAMIND_TEST_MINIO_BUCKET` | 设置 MinIO Bucket |
| `DATAMIND_TEST_MINIO_SECURE` | 设置是否使用 TLS 连接 MinIO |

缺少所需环境变量时，对应测试应明确 `skip` 并说明缺失项。

> [!WARNING]
> 测试基础设施不得回退到开发或生产实例。Integration 和 Backend E2E 的数据库连接只通过专用测试环境变量提供。

### PostgreSQL

```powershell
$env:DATAMIND_TEST_DATABASE_URL = "postgresql+asyncpg://user:password@127.0.0.1:5432/datamind_test"
```

PostgreSQL fixture 为每个测试创建独立 schema：

```text
datamind_it_<uuid>
```

测试完成后自动删除，从而避免不同测试共享业务表状态。

### Redis

```powershell
$env:DATAMIND_TEST_REDIS_URL = "redis://127.0.0.1:6379/15"
```

Integration 应使用专用测试 Redis，不与开发或生产实例共享测试状态。

### MinIO

MinIO 测试通过 `DATAMIND_TEST_MINIO_*` 环境变量设置独立的测试 Bucket 和专用测试凭据：

```powershell
$env:DATAMIND_TEST_MINIO_ENDPOINT = "127.0.0.1:9000"
$env:DATAMIND_TEST_MINIO_ACCESS_KEY = "datamind_test"
$env:DATAMIND_TEST_MINIO_SECRET_KEY = "datamind_test_secret"
$env:DATAMIND_TEST_MINIO_BUCKET = "datamind-integration-test"
$env:DATAMIND_TEST_MINIO_SECURE = "false"
```

> [!WARNING]
> 严禁在测试代码、配置文件、日志或文档中暴露生产环境凭据，包括 Access Key 和 Secret Key。

### Backend E2E

Backend E2E 当前需要真实 PostgreSQL：

```powershell
$env:DATAMIND_TEST_DATABASE_URL = "postgresql+asyncpg://user:password@127.0.0.1:5432/datamind_test"
pytest tests/e2e -m e2e --basetemp=.pytest-tmp-e2e
```

每个后端 E2E 使用隔离的：

- PostgreSQL schema；
- 制品目录；
- BentoML Home。

测试不应依赖项目根目录 `.env` 中的开发或生产连接配置。

### Wheel Smoke

显式启用 Wheel Smoke：

```powershell
$env:DATAMIND_RUN_WHEEL_SMOKE = "1"
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
.\.venv\Scripts\python.exe -m pytest `
    tests/smoke/test_wheel.py `
    --basetemp=.pytest-tmp-wheel
```

测试会在全新的 Python 虚拟环境中重新安装当前 Wheel，并验证 CLI 与 Console。

默认使用隔离的最小 Console 配置，不复制项目根目录 `.env`。确实需要额外配置时：

```powershell
$env:DATAMIND_SMOKE_ENV_FILE = "C:\path\to\wheel-smoke.env"
```

Wheel 安装默认继承 pip 自身索引配置。上例显式使用阿里云 PyPI 镜像；设置
`PIP_INDEX_URL` 后，Smoke 测试会向构建和安装 Wheel 的 pip 命令传递
`--index-url`。

---

## 持续集成

主测试 Workflow：

```text
.github/workflows/test.yml
```

| Job | 执行内容 | 基础设施 |
| --- | --- | --- |
| `quick-checks` | Unit / Service / CLI / Console / Vitest | 无外部服务 |
| `integration` | `pytest -m integration` | PostgreSQL / Redis / MinIO |
| `backend-e2e` | `pytest tests/e2e` | PostgreSQL |

Wheel Smoke 使用独立 Workflow：

```text
.github/workflows/wheel-smoke.yml
```

当前通过 `workflow_dispatch` 手动触发。

Docker Smoke 使用独立 Workflow：

```text
.github/workflows/docker-smoke.yml
```

本地显式启用 Docker Smoke：

```powershell
$env:DATAMIND_RUN_DOCKER_SMOKE = "1"
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
python -m pytest `
    tests/smoke/test_docker.py `
    --framework=full `
    --basetemp=.pytest-tmp-docker-smoke
```

CI 中 pytest 统一使用：

```shell
--color=no -ra
```

- `--color=no`：避免 pytest ANSI 控制字符进入 GitHub Actions 日志；
- `-ra`：输出 skipped、xfail、xpass、failed、error 等结果摘要。

这些参数只属于 CI 日志策略。本地直接执行 `pytest` 时继续使用 pytest 默认终端行为。

---

## 故障排查

### Windows 临时目录权限

Windows 上如果 pytest 受到系统临时目录 ACL 影响，可指定项目内独立临时目录：

```powershell
pytest tests/unit --basetemp=.pytest-tmp-unit
```

Integration：

```powershell
pytest -m integration --basetemp=.pytest-tmp-integration
```

Backend E2E：

```powershell
pytest tests/e2e --basetemp=.pytest-tmp-e2e
```

Wheel Smoke：

```powershell
pytest tests/smoke/test_wheel.py --basetemp=.pytest-tmp-wheel
```

`.pytest-tmp-*` 仅用于本地测试临时数据，不应提交到版本库。

### CLI 断言包含 ANSI

如果 Typer / Rich 输出中的完整 option 无法直接匹配，优先使用：

```python
from click import unstyle

output = unstyle(result.output)
```

不要通过关闭生产 CLI 样式来修复测试。
