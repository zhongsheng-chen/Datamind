# Routing 与流量分配

Routing 将部署的发布方式、角色、流量比例和请求匹配规则组合成路由配置。

## 配置字段

| 字段 | 含义 |
| --- | --- |
| `deployment_id` | 路由关联的部署 |
| `rollout_type` | 创建时来自 Deployment 的发布方式 |
| `rollout_group` | 创建时来自 Deployment 的角色 |
| `traffic_ratio` | 路由流量比例，范围 0～1 |
| `enabled` | 是否启用，CLI 创建默认关闭 |
| `rules` | 请求匹配条件 |
| `effective_from` / `effective_to` | 生效与失效时间 |

## Runtime 选择顺序

当前路由器依次处理：请求显式指定的 Deployment、运行中的 Experiment、匹配的启用 Routing、默认活跃部署。显式指定 Deployment 仍需通过部署校验。

普通 Routing 的 `traffic_ratio` 与 Experiment 的 `traffic_ratio`、Variant 的 `weight` 分别属于不同配置层。实验分流说明见[Assignment](../experiments/assignment.md)。

## 比例校验与回退

启用主路由的比例在 0～1 之间，同一模型、同一环境的总比例不能超过 1。full 部署的比例必须为 1；shadow 路由不消耗主路由预算。每个部署只允许一条未删除路由。Runtime 按以下顺序选主部署：显式 deployment_id → 运行中的实验 → 满足条件的普通路由 → 默认活跃部署。默认回退优先 champion，其次其他可用非影子部署；没有可用部署时返回路由错误。

普通路由对稳定主体进行哈希分配，候选路由按 ID 排序后使用比例区间；总比例小于 1 时不重新归一化，剩余流量进入默认部署回退。因此把路由比例改为 0 或禁用路由并不等于拒绝所有该模型请求。显式指定部署仍须通过模型、环境、状态和生效时间校验。

主路由确定后独立计算影子路由，排除同一个主 deployment_id。影子执行不会改变主结果。规则和时间见[路由规则](rules.md)。

条件与时间设置见[路由规则](rules.md)，发布操作见[部署](../deployment/index.md)。

## 申请评分的主、副与影子路由

控制台演示为同一个 `application-scorecard` 配置三条路由：

| 路由 | 版本 | 部署类型与角色 | 比例 |
| --- | --- | --- | --- |
| `application-scorecard-main` | 1.0.0 | canary / Champion | 0.8 |
| `application-scorecard-secondary` | 1.1.0 | canary / Challenger | 0.2 |
| `application-scorecard-shadow` | 1.1.0 | shadow / Shadow | 1 |

“主”和“副”是本例的命名，表示两条普通流量路由，不表示故障转移。影子路由使用相同输入旁路执行。为三个已启用的部署分别执行：

```bash
datamind route create <champion_deployment_id> \
  --name application-scorecard-main --traffic-ratio 0.8 --enabled
datamind route create <challenger_deployment_id> \
  --name application-scorecard-secondary --traffic-ratio 0.2 --enabled
datamind route create <shadow_deployment_id> \
  --name application-scorecard-shadow --traffic-ratio 1 --enabled
```

首次仅需单版本服务时，可以使用快速上手的 full 部署与 100% 路由。需要增加副路由时，应先停用原 full 路由和部署，再创建上述 canary 主部署；full 路由的比例不能直接改为 0.8。

实验运行时，未进入实验的请求继续按普通路由分配；实验流量由 Variant 绑定选择部署。实际配置和记录见[Console 手册](../guides/console.md)。
