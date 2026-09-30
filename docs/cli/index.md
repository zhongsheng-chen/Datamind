# CLI Reference

按命令组查阅参数、默认值与权限。完整操作流程见各组对应指南，生命周期见[状态与权限](../reference/states-permissions.md)。

```bash
datamind --help
datamind --version
datamind <命令组> <命令> --help
```

`--help` 可离线查看。认证启用时，资源命令读取本地 CLI 登录凭据；服务启动和数据库迁移属于进程管理，不代替 HTTP 登录。

多数资源命令提供 `--format text/json`，默认值以各参数表为准。JSON 输出保留资源 ID、状态和业务字段；列表输出通常是 JSON 数组，分页参数控制本次返回范围，不保证返回总数或分页对象。日志可能独立写入 stderr/日志文件，自动化客户端应检查退出码并解析完整 JSON 值。失败时命令退出非零，不能仅根据控制台出现资源 ID 判断成功。

| 命令组 | 命令数量 |
| --- | --- |
| [初始化、认证与数据库](system.md) | 5 |
| [模型管理](model.md) | 9 |
| [部署管理](deployment.md) | 7 |
| [路由管理](routing.md) | 8 |
| [实验管理](experiment.md) | 12 |
| [实验分组](variant.md) | 9 |
| [业务结果回流](outcome.md) | 1 |
| [用户与角色](identity.md) | 15 |
| [服务与运行状态](processes.md) | 4 |

## JSON 输出约定

以下展示模型注册响应的关键字段（省略存储等字段）；资源 ID 是后续命令的输入，业务版本与制品修订分别保留：

```json
{"name":"scorecard-demo","model_id":"<model_id>","version":"1.0.0","version_id":"<version_id>","artifact_id":"<artifact_id>","artifact_revision":1,"action":"created"}
```

注册 `action` 为 `created`、`revised` 或 `unchanged`。模型 `list` 的 JSON 为数组，`show` 为对象；部署创建/查询保留 `deployment_id`、版本、环境、`rollout_type`、`role` 与 `status`；路由保留 `routing_id`、`deployment_id`、比例及启用状态；实验与分组保留各自 ID、状态和配置；业务结果输出包含原始决策归属。字段随资源命令而异，不能把某个示例当作所有命令的统一响应。

init、login、logout、whoami 和进程启动命令没有 --format 参数。用户创建与密码重置会交互读取密码，--format json 不会取消交互。自动化应先查看该命令是否具备无交互参数。

当前共 70 个叶子命令。新增或修改命令后运行 `python -m scripts.generate_docs_reference` 更新，使用 `--check` 检查文档与定义是否一致。
