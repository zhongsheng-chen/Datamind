# 部署管理

操作流程见[部署与运行](../deployment/index.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

## datamind deployment create

创建部署。

创建部署时，全量发布自动设置角色为 champion，影子发布自动设置为 shadow，
金丝雀发布需通过 --role 指定 champion 或 challenger。

```text
datamind deployment create [<name>] [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 否 | `null` | 模型名称 |
| `--model-id` | 字符串 | 否 | `null` | 模型 ID |
| `--version` | 字符串 | 否 | `null` | 模型版本号 |
| `--version-id` | 字符串 | 否 | `null` | 版本 ID |
| `--rollout` | 字符串 | 否 | `"full"` | 发布方式，可选值：full / canary / shadow |
| `--role` | 字符串 | 否 | `null` | 金丝雀发布的部署角色：champion / challenger |
| `--threshold` | 数值 | 否 | `null` | 决策阈值 |
| `--description` | 字符串 | 否 | `null` | 部署描述 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

参数组合：

- `<name>` 与 `--model-id` 二选一，必须提供其中一个。
- `--version` 与 `--version-id` 只能指定一个。

权限：`deployment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/create.py)

## datamind deployment enable

启用部署。

启用后，运行实例将开始运行，已部署的模型将被加载。

启用部署不会自动将其设为默认部署。

```text
datamind deployment enable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/enable.py)

## datamind deployment set-default

设置默认部署。

默认部署必须是已启用且处于有效期内的 `champion`，设置后替换原默认部署。

```text
datamind deployment set-default <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/default.py)

## datamind deployment unset-default

取消默认部署。

取消后，该部署仍可通过路由或定向请求接收流量。

```text
datamind deployment unset-default <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/default.py)

## datamind deployment disable

停用部署。

停用后，运行实例将停止运行，已加载的模型将被卸载。

```text
datamind deployment disable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/disable.py)

## datamind deployment delete

逻辑删除已停用且已卸载的部署。

```text
datamind deployment delete <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/delete.py)

## datamind deployment restore

恢复逻辑删除的部署。

```text
datamind deployment restore <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/restore.py)

## datamind deployment list

列出部署。

```text
datamind deployment list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--model-id` | 字符串 | 否 | `null` | 按模型 ID 过滤 |
| `--version-id` | 字符串 | 否 | `null` | 按版本 ID 过滤 |
| `--framework` | 字符串 | 否 | `null` | 按模型框架过滤，可选值：sklearn / xgboost / lightgbm / catboost |
| `--rollout` | 字符串 | 否 | `null` | 按发布方式过滤，可选值：full / canary / shadow |
| `--role` | 字符串 | 否 | `null` | 按部署角色过滤，可选值：champion / challenger |
| `--status` | 字符串 | 否 | `null` | 按部署状态过滤，可选值：active / inactive |
| `--deployed-by` | 字符串 | 否 | `null` | 按部署人过滤 |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除部署 |
| `--limit` | 整数 | 否 | `10` | 返回记录数量限制。必须大于 0 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量。不能小于 0 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/list.py)

## datamind deployment show

查看部署详情。

```text
datamind deployment show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除部署 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`deployment.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/show.py)
