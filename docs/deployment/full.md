# 全量发布

全量发布由一个正式版本承接全部主预测流量，适合首次上线或直接切换模型版本。部署的发布类型为 `full`，角色自动设为 `champion`，路由流量比例必须为 `1`。

## 首次发布

按[快速上手](../getting-started/quickstart.md#步骤-1训练并注册模型)训练、注册并激活评分卡示例模型，再创建全量部署：

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout full
```

复制命令输出中的部署 ID，替换后续命令中的 `<deployment_id>`，然后启用部署并创建路由：

```bash
datamind deployment enable <deployment_id>
datamind route create <deployment_id> \
  --name scorecard-demo-main \
  --traffic-ratio 1 \
  --enabled
```

部署创建后默认停用，路由创建后默认不启用。上述命令通过 `deployment enable` 和 `--enabled` 启用两者。

按[快速上手](../getting-started/quickstart.md#步骤-4启动服务)启动预测服务与管理控制台。若服务已启动，可直接检查加载状态：

```bash
datamind runtime list
```

确认对应部署的运行实例状态为 `running` 后，按[在线预测](../guides/online-prediction.md)调用模型。通过响应中的 `request_id` 在管理控制台查看主执行记录，确认使用的部署与模型版本。

## 版本切换

1. 注册并激活新版本，创建全量部署，保持停用状态。
2. 确认模型文件可访问且部署配置正确，启用新部署，等待对应运行实例状态变为 `running`。
3. 在预测请求中指定新部署的 `deployment_id`，验证预测结果及主执行记录中的版本。
4. 为新部署创建流量比例为 `1` 的路由，保持不启用状态。禁用旧主路由，再启用新路由。同一模型、同一环境下，两条全量主路由不能同时启用，否则会超出流量预算。
5. 验证未指定 `deployment_id` 的请求使用新版本，记录新旧路由、部署 ID 和切换时间，再停用旧部署。

禁用旧路由与启用新路由是两次独立操作。两次操作之间，普通路由未匹配的请求可能回退到默认部署。需要逐步切换流量时，请使用[金丝雀发布](canary.md)。若同一模型、同一环境存在运行中的 A/B 实验，应先暂停或结束实验，再验证普通路由的切换结果。

## 回滚

保留旧版本及其模型文件，以便恢复旧版本：

1. 确认旧部署已启用，对应运行实例状态为 `running`。若旧部署已停用，先启用并等待加载完成。
2. 指定旧部署的 `deployment_id` 发起预测，验证结果。
3. 禁用新主路由，再启用旧主路由。
4. 发起未指定 `deployment_id` 的预测请求，确认主执行记录使用旧版本。

路由回滚不会改写历史请求或实验结果。

## 下线

1. 禁用并删除关联路由。
2. 停用部署，等待运行实例完成模型卸载后删除部署。
3. 确认版本不再被其他部署使用，再停用或删除版本。

删除前须满足关联限制，详见[状态与权限](../reference/states-permissions.md)。
