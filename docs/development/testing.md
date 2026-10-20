# 测试

本页说明如何为代码变更选择测试、准备运行条件并确认验证结果。后端测试使用 pytest，前端单元测试使用 Vitest，浏览器测试使用 Playwright。以下命令均在项目根目录执行。

## 选择测试范围

从本次修改直接影响的行为开始验证，再根据涉及的外部依赖和交付方式扩大范围。

| 变更内容                 | 优先运行                       | 按需补充                         |
|--------------------------|--------------------------------|----------------------------------|
| 公共模块、配置或模型处理 | `tests/unit/` 中的对应用例     | 模型框架测试                     |
| 业务规则和资源状态       | `tests/services/` 中的对应用例 | 真实数据库集成、后端完整流程     |
| 命令行或控制台接口       | `tests/cli/`、`tests/console/` | 服务层测试                       |
| 页面交互和前端状态       | `frontend-tests/unit/`         | `frontend-tests/e2e/` 浏览器测试 |
| 数据库、缓存或对象存储   | `tests/integration/`           | 使用该组件的业务流程             |
| 模型注册、部署和预测流程 | `tests/e2e/`                   | 对应框架的加载和推理测试         |
| 打包、依赖或镜像构建     | `tests/smoke/`                 | 安装后的控制台和静态资源验证     |

后端端到端测试验证真实业务流程；前端浏览器测试使用模拟 API 响应，验证页面交互。二者覆盖的边界不同，应根据修改内容分别选择。

## 本地测试

先按[开发环境](index.md#安装依赖)创建并激活虚拟环境。安装后端测试依赖：

```bash
python -m pip install -e ".[test]"
```

### 运行相关用例

根据修改范围，可以运行目录、文件或单个用例，也可以按名称筛选。以下以实验业务测试为例。

运行整个目录：

```bash
python -m pytest -ra tests/services/experiment
```

运行指定文件：

```bash
python -m pytest -ra tests/services/experiment/test_creation.py
```

运行单个用例：

```bash
python -m pytest -ra tests/services/experiment/test_creation.py::test_create_experiment_without_groups
```

按名称筛选用例，例如只运行名称中包含 `rolls_back` 的测试：

```bash
python -m pytest -ra tests/services/experiment -k "rolls_back"
```

需要检查普通后端测试时，执行以下命令，排除依赖可选模型框架的用例：

```bash
python -m pytest -ra -m "not framework" tests/unit tests/services tests/cli tests/console
```

构建相关用例还需要构建依赖和控制台资源。运行这部分测试前，安装 `.[test,release]`，并按[前端开发](frontend.md#构建与持续构建)完成资源构建。

### 验证模型框架

带 `framework` 标记的用例需要额外安装模型依赖。运行全部框架单元测试时，先安装完整依赖：

```bash
python -m pip install -e ".[test,full]"
```

随后运行框架用例：

```bash
python -m pytest -ra -m framework tests/unit
```

只验证某个框架时，可安装对应可选依赖，例如 `.[test,sklearn]`，并选择该框架的测试文件，避免运行其他框架的用例。

### 验证前端

安装前端依赖后，运行单元测试：

```bash
npm ci
npm run test:frontend
```

浏览器测试通过 `npm run test:e2e` 单独运行。Playwright 会构建前端并启动预览服务；浏览器安装和失败追踪见[前端开发](frontend.md#静态检查与测试)。

### 使用快捷命令

已安装 make 时，可以使用以下入口：

| 命令                  | 测试范围                                            |
|-----------------------|-----------------------------------------------------|
| `make test`           | 排除 `framework` 标记的单元、服务、CLI 和控制台测试 |
| `make test-framework` | 带 `framework` 标记的框架单元测试                   |
| `make test-frontend`  | 安装前端依赖并运行 Vitest                           |
| `make test-all`       | 汇总以上三项                                        |

快捷命令仍需要对应的 Python 依赖。`make test-all` 不包含真实组件集成、后端端到端、浏览器或交付物测试。

## 集成测试

涉及真实数据库、缓存和对象存储时，使用专用测试服务。连接参数通过当前进程的环境变量传入，测试夹具不会自动从 `.env` 加载这些参数。

### 配置测试服务

根据操作系统，在当前终端设置以下环境变量，并将地址和凭据替换为测试服务的实际值。

**Linux / macOS**

```bash
export DATAMIND_TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/datamind_test'
export DATAMIND_TEST_REDIS_URL='redis://127.0.0.1:6379/15'
export DATAMIND_TEST_MINIO_ENDPOINT='127.0.0.1:9000'
export DATAMIND_TEST_MINIO_ACCESS_KEY='test_access_key'
export DATAMIND_TEST_MINIO_SECRET_KEY='test_secret_key'
export DATAMIND_TEST_MINIO_BUCKET='datamind-test'
export DATAMIND_TEST_MINIO_SECURE='false'
```

**Windows PowerShell**

```powershell
$env:DATAMIND_TEST_DATABASE_URL = 'postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/datamind_test'
$env:DATAMIND_TEST_REDIS_URL = 'redis://127.0.0.1:6379/15'
$env:DATAMIND_TEST_MINIO_ENDPOINT = '127.0.0.1:9000'
$env:DATAMIND_TEST_MINIO_ACCESS_KEY = 'test_access_key'
$env:DATAMIND_TEST_MINIO_SECRET_KEY = 'test_secret_key'
$env:DATAMIND_TEST_MINIO_BUCKET = 'datamind-test'
$env:DATAMIND_TEST_MINIO_SECURE = 'false'
```

在设置变量的同一终端中运行测试。只运行部分集成用例时，提供对应服务的参数即可；涉及框架的用例还需安装相应模型依赖。

- **PostgreSQL**：使用专用数据库。夹具为每个用例创建独立的 `datamind_it_<随机标识>` schema，结束后删除，账号需要创建和删除 schema 的权限。
- **Redis**：使用独立测试 DB，与运行中的服务分开。
- **MinIO**：使用专用测试桶和对应访问凭据。

### 运行集成用例

配置就绪后，验证真实组件的交互：

```bash
python -m pytest -ra tests/integration
```

运行完整集成测试前，可安装 `.[test,full]`，以满足其中模型相关用例的依赖。缺少连接参数时，相关用例会跳过，需通过摘要确认预期测试实际执行。

### 验证后端完整流程

分类、评分和金丝雀发布用例需要 PostgreSQL 及完整模型依赖。安装 `.[test,full]` 并设置 `DATAMIND_TEST_DATABASE_URL` 后运行：

```bash
python -m pytest -ra tests/e2e
```

这些用例复用数据库隔离夹具，不要求同时提供 Redis 和 MinIO 参数，也不依赖前端浏览器。

## 冒烟测试

冒烟测试检查安装包和镜像的基本可用性，包括安装、依赖、构建信息及控制台启动。测试默认跳过，设置对应开关后才会执行；未指定已有产物时，测试会自行构建。

### Wheel 安装验证

Wheel 测试在隔离虚拟环境中安装软件包，检查 Python 导入、命令行入口和控制台启动。运行前准备专用 PostgreSQL 数据库，完成[控制台资源构建](frontend.md#构建与持续构建)，并安装测试与构建依赖：

```bash
python -m pip install -e ".[test,release]"
```

在当前终端开启测试并配置数据库连接，将示例地址替换为实际值。

**Linux / macOS**

```bash
export DATAMIND_RUN_WHEEL_SMOKE=1
export DATAMIND_SMOKE_DATABASE_URL='postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/datamind_test'
```

**Windows PowerShell**

```powershell
$env:DATAMIND_RUN_WHEEL_SMOKE = '1'
$env:DATAMIND_SMOKE_DATABASE_URL = 'postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/datamind_test'
```

在同一终端运行：

```bash
python -m pytest -ra tests/smoke/test_wheel.py
```

测试默认构建 Wheel，无需提前执行 `make build`。如需使用自定义控制台配置，可通过 `DATAMIND_SMOKE_ENV_FILE` 指定配置文件，替代直接提供数据库地址。

### Docker 镜像验证

Docker 测试检查镜像中的安装来源、构建信息和框架依赖。准备可用的 Docker 服务和后端测试依赖，再按待测框架运行；`full` 模式还会启动控制台，需要专用 PostgreSQL 数据库。

以下以 `full` 为例。数据库地址必须能从容器访问；数据库位于宿主机时，可使用测试已配置的 `host.docker.internal`，并替换示例凭据和端口。

**Linux / macOS**

```bash
export DATAMIND_RUN_DOCKER_SMOKE=1
export DATAMIND_SMOKE_DATABASE_URL='postgresql+asyncpg://test_user:test_password@host.docker.internal:5432/datamind_test'
```

**Windows PowerShell**

```powershell
$env:DATAMIND_RUN_DOCKER_SMOKE = '1'
$env:DATAMIND_SMOKE_DATABASE_URL = 'postgresql+asyncpg://test_user:test_password@host.docker.internal:5432/datamind_test'
```

在同一终端运行镜像构建与验证：

```bash
python -m pytest -ra tests/smoke/test_docker.py --framework full
```

`--framework` 支持 `sklearn`、`xgboost`、`lightgbm`、`catboost` 和 `full`，默认值为 `full`。选择单一框架时，测试验证镜像内容和框架依赖，不执行控制台启动检查，也无需提供数据库地址。

### 验证已有安装包或镜像

设置对应变量后，运行前面的测试命令即可跳过构建步骤：

- **Wheel**：通过 `DATAMIND_SMOKE_WHEEL` 指定文件路径。
- **Docker**：通过 `DATAMIND_SMOKE_DOCKER_IMAGE` 指定镜像名称，`--framework` 应与镜像一致。

同时设置 `DATAMIND_SMOKE_BUILD_COMMIT` 和 `DATAMIND_SMOKE_BUILD_DATE`，使其与待测版本的构建信息一致。测试开关、数据库等运行条件保持不变。

## 确认验证结果

测试结束后，结合执行范围和结果摘要确认本次变更已得到验证，并在提交说明中记录结果。

- **检查执行结果**：使用 `-ra` 查看跳过和预期失败等摘要。缺少服务参数或未开启冒烟测试导致的跳过，不代表验证通过。
- **说明验证范围**：记录已执行的测试、结果及尚未覆盖的部分。涉及文档修改时，同时完成[文档验证](documentation.md#验证与发布)。
- **核对 CI 覆盖**：新增框架或依赖时，检查[常规测试](https://github.com/zhongsheng-chen/Datamind/blob/main/.github/workflows/test.yml)、[Wheel 冒烟测试](https://github.com/zhongsheng-chen/Datamind/blob/main/.github/workflows/wheel-smoke.yml)和[Docker 冒烟测试](https://github.com/zhongsheng-chen/Datamind/blob/main/.github/workflows/docker-smoke.yml)是否包含相应验证。
