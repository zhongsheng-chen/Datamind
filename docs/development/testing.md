# 测试

测试分为业务单元、真实基础设施、端到端流程和交付物验证。运行前安装 `.[test]`，框架用例另外安装对应 extra；全部框架可用 `.[test,full]`。

| 层次 | 路径 | 依赖与范围 |
| --- | --- | --- |
| Unit / Service / CLI / Console | tests/unit、tests/services、tests/cli、tests/console | 普通业务校验，框架用例带 framework 标记 |
| Integration | tests/integration | PostgreSQL、Redis、MinIO 与真实集成 |
| E2E | tests/e2e | 分类、评分、金丝雀后端链路，使用独立数据库 schema |
| Frontend | frontend-tests | Vitest 单元测试与 Playwright 浏览器测试 |
| Smoke | tests/smoke | 构建后的 Wheel 与 Docker 镜像 |

## 常规测试

```bash
make test
make test-framework
make test-frontend
make test-all
```

`test-all` 聚合普通后端、框架和前端单元测试，不包含 Integration、后端 E2E 与 Smoke。针对修改可直接运行 `python -m pytest -ra tests/services/experiment` 等相关目录。前端浏览器准备见[前端开发](frontend.md)。

## 真实基础设施

使用专用测试服务，配置：

```dotenv
DATAMIND_TEST_DATABASE_URL=postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/datamind_test
DATAMIND_TEST_REDIS_URL=redis://127.0.0.1:6379/15
DATAMIND_TEST_MINIO_ENDPOINT=127.0.0.1:9000
DATAMIND_TEST_MINIO_ACCESS_KEY=test_access_key
DATAMIND_TEST_MINIO_SECRET_KEY=test_secret_key
DATAMIND_TEST_MINIO_BUCKET=datamind-test
DATAMIND_TEST_MINIO_SECURE=false
```

```bash
python -m pytest -ra tests/integration
python -m pytest -ra tests/e2e
```

Integration conftest 在连接参数缺失时跳过相应测试。数据库 fixture 创建 `datamind_it_<随机标识>` schema 并在结束时删除，需要建删 schema 权限；使用专用数据库与桶。Redis 的测试 DB 与运行服务分开。测试报告中 skipped 不等于已完成集成验证。

CI 当前使用 Python 3.12–3.14、Node.js 24、PostgreSQL 17.11、Redis 8.8.2 和固定 MinIO 镜像；具体镜像摘要以 `.github/workflows/` 为准。新增依赖或框架支持应同步相关矩阵。

## 交付物 Smoke

先执行 `make build`，为 Wheel 配置 `DATAMIND_RUN_WHEEL_SMOKE=1` 和专用 `DATAMIND_SMOKE_DATABASE_URL`，运行 `python -m pytest -ra tests/smoke/test_wheel.py`。Docker 用例设置 `DATAMIND_RUN_DOCKER_SMOKE=1`，需要 Docker daemon，连接 URL 要能从容器访问数据库。

Smoke 可使用 `DATAMIND_SMOKE_DOCKER_IMAGE` 指定待测镜像，框架覆盖 sklearn、xgboost、lightgbm、catboost、full。涉及构建身份时设置对应 `DATAMIND_SMOKE_BUILD_COMMIT` 与 `DATAMIND_SMOKE_BUILD_DATE`。精确入口和参数以各 smoke 测试和独立 CI 工作流为准；不要用源码环境测试替代安装后的 Wheel 或容器测试。

## 文档验证

```bash
python -m scripts.generate_docs_reference --check
python -m mkdocs build --strict
```

文档构建检查导航和内部链接；命令、API 和业务约束仍需用对应测试与实际运行验证。
