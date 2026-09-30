# Deployment 与 Runtime

Deployment 记录某个模型版本在指定环境中的发布配置，Routing 决定请求如何到达 Deployment，Runtime 负责加载模型并执行预测。

## 从配置到执行

1. 注册并激活模型版本。
2. 创建 Deployment，选择发布方式。
3. 启用 Deployment，配置并启用 Routing。
4. 启动 Runtime，检查实际运行状态。
5. 发起预测并核对命中的部署与版本。

完整命令见[快速上手](../getting-started/quickstart.md)。

## 发布方式

| 发布方式 | 部署角色 | 适用场景 |
| --- | --- | --- |
| [full](full.md) | 自动选择 champion | 全量提供主预测结果 |
| [canary](canary.md) | 显式选择 champion 或 challenger | 新旧版本按流量比例共同服务 |
| [shadow](shadow.md) | 自动选择 shadow | 旁路执行并保留主预测结果 |

`rollout_type` 表示发布方式，Deployment 的 `role` 表示部署角色。创建 Routing 时会将部署角色写入 `rollout_group`。

## 进程与基础设施

Runtime 与任务 Worker 是不同进程，Console 提供管理界面。进程入口见[Runtime 与 Worker](processes.md)，容器组合见[Docker](docker.md)。
