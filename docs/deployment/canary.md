# 金丝雀发布

`canary` 用于渐进放量。创建部署（`Deployment`）必须显式选择 `champion` 或 `challenger`，比例设置在路由（`Routing`）上。主、副路由分别绑定不同部署，角色本身不决定比例。

## 准备主版本和候选版本

先完成[快速上手](../getting-started/quickstart.md)，注册并激活 `scorecard-demo` 1.0.0。按[训练示例](../examples/index.md)生成候选制品 `scorecard_demo_v2.pkl`，然后注册并激活候选版本：

```bash
datamind model register scorecard-demo \
  --version 1.1.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2.pkl \
  --framework sklearn --model-type logistic_regression --task-type scoring
datamind model activate scorecard-demo --version 1.1.0
```

对两个版本分别创建金丝雀部署：

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout canary --role champion
datamind deployment create scorecard-demo --version 1.1.0 --rollout canary --role challenger
datamind deployment enable <champion_deployment_id>
datamind deployment enable <challenger_deployment_id>
datamind runtime list --format json
```

已有 `full` 主路由时先禁用该路由，避免与 `canary` 路由共同超出流量预算。等待两个部署实际加载，再创建路由：

```bash
datamind route create <champion_deployment_id> \
  --name scorecard-demo-main --traffic-ratio 0.8 --enabled
datamind route create <challenger_deployment_id> \
  --name scorecard-demo-secondary --traffic-ratio 0.2 --enabled
```

复制返回的两个路由 ID。使用不同 `subject_key` 发起请求，并在 Console 的请求与执行记录中核对命中的版本。有限样本不保证严格 80/20，稳定主体也不会在重复请求间随机切换。

## 放量与回滚

从 80/20 改为 50/50 时，先减少主路由，再增加候选路由：

```bash
datamind route update <main_routing_id> --traffic-ratio 0.5
datamind route update <secondary_routing_id> --traffic-ratio 0.5
```

两次操作之间剩余流量可能走默认部署回退，详见[路由优先级](../routing/index.md)。不能先增加候选比例到 0.5，否则启用主路由比例合计 1.3，更新会被拒绝。继续放量也遵循先减少一侧、再增加另一侧的顺序。

回滚到主版本：

```bash
datamind route disable <secondary_routing_id>
datamind route update <main_routing_id> --traffic-ratio 1
```

完成全量切换前保留主版本制品与可加载部署。切换成功后再删除旧路由、停用旧部署并等待卸载。需要将候选作为新的 `champion` 时创建合适角色的新部署，部署创建时的角色不是路由更新参数。

## 与实验和影子的关系

运行中的实验优先于普通路由。评估纯 `canary` 比例前暂停或结束同模型、同环境的实验，显式指定 `deployment_id` 的请求也不会按普通路由分流。A/B 还记录实验分配（`Assignment`）和后验业务结果（`Outcome`），见[实验流程](../experiments/index.md)。影子路由独立执行，不占主路由预算，见[影子发布](shadow.md)。
