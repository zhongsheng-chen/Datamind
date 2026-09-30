<!--suppress HtmlDeprecatedAttribute -->
<div align="center">
  <h1>Datamind</h1>
  <p><strong>开放式模型服务管理平台</strong></p>
  <p>将模型交付为可管理、可部署、可调用、可审计的生产服务。</p>
  <p>
    <a href="https://github.com/zhongsheng-chen/Datamind/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/zhongsheng-chen/Datamind/actions/workflows/test.yml/badge.svg?branch=main"></a>
    <a href="https://datamind.readthedocs.io/"><img alt="Documentation" src="https://readthedocs.org/projects/datamind/badge/?version=latest"></a>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-blue">
    <a href="https://github.com/zhongsheng-chen/Datamind/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-green.svg"></a>
  </p>
  <p>
    <a href="https://datamind.readthedocs.io/"><strong>文档</strong></a> ·
    <a href="#quick-start"><strong>快速开始</strong></a> ·
    <a href="#features"><strong>核心能力</strong></a> ·
    <a href="#model-compatibility"><strong>模型支持</strong></a> ·
    <a href="#examples"><strong>示例</strong></a>
  </p>
</div>

---

## Datamind 是什么

Datamind 是一个开放式模型服务管理平台，专注于模型训练完成后的交付与运行。它连接模型开发与生产运行，让开发成果能够直接转化为生产服务。平台支持多框架、多任务和多算法，将复杂的交付、运行与治理沉淀为稳定的平台能力。

<a id="features"></a>

## 核心能力

- **多框架、多任务、多算法**：支持不同机器学习框架，保持一致的交付与运行方式。
- **渐进式模型发布**：支持全量、金丝雀和影子发布，让模型上线与切换更加可控。
- **在线与批量推理**：支持实时预测和批量预测，满足不同生产运行场景。
- **在线实验与评估**：支持 A/B 实验、稳定分桶和流量分配，用于真实流量下的模型效果评估。
- **全生命周期治理**：提供权限控制、操作审计和运行状态管理，让模型服务可追踪、可管理。

<a id="quick-start"></a>

## 快速开始

建议使用 Python 3.12 和 PostgreSQL 17，其中 Python 支持 `>=3.12,<3.15`。

如需异步任务或对象存储，还需分别配置 Redis 或 MinIO。已验证的版本为 Redis `8.8.2` 和 MinIO `RELEASE.2025-09-07T16-13-09Z`。

### 安装

从 PyPI 安装：

```bash
python -m pip install pydatamind
```

如需机器学习框架支持，可按需安装对应 extra，例如：

```bash
python -m pip install "pydatamind[sklearn]"
```

或安装全部支持的机器学习框架：

```bash
python -m pip install "pydatamind[full]"
```

从源码安装：

```bash
git clone https://github.com/zhongsheng-chen/Datamind.git
cd Datamind
python -m pip install -e .
```

从源码运行管理控制台前，需要构建前端资源，推荐使用 Node.js 24：

```bash
npm ci
npm run build:console
```

### 配置

创建 `.env` 配置文件，并设置以下首次运行所需参数。完整配置项及说明见 [`.env.example`](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example)。

```ini
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
```

- `DATAMIND_SERVICE_ENVIRONMENT`：指定运行环境。
- `DATAMIND_DATABASE_URL`：设置 PostgreSQL 数据库连接地址。
- `DATAMIND_AUTH_ENABLED`：启用认证。
- `DATAMIND_AUTH_SECRET_KEY`：设置 JWT 签名密钥。

请根据实际环境设置数据库连接地址和 JWT 签名密钥。生产部署配置见 [CLI 使用说明](datamind/cli/README.md) 和 [Docker 部署文档](https://datamind.readthedocs.io/en/latest/deployment/docker/)。

### 初始化

执行数据库迁移：

```bash
datamind db upgrade
```

创建首个管理员并完成系统初始化：

```bash
datamind init
```

默认管理员用户名和密码均为 `admin`。如需自定义，请在执行初始化前配置：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=replace-with-a-strong-password
```

### 登录

启用认证后，完成系统初始化即可登录 CLI：

```bash
datamind login --username admin
```

如已自定义管理员用户名，请替换命令中的 `admin`。按提示输入密码即可完成登录。CLI 会在本地保存登录凭据，供后续命令自动使用。

### 启动

启动服务：

```bash
datamind service run
```

在另一个终端启动管理控制台：

```bash
datamind console run
```

打开管理控制台：[http://127.0.0.1:8701](http://127.0.0.1:8701)，使用初始化时创建的管理员账号登录。

![Datamind 管理控制台登录界面](docs/assets/login.png)

<a id="model-compatibility"></a>

## 模型支持

Datamind 当前支持分类与评分两类任务，并兼容多种主流 Python 机器学习框架。

| 机器学习框架     | 分类 | 评分 |
|------------------|:----:|:----:|
| **scikit-learn** |  ✓  |  ✓  |
| **XGBoost**      |  ✓  |  —   |
| **LightGBM**     |  ✓  |  —   |
| **CatBoost**     |  ✓  |  —   |

- **分类任务**：支持 `sklearn.linear_model.LogisticRegression`、`sklearn.tree.DecisionTreeClassifier` 和 `sklearn.ensemble.RandomForestClassifier`，并兼容 `XGBoost`、`LightGBM` 与 `CatBoost`，返回分类标签与预测概率。
- **评分任务**：支持以 `sklearn.linear_model.LogisticRegression` 为估计器的 `optbinning.Scorecard`，返回违约概率、总评分与特征分。


<a id="examples"></a>

## 示例

示例位于源码仓库的 `examples/` 目录，请克隆仓库后在项目根目录运行。 相关依赖包括 `scikit-learn` 和 `optbinning`。若已安装 `pydatamind[sklearn]` 或 `pydatamind[full]`，可跳过依赖安装。

```bash
python -m pip install -e ".[sklearn]"
```

### 分类任务

以 `random-forest` 分类模型为例：

```bash
python examples/classification/random_forest/train.py

datamind model register random-forest \
  --version 1.0.0 \
  --model-path examples/classification/random_forest/artifacts/random_forest.pkl \
  --framework sklearn \
  --model-type random_forest \
  --task-type classification
```

### 评分任务

以 `scorecard` 评分模型为例：

```bash
python examples/scorecard/train.py

datamind model register scorecard \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

更多示例见 [examples](https://github.com/zhongsheng-chen/Datamind/tree/main/examples)。

## Docker 镜像

Datamind 的 Docker 镜像发布于 Docker Hub：

```text
docker.io/zhongshengchen/datamind:latest
```

Docker 镜像、Docker Compose 及相关配置见 [Docker 部署文档](https://datamind.readthedocs.io/en/latest/deployment/docker/)。

## 文档

安装、使用与部署说明见 [Documentation](https://datamind.readthedocs.io/)。


## 开发

安装开发环境：

```bash
python -m pip install -e ".[test,full,release]"
npm ci
npm run build:console
```

运行本地测试：

```bash
make test-all
```

构建：

```bash
make build
```

## 致谢

感谢所有参与 Datamind 开发、测试、文档与反馈的贡献者，以及为本项目提供基础能力的开源社区。

## License

Datamind 使用 [Apache License 2.0](LICENSE)。
