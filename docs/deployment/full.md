# 全量发布

全量发布使用 `rollout_type=full`，角色自动为 `champion`。它适合首次交付或单一正式版本承接流量。启用 full 路由时比例必须为 1。

## 首次发布

按[快速上手](../getting-started/quickstart.md)训练、注册并激活申请评分模型。在获得各步骤返回的 ID 后执行：

```bash
datamind deployment create application-scorecard --version 1.0.0 --rollout full
datamind deployment enable <deployment_id>
datamind route create <deployment_id> \
  --name application-scorecard-main --traffic-ratio 1 --enabled
datamind runtime list --format json
```

创建 Deployment 默认 inactive，创建 Routing 默认不启用。以上明确开启两者。确认 Runtime 实际加载后，按[在线预测](../guides/online-prediction.md)调用模型并核对响应及请求记录中的版本。

## 版本切换

先注册并激活新版本，创建新的 inactive full 部署。验证制品与部署条件，启用新部署并等待加载完成。可指定其 deployment_id 做定向验证。然后禁用旧主路由，启用新部署比例为 1 的路由。两条 full 主路由不能同时启用，否则超出总流量预算。

路由切换由多条管理操作组成，不是跨命令原子事务。新路由生效前仍存在默认部署回退，因此有连续交付要求时优先使用[canary](canary.md)完成渐进切换。记录新旧路由、部署 ID 和操作时间，检查实际主预测版本后再停用旧部署。

## 回滚与下线

保留旧版本与制品，在回滚时先确保旧部署可加载，再禁用新路由、启用旧路由，检查预测与请求记录。旧部署已经停用时先启用并确认加载。路由回滚不会改写历史请求或实验结果。

下线时依次禁用并删除路由，停用 Deployment，等待运行节点卸载后删除 Deployment，最后停用或删除版本。关联限制见[状态与权限](../reference/states-permissions.md)。
