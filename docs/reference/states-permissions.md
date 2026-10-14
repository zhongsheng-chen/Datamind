# 状态与权限

执行资源操作时，需要同时满足状态约束和权限要求。本页列出资源的状态转换、运行与执行状态，以及各项操作使用的权限。

## 资源生命周期

| 资源                  | 允许的转换                                                                                                                                                                                       |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 模型（`Model`）       | `active` → `inactive` / `deprecated`；`inactive` → `active` / `deprecated` / `archived`；`deprecated` → `archived`                                                                               |
| 版本（`Version`）     | `active` → `inactive` / `deprecated`；`inactive` → `active` / `deprecated` / `archived`；`deprecated` → `archived`                                                                               |
| 部署（`Deployment`）  | `inactive` ↔ `active`                                                                                                                                                                            |
| 实验（`Experiment`）  | `draft` → `running` / `archived`；`running` → `paused` / `stopped` / `completed` / `archived`；`paused` → `running` / `stopped` / `completed` / `archived`；`stopped` / `completed` → `archived` |
| 实验分组（`Variant`） | `active` ↔ `inactive`；`active` / `inactive` → `archived`                                                                                                                                        |

资源归档后，生命周期结束，不再支持上表中的状态转换。执行操作还需满足关联资源的约束：

- 版本存在有效部署时，不能停用或删除。
- 删除部署前，需先停用，并等待运行实例完成卸载。
- 实验分组只能绑定同一模型在同一环境中的可用部署，且部署的发布类型不能为 `shadow`。

具体操作步骤见[模型管理](../models/index.md)、[部署管理](../deployment/index.md)和[实验分析](../experiments/analysis.md)。

逻辑删除通过 `deleted_at` 标记，与资源的业务状态分别管理。恢复后的状态取决于资源类型：模型、版本和部署设为 `inactive`，路由设为禁用，实验及其分组保留删除前的状态。

## 运行与执行状态

| 对象                      | 状态                                                                                                     |
|---------------------------|----------------------------------------------------------------------------------------------------------|
| 运行实例（`Runtime`）     | `starting`、`running`、`stopping`、`stopped`、`failed`                                                   |
| 运行控制目标（`Control`） | `loaded`、`unloaded`                                                                                     |
| 执行记录（`Execution`）   | `queued`、`running`、`success`、`failed`、`timeout`、`cancelled`                                         |
| 批次（`Batch`）           | `queued`、`running`、`retrying`、`cancelling`、`succeeded`、`partially_succeeded`、`failed`、`cancelled` |

运行控制通过 `Control.desired_status` 指定各 Worker 的加载目标，实际执行进度由运行实例状态反映。目标设为 `loaded` 或 `unloaded` 后，Worker 仍需完成相应的加载或卸载操作；重新加载则通过递增 `generation` 触发。

查询运行实例时，系统根据心跳报告健康状态：`healthy`、`unhealthy` 或 `unknown`。运行状态描述实例的运行阶段，健康状态用于判断实例当前是否正常。

## 发布与决策枚举

| 枚举                             | 取值                                                      |
|----------------------------------|-----------------------------------------------------------|
| 发布类型（`RolloutType`）        | `full`、`canary`、`shadow`                                |
| 部署角色（`DeploymentRole`）     | `champion`、`challenger`、`shadow`                        |
| 分配策略（`AssignmentStrategy`） | `hash`、`manual`                                          |
| 决策策略（`DecisionStrategy`）   | `experiment`、`routing`、`deployment`、`shadow`、`manual` |
| 决策结果（`DecisionResult`）     | `approve`、`reject`                                       |
| 执行类型（`ExecutionType`）      | `primary`、`shadow`                                       |

部署角色用于标识部署在发布中的作用，具体流量分配由[路由配置](../routing/index.md)决定。主、副及影子路由的配置方式见[流量分配](../routing/index.md)。

## 权限全集

| 权限                                                         | 用途                                             |
|--------------------------------------------------------------|--------------------------------------------------|
| `model.read` / `model.write` / `model.delete`                | 查询；注册、激活、停用、恢复；删除与永久清理     |
| `deployment.read` / `deployment.write` / `deployment.delete` | 查询；创建、启停；删除与恢复                     |
| `routing.read` / `routing.write` / `routing.delete`          | 查询；创建、更新、启停；删除与恢复               |
| `experiment.read` / `experiment.write` / `experiment.delete` | 查询和分析；实验与分组配置、生命周期；删除与恢复 |
| `identity.read` / `identity.manage`                          | 查询用户角色；账户和授权管理                     |
| `runtime.read` / `runtime.manage`                            | 查询实际运行；重新加载启用中的部署               |
| `prediction.invoke`                                          | 在线、批量预测以及批次查询、取消、重试           |
| `request.read`                                               | 查看请求、决策和执行记录                         |
| `audit.read`                                                 | 查看审计记录                                     |
| `data.export`                                                | 导出数据                                         |

角色可授予上表中的具体权限，也可使用命名空间通配符（如 `model.*`）或全局通配符 `*`。内置 `administrator` 角色通过 `*` 获得全部权限。授权时仅接受已定义的权限及其命名空间。
