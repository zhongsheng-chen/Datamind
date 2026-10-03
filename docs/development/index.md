# 开发环境

本地开发推荐 Python 3.12 和 Node.js 24。先克隆仓库，在项目根目录创建并激活虚拟环境，再安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test,full,release]"
npm ci
npm run build:console
```

## 项目结构

| 路径 | 职责 |
| --- | --- |
| `datamind/cli/` | Typer 命令入口 |
| `datamind/services/` | 管理服务与资源约束 |
| `datamind/runtime/` | 路由、加载、预测与任务执行 |
| `datamind/models/` | 模型检查、Schema 与制品处理 |
| `datamind/config/` | 配置与校验 |
| `datamind/db/` | 数据模型、Repository 与迁移 |
| `datamind/ab_test/` | 分配、指标与分析 |
| `datamind/console/` | Console 后端与前端源码 |
| `tests/`、`frontend-tests/` | 后端与前端测试 |
| `build_support/`、`scripts/` | 构建和发布工具 |

## 开发阅读路径

- [数据库与扩展](extensions.md)：配置、Migration、新增 CLI 与模型框架。
- [前端](frontend.md)：界面代码与资源构建。
- [测试](testing.md)：分层测试与外部基础设施。
- [构建与 Release](release.md)：包、镜像与发布流程。
- [文档维护](documentation.md)：页面组织、参考生成与构建验证。

## 本地联调

准备专用 PostgreSQL，按[配置与初始化](../getting-started/configuration.md)设置工作目录 .env。需要批量和影子时同时准备 Redis，需要共享制品时选择 MinIO。在独立终端分别启动预测服务（`Runtime`）、Console 和任务 Worker，入口见[服务管理](../deployment/processes.md)。使用 examples 训练本地模型并跑快速上手，确认管理操作和预测链路。

Windows 虚拟环境激活使用 `.venv\Scripts\Activate.ps1`。所有进程保持相同工作目录，避免相对制品路径和 .env 指向不同位置。开发凭据、模型文件、日志和本地数据库数据不提交到仓库。测试环境与联调环境分开，避免运行清理 fixture 影响演示。
