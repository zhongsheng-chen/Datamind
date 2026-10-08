# 服务管理

相关说明见[对应文档](../deployment/processes.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind service run

启动 Datamind 模型服务。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/service/run.py)

```text
datamind service run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | 字符串 | 否 | `null` | 监听地址，默认 0.0.0.0 |
| `--port` | 整数 | 否 | `null` | 监听端口，默认 8700 |
| `--reload` | 布尔 | 否 | `false` | 代码变更后自动重载 |
| `--verbose` | 布尔 | 否 | `false` | 显示 BentoML 警告和信息日志 |

输入校验（命令函数内的显式检查）：

- DATAMIND_SERVICE_ENVIRONMENT 不能为空
- --host 不能为空
- --port 必须在 1 到 65535 之间

## datamind service healthcheck

检查预测服务是否就绪。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/service/healthcheck.py)

```text
datamind service healthcheck [OPTIONS]
```

无额外参数。


## datamind worker run

启动任务 Worker。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/worker/run.py)

```text
datamind worker run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--role` | all/batch/shadow | 否 | `null` | 处理的任务类型，默认使用配置值 |
| `--concurrency` | 整数范围 | 否 | `null` | Worker 并发数，默认使用配置值 |

## datamind worker healthcheck

检查任务 Worker 是否就绪。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/worker/healthcheck.py)

```text
datamind worker healthcheck [OPTIONS]
```

无额外参数。


## datamind runtime list

查询部署运行状态列表。

权限：`runtime.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/list.py)

```text
datamind runtime list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--desired-status` | 字符串 | 否 | `null` | 按期望运行状态过滤，可选值：loaded / unloaded |
| `--limit` | 整数 | 否 | `10` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json
- --desired-status 只支持 loaded 或 unloaded
- --limit 必须大于 0
- --offset 不能小于 0

## datamind runtime show

查看部署运行状态。

权限：`runtime.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/show.py)

```text
datamind runtime show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json

## datamind console run

启动管理控制台。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/console/run.py)

```text
datamind console run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | 字符串 | 否 | `null` | 监听地址，默认 127.0.0.1 |
| `--port` | 整数 | 否 | `null` | 监听端口，默认 8701 |
| `--startup-timeout` | 整数范围 | 否 | `null` | 等待控制台就绪的最长时间（秒），默认 120 |
| `--reload` | 布尔 | 否 | `false` | 代码变更时自动重载 |
| `--verbose` | 布尔 | 否 | `false` | 显示 BentoML 警告和信息日志 |

输入校验（命令函数内的显式检查）：

- --host 不能为空
- --port 必须在 1 到 65535 之间

## datamind console healthcheck

检查管理控制台是否就绪。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/console/healthcheck.py)

```text
datamind console healthcheck [OPTIONS]
```

无额外参数。
