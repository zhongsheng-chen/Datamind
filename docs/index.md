# Datamind

**Datamind 是一个开放式模型服务管理平台，用于将已经训练完成的 Python 模型交付为可管理、可部署、可调用和可审计的生产服务。**

Datamind 聚焦模型从制品到在线服务的交付链路：

```text
Model → Version → Deployment → Routing → Runtime
```

## 核心能力

- **模型与版本管理**：统一管理模型、版本、制品和生命周期。
- **部署与路由**：支持全量、金丝雀和影子发布，并通过路由控制请求流量。
- **在线与批量推理**：提供统一 Runtime Service，并支持批量预测任务。
- **分类与评分**：同时支持通用分类模型和信用评分卡。
- **实验管理**：支持 A/B 实验、实验分组、流量分配和效果分析。
- **生产治理**：提供认证、权限、审计、健康检查和运行状态管理。
- **模型存储**：支持本地文件系统和 MinIO。

Datamind 输出模型预测结果，不承担授信审批、额度策略或其他业务决策。

## 安装

安装 scikit-learn 与评分卡支持：

```bash
python -m pip install "pydatamind[sklearn]"
```

安装全部模型框架：

```bash
python -m pip install "pydatamind[full]"
```

确认 CLI：

```bash
datamind --version
datamind --help
```

下一步请阅读：

- [安装](getting-started/installation.md)
- [快速上手](getting-started/quickstart.md)
- [架构](concepts/architecture.md)
- [Docker 部署](deployment/docker.md)

!!! note "包名与入口"

    PyPI distribution 名称为 `pydatamind`，Python 导入名和 CLI 入口均为 `datamind`。
