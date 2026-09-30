# 部署

部署将一个模型版本发布到指定环境。发布前激活版本，发布后检查 Runtime 的加载状态，再通过路由接入流量。

## 选择发布方式

| 方式 | 适用场景 | 部署角色 |
| --- | --- | --- |
| [全量](full.md) | 单一正式版本提供预测 | champion |
| [金丝雀](canary.md) | 新旧版本共同服务，逐步调整比例 | champion / challenger |
| [影子](shadow.md) | 使用真实输入旁路验证候选版本 | shadow |

发布方式使用 rollout_type 表示，角色使用 role 表示。full 和 shadow 自动确定角色，canary 在创建时选择角色。比例在路由上配置。

## 发布流程

1. 注册并激活目标版本。
2. 创建并启用部署。
3. 确认 Runtime 已加载模型。
4. 创建并启用路由，发起预测。
5. 在请求与执行记录中确认命中的版本。

首次发布的完整命令见[快速上手](../getting-started/quickstart.md)。

## 运行进程

Runtime 执行在线预测，任务 Worker 执行批量和影子预测，Console 提供管理界面。启动入口见[Runtime 与 Worker](processes.md)，容器运行见[Docker](docker.md)，共享存储与运维见[生产部署](production.md)。
