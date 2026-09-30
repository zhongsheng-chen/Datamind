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
- **分类与评分**：同时支持通用分类模型和申请评分模型。
- **实验管理**：支持 A/B 实验、实验分组、流量分配和效果分析。
- **生产治理**：提供认证、权限、审计、健康检查和运行状态管理。
- **模型存储**：支持本地文件系统和 MinIO。

Datamind 输出模型预测结果，不承担授信审批、额度策略或其他业务决策。

## 按任务阅读

| 目标 | 入口 |
| --- | --- |
| 第一次使用 | [安装](getting-started/installation.md)、[配置与初始化](getting-started/configuration.md)、[快速上手](getting-started/quickstart.md) |
| 理解平台资源 | [架构](concepts/architecture.md)、[资源与生命周期](concepts/resources.md) |
| 准备模型制品 | [模型与版本](models/index.md)、[兼容性](models/compatibility.md) |
| 发布与运行 | [部署](deployment/index.md)、[流量管理](routing/index.md) |
| 评估模型效果 | [A/B 测试](experiments/index.md)、[Outcome](experiments/outcomes.md) |
| 接入预测与管理界面 | [在线预测](guides/online-prediction.md)、[批量预测](guides/batch-prediction.md)、[Console](guides/console.md) |
| 查命令与字段 | [CLI Reference](cli/index.md)、[配置](reference/configuration.md)、[Runtime API](reference/runtime-api.md) |
| 参与开发 | [开发环境](development/index.md)、[测试](development/testing.md)、[Release](development/release.md) |

## 文档范围

本站按任务指南、概念和 Reference 组织正式文档，内容依据当前代码、配置与测试核对。正在完善的章节及核对依据见[文档实施计划](development/documentation.md)。

!!! note "包名与入口"

    PyPI distribution 名称为 `pydatamind`，Python 导入名和 CLI 入口均为 `datamind`。
