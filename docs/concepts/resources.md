# 资源与生命周期

同一个模型可以有多个版本，同一个版本可以产生多个制品修订，并部署到不同环境。区分这些资源，可以避免把模型激活、部署启用和运行时加载视为同一操作。

## 资源关系

| 资源 | 含义 | 关联 |
| --- | --- | --- |
| Model | 模型名称、框架和任务元数据 | 包含多个 Version |
| Version | 模型的业务版本 | 指向当前 Artifact 修订 |
| Artifact | 注册制品的独立修订与存储记录 | 隶属 Version |
| Deployment | 指定版本在某个环境的部署配置 | 关联 Model 与 Version |
| Routing | 部署的流量比例、规则和生效时间 | 关联 Deployment |
| Runtime | Worker 的实际运行状态 | 反映 Deployment 的执行情况 |
| Experiment / Variant | 实验及其 Control、Treatment 分组 | Variant 绑定 Deployment |

## 状态边界

模型和版本激活后，仍需创建并启用 Deployment。Routing 也有独立的启用状态和时间范围。Runtime 的目标状态与各 Worker 的实际状态通过协调机制同步，不能仅凭部署状态判断模型已经加载。

状态取值见[状态与权限](../reference/states-permissions.md)，操作顺序见[快速上手](../getting-started/quickstart.md)。

## 版本与制品修订

Version 的业务版本号和 Artifact 的修订号分别管理。注册服务负责制品校验和当前制品投影更新。相同版本再次提交制品的校验、幂等与更新边界见[模型与版本](../models/index.md)。
