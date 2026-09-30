# 文档盘点与验收

本页记录 [Issue #21](https://github.com/zhongsheng-chen/Datamind/issues/21) 的盘点、信息架构、实施结果与核对依据。盘点与验收日期为 2026-09-30。正式内容按当前代码、配置、Typer 定义、测试与实际运行编写。

## 现有资料盘点

| 来源 | 当前内容 | 处理方式 |
| --- | --- | --- |
| 根 README | 项目介绍、安装、配置、初始化、示例入口 | 保留已校正入口，不进行无关重写 |
| 原 docs/index.md | 项目介绍与安装命令 | 改为正式文档阅读入口 |
| 原 getting-started | 安装及服务启动，未覆盖首次预测 | 分离配置与初始化，补齐首次模型交付 |
| 原 concepts/architecture.md | 控制面、运行面和简化资源链 | 校正资源关系，新增资源生命周期页面 |
| 原 deployment/docker.md | 镜像和 Compose | 保留并核对现有 Compose，补充进程与生产主题 |
| datamind/cli/README.md | 大量命令说明与实验流程 | 只作选题线索，参数重新核对 Typer 与测试 |
| datamind/console/README.md | 前端开发与界面说明 | 分离产品操作和前端开发 |
| examples/README.md | 训练与制品注册 | 核对当前训练脚本、框架与制品校验 |
| tests/README.md | 测试运行说明 | 核对目录、标记、conftest、Makefile 和 CI |
| RELEASING.md | 发布说明 | 核对 release 脚本、构建配置和工作流 |
| .env.example / docker/.env.example | 应用与容器配置模板 | 与配置类一起作为字段核对依据 |
| .readthedocs.yaml / docs/requirements.txt | Python 3.12、MkDocs 严格构建 | 保持构建链路，补充本地无环境变量的构建支持 |

## 信息架构与页面边界

一级导航采用：首页、快速开始、核心概念、模型、部署、流量管理、A/B 测试、使用指南、CLI Reference、示例、Reference、开发。

| 目录 | 负责内容 | 不重复承担的内容 |
| --- | --- | --- |
| getting-started | 首次安装到模型调用 | 全部参数、复杂发布与实验流程 |
| concepts | 资源关系、职责与生命周期概念 | 逐项 CLI 参数 |
| models | 版本、制品修订与兼容性 | 训练算法教学 |
| deployment | full/canary/shadow、进程和生产运行 | 路由语法与实验分桶 |
| routing | 普通路由、比例、条件与时间 | 实验分组和 Outcome |
| experiments | 实验流程、Assignment、Outcome、分析 | 上层业务审批策略 |
| guides | 分类、评分、预测、Console 与访问控制操作 | 字段与默认值全集 |
| cli | 命令、参数、默认值、输出、权限和约束 | 完整任务教程 |
| examples | 当前仓库脚本、输入与制品入口 | 重复正式使用指南 |
| reference | 配置、API、状态与权限 | 为什么与操作步骤 |
| development | 环境、结构、扩展、测试、前端、发布 | 产品 Console 操作 |

## 核对依据

组件 README 仅用于选题盘点，正文根据以下实现重新核对；参数和默认值从当前定义生成，操作指南说明业务顺序和限制。

| 主题 | 代码与测试依据（仓库相对路径） | 正文覆盖 |
| --- | --- | --- |
| 安装和配置 | pyproject.toml、package.json、datamind/config/、tests/unit/config/ | 补齐分组字段、默认值、校验与运行条件 |
| 初始化与首次交付 | datamind/cli/init.py、auth/、model/、deployment/、route/；tests/e2e/ | 实际跑通安装、初始化、登录、部署、路由与预测 |
| 版本与制品 | datamind/services/registration.py、lifecycle.py、deletion.py；tests/services/model/ | 修订更新、幂等、状态转换与清理约束 |
| 兼容性 | datamind/constants/model_type.py、models/artifact/formats.py、handlers/、schema.py；tests/unit/models/、tests/integration/inference/ | 逐框架对象、格式、输入 Schema 与错误示例 |
| Deployment / Runtime | datamind/services/deployment.py、control.py、runtime/manager.py、reconciler.py；tests/services/deployment/、tests/unit/runtime/ | 生命周期、目标与实际状态、多 Worker 行为 |
| 发布与 Routing | datamind/cli/deployment/create.py、route/、runtime/routing/；tests/e2e/test_canary_flow.py、tests/unit/routing/ | 独立发布指南、规则语法、比例与回退的范围 |
| Experiment / Assignment | datamind/services/experiment.py、ab_test/assignment.py、engine.py；tests/services/experiment/、tests/unit/ab_test/ | 端到端实验、hash/manual、主体解析、稳定性与配置变更限制 |
| Outcome / Analysis | datamind/services/outcome.py、cli/outcome/、ab_test/analyzer.py、metrics.py；tests/services/experiment/test_outcome.py | 关联、幂等、观察窗口、指标与样本解释 |
| 在线与批量 | datamind/runtime/server/prediction.py、schemas.py、services/batch.py、runtime/task_queue/；tests/integration/celery/ | HTTP 示例、任务查询、取消、重试和失败处理 |
| Docker 与生产 | docker/Dockerfile、docker-compose.yml、datamind/config/worker.py；tests/smoke/、.github/workflows/docker-smoke.yml | 基础设施、共享存储、探针、多实例和升级步骤 |
| Console 与权限 | datamind/console/routes.py、actions.py、static/；services/identity.py、auth/、constants/permissions.py；tests/console/、tests/services/identity/ | 真正运行 Console，按实际页面截图并记录操作 |
| CLI Reference | datamind/cli/main.py 及各 Typer 命令；tests/cli/ | 按命令组拆页，核对参数、输出、权限和状态限制 |
| 开发与发布 | Makefile、scripts/、build_support/、datamind/db/migrations/、frontend-tests/、.github/workflows/ | 完整环境、扩展、Migration、测试分层与发布验证 |

已核对的重要差异：Routing 创建默认不启用；canary 必须指定角色；实验曝光比例与 Variant 权重分别管理；manual 不进行 hash 曝光；版本和制品修订分别管理；make test-all 不包含所有 Integration/E2E/Smoke。

## Issue #21 验收映射

| 验收项 | 正式入口 |
| --- | --- |
| 1. 完整信息架构与导航 | MkDocs 的 12 个一级导航及本文页面边界 |
| 2. 安装到首次模型服务 | [安装](docs/getting-started/installation.md)、[初始化](docs/getting-started/configuration.md)、[快速上手](docs/getting-started/quickstart.md) |
| 3. Deployment / Routing / Runtime 关系 | [架构](docs/concepts/architecture.md)、[资源](docs/concepts/resources.md)、[部署](docs/deployment/index.md) |
| 4. 独立发布指南 | [full](docs/deployment/full.md)、[canary](docs/deployment/canary.md)、[shadow](docs/deployment/shadow.md) |
| 5. 端到端 A/B | [实验流程](docs/experiments/index.md) |
| 6. 曝光比例与分组权重 | [Assignment](docs/experiments/assignment.md) |
| 7. Assignment / Outcome / Analysis | [分配](docs/experiments/assignment.md)、[回流](docs/experiments/outcomes.md)、[分析](docs/experiments/analysis.md) |
| 8. 兼容性与制品 | [兼容性](docs/models/compatibility.md)、[模型与版本](docs/models/index.md) |
| 9. Docker / Runtime / Worker / 生产 | [Docker](docs/deployment/docker.md)、[进程](docs/deployment/processes.md)、[生产](docs/deployment/production.md) |
| 10. CLI 与 Guides 分离 | [逐命令 Reference](docs/cli/index.md)、[模型指南](docs/guides/models.md) |
| 11. Console / 认证 / 权限 | [操作手册](docs/guides/console.md)、[身份](docs/guides/access-control.md)、[权限表](docs/reference/states-permissions.md) |
| 12. 开发 / 测试 / 构建 / Release | [开发](docs/development/index.md)、[测试](docs/development/testing.md)、[发布](docs/development/release.md) |
| 13. RTD 构建与内部链接 | 保留 .readthedocs.yaml 严格配置，本地同配置 strict 构建 |
| 14. 组件 README 收敛 | cli、console、examples、tests README 保留开发说明并链接正式文档；RELEASING 链接正式发布页 |

CLI Reference 共 70 个叶子命令，配置表共 85 个环境变量，Runtime 请求字段按当前 Pydantic 模型生成。维护入口为 `scripts/generate_docs_reference.py`，`--check` 检测定义与文档漂移。业务行为未因文档需求修改。

## 实际运行与截图

根据用户追加范围，已重建独立演示数据库与截图，使用申请评分、行为评分、催收评分、欺诈风险、多头借贷风险和违约概率六个模型。评分任务复用 scorecard 示例，分类任务分别使用 CatBoost、XGBoost 和随机森林。

申请评分使用 80% 主路由、20% 副路由、100% 影子路由及 hash 实验，回流 64 条模拟 T+30 Outcome。演示追加约三万次在线调用，以及每个模型各 50、100、200 条实例的批量任务。完成后删除多头借贷风险模型，记录回收站、历史调用和最终概览。实际完成计数以 Console 手册为准。

截图直接保存到 `docs/assets/`，共 27 张，以评分卡为主线。最终 overview 显示底部模型表与排行的全部六行；仅截图时展开列表，手册说明界面实际可滚动。模型命名和制品文件对应申请、行为、催收评分及三个分类演示。

## 文档验证

在项目环境安装文档依赖并执行：

```bash
python -m pip install -r docs/requirements.txt
python -m scripts.generate_docs_reference --check
python -m mkdocs build --strict
```

导航遗漏、目标文件缺失与锚点问题按警告处理，严格构建会失败。配置依据见 [MkDocs validation](https://www.mkdocs.org/user-guide/configuration/#validation)。本地 site_url 有默认值；ReadTheDocs 提供的 canonical URL 可覆盖它。

构建通过只验证文档结构与链接，不代表命令或所有产品流程已经端到端验证；运行证据应记录在具体指南中。

验收时本地严格构建通过，Reference 漂移检查通过；配置、Routing、A/B、认证、模型、部署、实验、身份等相关 1,135 个测试通过（880 个业务与配置用例、255 个 CLI 与模型结构用例）。截图引用已核对，所有图片都被正式页面引用。代码格式与静态检查覆盖新增 Reference 生成器和信贷分类示例。ReadTheDocs 线上部署将在仓库变更发布后执行，本次不将本地构建描述为线上已发布。
