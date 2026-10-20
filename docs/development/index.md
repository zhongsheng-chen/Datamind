# 开发环境

本文介绍如何从源码搭建 Datamind 开发环境，并验证本地开发配置。

## 环境要求

推荐使用以下开发工具，并按需准备运行依赖：

- Python 3.12
- Node.js 24
- PostgreSQL
- Redis
- MinIO（可选）

运行依赖的准备方式，请参阅[本地部署](../deployment/local.md)。

## 克隆仓库

```bash
git clone https://github.com/zhongsheng-chen/Datamind.git
cd Datamind
```

以下命令均在项目根目录执行。

## 安装依赖

创建虚拟环境：

```bash
python -m venv .venv
```

Linux 和 macOS：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

激活后，以可编辑模式安装项目和测试依赖，使源码修改直接生效：

```bash
python -m pip install -e ".[test]"
```

涉及模型预测时，按框架安装对应依赖，例如 `.[test,sklearn]`；需要全部框架时使用 `.[test,full]`。构建与发布工具的安装方式请参阅[构建与 Release](release.md)。

安装前端依赖并构建管理控制台：

```bash
npm ci
npm run build:console
```

## 验证环境

检查命令行入口：

```bash
datamind --help
```

运行前端单元测试：

```bash
npm run test:frontend
```

后端测试按修改范围选择执行，测试依赖和命令请参阅[测试](testing.md)。

## 本地联调

按照[本地部署](../deployment/local.md#配置)配置数据库和模型文件存储，完成初始化后启动服务。各进程使用同一工作目录和 `.env` 文件，确保配置与相对路径一致。

修改管理控制台前端时，可在另一个终端持续构建资源：

```bash
npm run watch:console
```

构建与浏览器测试请参阅[前端开发](frontend.md)。运行服务后，按照[快速上手](../getting-started/quickstart.md)验证模型注册、部署和预测流程。

联调与测试使用独立的数据资源，测试配置请参阅[测试](testing.md#集成测试)。开发凭据、模型文件、日志和本地数据库数据不提交到仓库。

## 项目结构

| 路径                        | 职责                            |
|-----------------------------|---------------------------------|
| `datamind/cli/`             | Typer 命令入口                  |
| `datamind/services/`        | 管理服务与资源约束              |
| `datamind/runtime/`         | 路由、加载、预测与任务执行      |
| `datamind/models/`          | 模型检查、Schema 与模型文件处理 |
| `datamind/config/`          | 配置与校验                      |
| `datamind/db/`              | 数据模型、Repository 与迁移     |
| `datamind/ab_test/`         | 分配、指标与分析                |
| `datamind/console/`         | Console 后端与前端源码          |
| `tests/`、`frontend-tests/` | 后端与前端测试                  |
| `scripts/`                  | 构建、发布、验证与文档生成入口  |
| `build_support/`            | 构建和发布支持工具              |
| `doc_support/`              | 参考文档生成逻辑、模板及元数据  |

## 开发指南

- [数据库与扩展](extensions.md)：配置、Migration、新增 CLI 与模型框架。
- [前端](frontend.md)：界面代码与资源构建。
- [测试](testing.md)：分层测试与外部基础设施。
- [构建与 Release](release.md)：包、镜像与发布流程。
- [文档维护](documentation.md)：页面组织、参考生成与构建验证。

