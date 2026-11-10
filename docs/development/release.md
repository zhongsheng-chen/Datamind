# 构建与发布

本文介绍 Datamind 的本地构建、构建验证与发布流程。

## 构建准备

环境配置请参阅[开发环境](index.md)。在项目根目录运行：

```bash
python -m pip install -e '.[test,release]'
```

该命令以可编辑模式安装 Datamind，并安装构建和测试所需的依赖。

## 构建标识

构建 Docker 镜像和正式发布的 Python 发行包时，需记录源码提交与构建时间。同一次发布使用相同的构建标识，可通过以下命令设置：

```bash
export DATAMIND_BUILD_COMMIT="$(git rev-parse HEAD)"
export DATAMIND_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## 本地构建

### Python 发行包

安装 [Make](https://www.gnu.org/software/make/) 后，可运行以下命令构建发行包：

```bash
make build
```

该命令会安装前端依赖、构建管理控制台前端资源，并在 `dist/` 目录生成 Wheel 和 sdist 发行包。未安装 Make 时，可依次执行以下等效命令：

```bash
npm ci
npm run build:console
python -m build
```

### Docker 镜像

安装并启动 [Docker](https://docs.docker.com/get-started/get-docker/)，然后运行以下命令构建镜像：

```bash
docker build -f docker/Dockerfile -t datamind \
  --build-arg DATAMIND_BUILD_COMMIT \
  --build-arg DATAMIND_BUILD_DATE \
  .
```

该命令在本地生成 `datamind:latest` 镜像，不会推送到 Docker Hub。 Python 依赖默认从 PyPI 安装。如需使用其他镜像源，可通过 `--build-arg` 设置 `PIP_INDEX_URL`，例如[清华 PyPI 镜像源](https://pypi.tuna.tsinghua.edu.cn/simple)或[阿里云 PyPI 镜像源](https://developer.aliyun.com/mirror/pypi)。

以下示例使用清华 PyPI 镜像源：

```bash
docker build -f docker/Dockerfile -t datamind \
  --build-arg DATAMIND_BUILD_COMMIT \
  --build-arg DATAMIND_BUILD_DATE \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  .
```

如需指定模型框架，可通过 `DATAMIND_PYTHON_EXTRA` 构建参数设置：

```bash
docker build -f docker/Dockerfile -t datamind:sklearn \
  --build-arg DATAMIND_BUILD_COMMIT \
  --build-arg DATAMIND_BUILD_DATE \
  --build-arg DATAMIND_PYTHON_EXTRA=sklearn \
  .
```

### 构建脚本

项目提供了构建脚本，也可通过 Make 构建镜像：

```bash
make build-docker
```

该命令构建包含全部模型框架的镜像，镜像名称为 `docker.io/zhongshengchen/datamind:<version>`。 如需指定模型框架，可使用以下命令：

```bash
make build-docker FRAMEWORK=<framework>
```

该命令构建指定模型框架的镜像，镜像名称为 `docker.io/zhongshengchen/datamind:<version>-<framework>`。 未安装 Make 时，可直接运行构建脚本：

```bash
python -m scripts.build_docker --framework <framework>
```

更多选项请参阅 `python -m scripts.build_docker --help`。

## 构建验证

### Python 发行包

使用构建时的提交 SHA 和构建时间验证发行包：

```bash
python -m scripts.verify_distributions \
  --dist dist \
  --build-commit "$DATAMIND_BUILD_COMMIT" \
  --build-date "$DATAMIND_BUILD_DATE"
```

该命令检查 Wheel 和 sdist 的版本、文件及构建标识。

### Docker 镜像

检查本地镜像的构建标识：

```bash
docker image inspect datamind:latest --format '{{json .Config.Labels}}'
```

确认 `org.opencontainers.image.version`、`org.opencontainers.image.revision` 和 `org.opencontainers.image.created` 分别与本次构建的版本、提交 SHA 和构建时间一致。

升级现有部署，请参阅[升级](../deployment/upgrade.md)。

## CI 发布流程

### 发布配置

发布任务使用 GitHub Actions 的 `release` 环境。发布地址和用户名通过 Variables 配置，密码和令牌通过 Secrets 配置：

| 类型 | 配置项 |
| --- | --- |
| Variables | `TWINE_REPOSITORY_URL`、`TWINE_USERNAME`、`DOCKERHUB_USERNAME` |
| Secrets | `TWINE_PASSWORD`、`DOCKERHUB_TOKEN` |

在本地设置对应环境变量后，可检查配置是否完整、仓库地址格式是否正确：

```bash
python -m scripts.release validate-twine-config
python -m scripts.release validate-dockerhub-config
```

### 发布步骤

Git 标签采用 `v<version>` 格式，其中 `<version>` 与 `pyproject.toml` 中的版本一致。发布前，可在本地执行以下命令校验发布信息：

```bash
python -m scripts.release prepare \
  --tag v<version> \
  --commit "$DATAMIND_BUILD_COMMIT" \
  --build-date "$DATAMIND_BUILD_DATE"
```

推送 `v*` 标签后，工作流校验发布信息并运行自动化测试。若 GitHub Release 已存在，则终止发布。测试通过后，两条流程并行执行：

- **Python 发行包**：构建并校验 Wheel 和 sdist，通过 Wheel Smoke 测试后，检查 Twine 配置并上传发行包。
- **Docker 镜像**：并行构建 sklearn、xgboost、lightgbm、catboost 和 full 镜像。各任务先确认版本标签尚未使用，再构建镜像，通过 Docker Smoke 测试后推送。

Python 发行包和全部版本镜像发布成功后，工作流将 full 镜像更新为 `latest`，随后创建 GitHub Release，并上传本次构建的 Wheel 和 sdist。预发布版本会标记为 GitHub 预发布，Docker `latest` 同样更新。

## 失败处理

发布失败后，先确认各项发布状态，再决定如何处理：

- 检查 Python 发行包、各版本镜像、`latest` 和 GitHub Release，确认哪些步骤已完成。
- 核对已发布内容的版本、提交 SHA 和构建时间。
- 不要覆盖已发布的版本。如需修复，递增版本号后重新发布。
