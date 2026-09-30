# 服务与运行状态 CLI

任务步骤见[使用指南](../deployment/processes.md)。本页列出当前命令、全部显式参数、默认值、权限和入口校验；服务层的状态转换见[状态与权限](../reference/states-permissions.md)。

位置参数用大写表示；`null` 表示未指定。布尔开关默认关闭时，传入选项将其开启。重复选项和路径要求以类型/说明为准。所有命令还支持 `--help`。

## datamind service run

启动 Datamind 模型服务.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/service/run.py)。

```text
datamind service run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | text | 否 | `null` | 监听地址，默认 0.0.0.0 |
| `--port` | integer | 否 | `null` | 监听端口，默认 8700 |
| `--reload` | boolean | 否 | `false` | 代码变更后自动重载 |
| `--verbose` | boolean | 否 | `false` | 显示 BentoML 警告和信息日志 |

入口校验与错误：

- DATAMIND_SERVICE_ENVIRONMENT 不能为空
- --host 不能为空
- --port 必须在 1 到 65535 之间

## datamind runtime list

查询部署运行状态列表.

权限：`runtime.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/list.py)。

```text
datamind runtime list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--desired-status` | text | 否 | `null` | 按期望运行状态过滤，可选值：loaded / unloaded |
| `--limit` | integer | 否 | `10` | 返回记录数量限制 |
| `--offset` | integer | 否 | `0` | 分页偏移量 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json
- --desired-status 只支持 loaded 或 unloaded
- --limit 必须大于 0
- --offset 不能小于 0

## datamind runtime show

查看部署运行状态.

权限：`runtime.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/show.py)。

```text
datamind runtime show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind console run

启动管理控制台.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/console/run.py)。

```text
datamind console run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | text | 否 | `null` | 监听地址，默认 127.0.0.1 |
| `--port` | integer | 否 | `null` | 监听端口，默认 8701 |
| `--startup-timeout` | integer range | 否 | `null` | 等待控制台就绪的最长时间（秒），默认 120 |
| `--reload` | boolean | 否 | `false` | 代码变更时自动重载 |
| `--verbose` | boolean | 否 | `false` | 显示 BentoML 警告和信息日志 |

入口校验与错误：

- --host 不能为空
- --port 必须在 1 到 65535 之间
