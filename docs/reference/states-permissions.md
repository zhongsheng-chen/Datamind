# 状态与权限

资源状态决定允许的生命周期操作，权限决定用户能否执行这些操作。删除标记 `deleted_at` 独立于业务状态，恢复后需按原有状态继续管理。

## 生命周期

| 资源 | 允许的转换或状态 |
| --- | --- |
| Model / Version | active → inactive / deprecated；inactive → active / deprecated / archived；deprecated → archived；archived 为终态 |
| Deployment | inactive ↔ active |
| Experiment | draft → running / archived；running → paused / stopped / completed / archived；paused → running / stopped / completed / archived；stopped / completed → archived；archived 为终态 |
| Variant | active ↔ inactive；active / inactive → archived；archived 不能重新启用 |
| Artifact | active、retired、purge_pending、purged、purge_failed；替换当前修订后保留历史，永久清理记录清理结果 |
| Runtime 实际状态 | starting、running、stopping、stopped、failed |
| 运行控制目标 | loaded / unloaded；reload 增加 generation |
| Execution | queued、running、success、failed、timeout、cancelled |
| Batch | queued、running、retrying、cancelling、succeeded、partially_succeeded、failed、cancelled |

这些转换不绕过关联校验。例如有效部署阻止版本停用或删除。删除部署之前需要停用并等待运行节点卸载。实验分组绑定的部署必须属于同一模型、环境且可用，不能是 shadow。各资源的[模型](../models/index.md)、[部署](../deployment/index.md)和[实验](../experiments/analysis.md)指南说明操作顺序。

## 发布与决策枚举

| 字段 | 取值 |
| --- | --- |
| rollout_type | full、canary、shadow |
| deployment role | champion、challenger、shadow |
| assignment strategy | hash、manual |
| decision strategy | experiment、routing、deployment、shadow、manual |
| decision result | approve、reject |
| execution type | primary、shadow |

`champion` 和 `challenger` 是部署角色。它们不自动创建路由或设置比例。主、副、影子路由的配置见[流量管理](../routing/index.md)。

## 权限全集

| 权限 | 用途 |
| --- | --- |
| model.read / write / delete | 查询；注册、激活、停用、恢复；删除与永久清理 |
| deployment.read / write / delete | 查询；创建、启停；删除与恢复 |
| routing.read / write / delete | 查询；创建、更新、启停；删除与恢复 |
| experiment.read / write / delete | 查询和分析；实验与分组配置、生命周期；删除与恢复 |
| identity.read / manage | 查询用户角色；账户和授权管理 |
| runtime.read / manage | 查询实际运行；加载、卸载与重载控制 |
| prediction.invoke | 在线、批量预测以及批次查询、取消、重试 |
| outcome.write | 回流业务结果 |
| request.read | 查看请求、决策和执行记录 |
| audit.read | 查看审计记录 |
| data.export | 导出数据 |

上表共 21 个具体权限，来源为 `datamind/constants/permissions.py`。内置 administrator 使用 `*`。权限判断支持精确匹配、全局 `*` 与命名空间通配（如 `model.*`）。授予角色时仍须遵守身份服务对可配置权限的校验，通常使用表中的具体权限。

不同命令的权限不能从动词猜测，例如 Deployment 的 restore 使用 `deployment.delete`。逐命令要求见[CLI Reference](../cli/index.md)，接口要求见[Runtime API](runtime-api.md)。Console 按权限显示按钮，前端动作名不是可直接授予的后端权限。服务端仍会校验权限。
