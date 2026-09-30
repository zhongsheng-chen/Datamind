# 构建与 Release

Python 包与 Docker 镜像共同交付后端、框架依赖和 Console 静态资源。版本来自 `pyproject.toml`，发布流程由 `.github/workflows/release.yml` 和 `scripts/release.py` 定义。

## 本地构建

```bash
python -m pip install -e '.[test,release]'
npm ci
make build
```

`make build` 先构建 Console，再构建 Wheel 和 sdist。产物在 `dist/`。`make build-docker` 调用 `scripts.build_docker`，具体框架与镜像参数可用 `python -m scripts.build_docker --help` 查看。不要只执行 Python 构建而遗漏 Console。

## 版本和构建身份

发布标签必须精确为 `v<pyproject 中的版本>`。同一次发布使用相同完整 40 位提交 SHA 和 UTC RFC 3339 构建日期，写入发行包及镜像元数据，确保可追溯。

```bash
python -m scripts.release prepare \
  --tag v<version> \
  --commit <40位提交SHA> \
  --build-date <UTC-RFC3339时间>
```

`prepare` 检查标签、版本与身份并生成发布元数据，不发布产物。正式包与所有镜像构建前设置同一身份：

```bash
export DATAMIND_BUILD_COMMIT=<40位提交SHA>
export DATAMIND_BUILD_DATE=<UTC-RFC3339时间>
make build
make build-docker
```

未设置身份的 Python 开发构建不能作为正式发布包。Docker 构建必须同时提供两个变量，否则直接失败。验证时传入同一身份：

```bash
python -m scripts.verify_distributions \
  --dist dist \
  --build-commit <40位提交SHA> \
  --build-date <UTC-RFC3339时间>
python -m scripts.verify_framework --help
```

发行包校验检查 Wheel/sdist 的版本、文件和构建身份。框架验证检查模型能力。按[测试指南](testing.md)对安装后的 Wheel 和最终镜像执行 Smoke。

## CI 发布顺序

1. 推送 `v*` 标签触发工作流。准备元数据并拒绝已经存在的 GitHub Release。
2. 通过复用的测试门禁，构建并验证 Python 发行包，执行 Wheel Smoke。
3. 在 release 环境校验 Twine 配置并上传 Python 产物。
4. 为 sklearn、xgboost、lightgbm、catboost、full 构建固定版本镜像，检查版本标签尚不存在，逐个通过 Docker Smoke 后推送。
5. Python 与所有版本镜像发布成功后，将 full 镜像更新为 latest。
6. 全部完成后创建 GitHub Release，上传准确的 Wheel/sdist 文件。

发布凭据通过 CI Secret 提供：`TWINE_REPOSITORY_URL`、`TWINE_USERNAME`、`TWINE_PASSWORD`、`DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`。发布前可分别执行 `scripts.release validate-twine-config`、`validate-dockerhub-config` 检查配置。凭据不能写入仓库。

## 失败处理

固定版本标签作为不可变交付物处理。某一步失败后，先确认哪些产物已经公开，核对提交、日期和版本。不要覆盖已经发布的版本。latest 和 GitHub Release 仅在完整交付成功后更新，因此不能把其中一项存在当作全部发布成功的证据。

需要修复已发布内容时递增版本，在新标签上重新执行验证。数据库升级与应用回滚的边界见[生产部署](../deployment/production.md)。
