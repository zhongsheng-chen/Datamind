# Datamind 发布指南

Datamind 使用 `.github/workflows/release.yml` 完成 Python 分发包、Docker
镜像和 GitHub Release 的统一发布。推送与项目版本匹配的 Git Tag 后，发布流程
自动启动。

## 发布目标配置

在 GitHub 仓库的 `Settings > Environments` 中创建 `release` Environment，并
配置以下 Variables：

| Variable               | 说明                               | 示例                              |
|------------------------|------------------------------------|-----------------------------------|
| `TWINE_REPOSITORY_URL` | Python 包仓库的 HTTPS 上传地址     | `https://upload.pypi.org/legacy/` |
| `TWINE_USERNAME`       | Python 包仓库用户名或 Token 用户名 | `__token__`                       |
| `DOCKERHUB_USERNAME`   | Docker Hub 用户名                  | `zhongshengchen`                  |

配置以下 Secrets：

| Secret            | 说明                       |
|-------------------|----------------------------|
| `TWINE_PASSWORD`  | Python 包仓库密码或 Token  |
| `DOCKERHUB_TOKEN` | Docker Hub 访问令牌        |

发布校验要求：

- `TWINE_REPOSITORY_URL` 必须使用 HTTPS。
- `TWINE_USERNAME` 和 `TWINE_PASSWORD` 必须与目标仓库的认证方式一致。
- `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` 必须具有镜像仓库写入权限。

`GITHUB_TOKEN`、`GITHUB_REF_NAME` 和 `GITHUB_OUTPUT` 由 GitHub Actions 提供，
无需手工配置。

## 验证发布配置

完成 Environment 配置后，在 GitHub 仓库的 `Actions` 页面选择
`Release Configuration Check`，点击 `Run workflow` 手动运行。
该工作流自身在 `main` 分支更新时也会自动运行。

该工作流会：

- 读取并校验 `release` Environment 中的 Twine 配置。
- 读取 `pyproject.toml` 中的镜像仓库配置。
- 使用配置的凭据登录 Docker Hub，然后立即退出。

检查过程不会上传 Python 分发包、推送 Docker 镜像或创建 GitHub Release。
PyPI Token 的项目权限将在首次正式上传时由 PyPI 最终校验。

## 项目发布配置

发布前检查 `pyproject.toml` 中的以下配置：

| 配置                                                 | 用途                                                  |
|------------------------------------------------------|-------------------------------------------------------|
| `project.name`                                       | Python distribution name 与分发包文件名              |
| `project.version`                                    | Python 包版本、Docker 镜像 Tag 和 GitHub Release 标题 |
| `project.authors`、`project.license`、`project.urls` | Python 包与 OCI 镜像元数据                            |
| `tool.datamind.oci`                                  | OCI 镜像标题和供应商信息                              |
| `tool.datamind.docker.repository`                    | 不含 Tag 的 Docker Hub 镜像仓库                       |

正式发布从 `tool.datamind.docker.repository` 读取镜像仓库，不在 GitHub 中重复
配置。当前仓库为 `docker.io/zhongshengchen/datamind`。

正式 Git Tag 必须严格使用 `v<project.version>` 格式。例如，项目版本为
`0.1.0` 时，只接受 `v0.1.0`。

## 执行发布

确认版本和发布配置后，提交版本变更并推送 Tag：

```bash
git tag v0.1.0
git push origin v0.1.0
```

Release Workflow 完成以下阶段：

1. 校验 Git Tag、项目版本和完整的 40 位 Git 提交哈希，并生成统一构建时间。
2. 执行完整测试工作流。
3. 测试通过后，并行处理 Python 分发包和 Docker 镜像：
   - 构建并验证 Wheel 和 sdist，测试最终 Wheel，再将分发包上传到目标仓库。
   - 分别构建、验证并推送 `sklearn`、`xgboost`、`lightgbm`、`catboost` 和
     `full` Docker 镜像。
4. 两类制品全部发布成功后，使用已经验证的 Python 分发包创建 GitHub
   Release。

Python distribution、Python import、CLI 与 Docker 使用不同层面的稳定名称：

| 对象 | 名称 |
| --- | --- |
| 项目品牌 | `Datamind` |
| PyPI distribution | `pydatamind` |
| Python import | `datamind` |
| CLI | `datamind` |
| Docker repository | `docker.io/zhongshengchen/datamind` |

发布准备步骤从 `project.name` 和 `project.version` 统一生成
`distribution`、`wheel_name` 与 `sdist_name`，后续构建、Smoke、上传和
GitHub Release 均直接使用这些输出。

发布流程拒绝覆盖已有 GitHub Release 或 Docker 镜像 Tag。Python 包仓库也应
启用版本不可变策略。

## 工作流内部变量

以下变量由 Release Workflow 自动生成或仅用于临时测试，不应配置为仓库
Variables 或 Secrets：

| 变量                          | 来源与用途                                   |
|-------------------------------|----------------------------------------------|
| `DATAMIND_BUILD_COMMIT`       | Tag 指向的 Git 提交哈希，写入 Wheel 和 sdist |
| `DATAMIND_BUILD_DATE`         | 本次发布统一使用的 UTC RFC 3339 构建时间     |
| `DATAMIND_RUN_WHEEL_SMOKE`    | 启用发布 Wheel 验证                          |
| `DATAMIND_RUN_DOCKER_SMOKE`   | 启用发布镜像验证                             |
| `DATAMIND_SMOKE_BUILD_COMMIT` | 验证制品中的 Git 提交哈希                    |
| `DATAMIND_SMOKE_BUILD_DATE`   | 验证制品中的构建时间                         |
| `DATAMIND_SMOKE_WHEEL`        | 指向当前工作流构建的 Wheel                   |
| `DATAMIND_SMOKE_DOCKER_IMAGE` | 指向当前矩阵任务构建的镜像                   |
| `DATAMIND_SMOKE_DATABASE_URL` | 连接当前作业的临时 PostgreSQL 服务           |

## 发布产物

每次发布生成：

- `pydatamind-<version>-py3-none-any.whl`
- `pydatamind-<version>.tar.gz`
- `<repository>:<version>`，即支持全部框架的镜像
- `<repository>:<version>-<framework>`，即各单框架镜像
- 名称为 `Datamind <version>` 的 GitHub Release

Python 分发包会作为工作流 Artifact 保留 14 天；正式包和镜像的保留策略由
对应的包仓库和镜像仓库管理。
