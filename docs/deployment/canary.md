# 金丝雀发布

金丝雀发布先将少量请求分配给候选版本，观察运行情况后逐步提高其流量比例。比例由用户调整，平台不会自动递增。创建部署（`Deployment`）必须显式选择 `champion` 或 `challenger`，比例设置在路由（`Routing`）上。主、副路由分别绑定不同部署，角色本身不决定比例。

## 前置条件

- 已完成[快速上手](../getting-started/quickstart.md)，主版本能够正常预测；
- 已按[模型训练示例](../examples/index.md)生成 1.1.0 候选版本模型文件；
- 当前账户具备 `model.write`、`deployment.write`、`routing.read`、`routing.write` 和 `runtime.read` 权限；
- 下文所有 `<..._id>` 均已替换为前一步输出的真实 ID。

## 准备主版本和候选版本

主版本 `scorecard-demo` 1.0.0 已由快速上手注册并激活。使用前置步骤生成的 `scorecard_demo_v2.pkl` 注册并激活候选版本：

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
datamind runtime list
```

确认两个新部署的运行实例状态均为 `running` 后，再切换路由。快速上手已经创建名为 `scorecard-demo-main` 的 `full` 路由。先查询它，将结果中的 `routing_id` 替换下方 `<quickstart_routing_id>` 后禁用，避免与 `canary` 路由共同超出流量预算：

```bash
datamind route list --name scorecard-demo-main
datamind route disable <quickstart_routing_id>
```

禁用只会停止路由分流，不会删除记录或释放名称，因此下面的金丝雀路由使用独立名称。创建并启用两条路由：

```bash
datamind route create <champion_deployment_id> \
  --name scorecard-demo-canary-champion --traffic-ratio 0.8 --enabled
datamind route create <challenger_deployment_id> \
  --name scorecard-demo-canary-challenger --traffic-ratio 0.2 --enabled
```

复制返回的两个路由 ID，后续分别替换 `<champion_routing_id>` 和 `<challenger_routing_id>`。使用不同 `subject_key` 发起请求，并在 Console 的请求与执行记录中核对命中的版本。有限样本不保证严格 80/20，稳定主体也不会在重复请求间随机切换。

## 调整比例与回滚

从 80/20 改为 50/50 时，先减少主路由，再增加候选路由：

```bash
datamind route update <champion_routing_id> --traffic-ratio 0.5
datamind route update <challenger_routing_id> --traffic-ratio 0.5
```

两次操作之间剩余流量可能走默认部署回退，详见[流量分配](../routing/index.md)。不能先增加候选比例到 0.5，否则启用主路由比例合计 1.3，更新会被拒绝。继续提高候选版本的流量比例时，也遵循先减少一侧、再增加另一侧的顺序。

回滚到主版本：

```bash
datamind route disable <challenger_routing_id>
datamind route update <champion_routing_id> --traffic-ratio 1
```

完成全量切换前，不要删除主版本的模型文件或部署，并确保主部署仍可重新加载。切换成功后再删除旧路由、停用旧部署并等待卸载。需要将候选作为新的 `champion` 时创建合适角色的新部署，部署创建时的角色不是路由更新参数。

## 验证与异常处理

每次调整比例后，使用多个不同 `subject_key` 发起预测，并从请求记录确认实际 `deployment_id` 和版本。重复同一主体只验证稳定性，不能用于观察总体比例。

更新被拒绝且提示总比例超过 1 时，先降低或禁用现有普通路由，再增加另一条路由。候选部署命中后预测失败时，立即将候选路由比例降为 0 或禁用，并检查候选部署的运行实例、模型文件和框架依赖。普通路由配置改变会重新划分区间，不保证主体永久粘滞；需要固定分组时使用实验。

## 与实验和影子的关系

运行中的实验优先于普通路由。评估纯 `canary` 比例前暂停或结束同模型、同环境的实验，显式指定 `deployment_id` 的请求也不会按普通路由分流。A/B 还记录实验分配（`Assignment`），并使用原始决策和主执行记录分析各组运行情况，见[实验流程](../experiments/index.md)。影子路由独立执行，不占主路由预算，见[影子发布](shadow.md)。
