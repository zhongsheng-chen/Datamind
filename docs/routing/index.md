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

## 请求如何选择部署

Runtime 按以下顺序选择主部署：

1. 请求中明确指定的 deployment_id。
2. 运行中的实验。
3. 满足条件的普通路由。
4. 默认活跃部署。

指定部署仍须满足模型、环境、状态和生效时间要求。默认回退优先选择 champion，再选择其他可用的非影子部署。没有可用部署时返回路由错误。

## 流量比例

同一模型、同一环境中，启用的普通路由比例之和不能超过 1。full 路由必须为 1，shadow 路由独立计算。每个部署只允许一条未删除路由。

普通路由对稳定主体进行哈希分配，按路由 ID 排序后划分比例区间。总比例小于 1 时，剩余请求走默认部署回退，比例不会重新归一化。因此，禁用路由或将比例改为 0 后，默认部署仍可能收到请求。

实验曝光比例和分组权重属于另一层配置，见[实验分配](../experiments/assignment.md)。主部署选定后，再独立计算影子路由，排除已经作为主目标的同一部署。

规则与时间设置见[路由规则](rules.md)，版本切换见[金丝雀发布](../deployment/canary.md)。

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

首次仅需单版本服务时，可以使用快速上手的 full 部署与 100% 路由。需要增加副路由时，应先停用原 full 路由和部署，再创建上述 canary 主部署。full 路由的比例不能直接改为 0.8。

实验运行时，未进入实验的请求继续按普通路由分配。实验流量由 Variant 绑定选择部署。实际配置和记录见[Console 手册](../guides/console.md)。
