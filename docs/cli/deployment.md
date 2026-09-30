# 部署管理 CLI

任务步骤见[使用指南](../deployment/index.md)。本页列出当前命令、全部显式参数、默认值、权限和入口校验；服务层的状态转换见[状态与权限](../reference/states-permissions.md)。

位置参数用大写表示；`null` 表示未指定。布尔开关默认关闭时，传入选项将其开启。重复选项和路径要求以类型/说明为准。所有命令还支持 `--help`。

## datamind deployment create

创建部署.

全量发布自动使用 champion，影子发布自动使用 shadow；
金丝雀发布需要通过 --role 指定 champion 或 challenger。

权限：`deployment.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/create.py)。

```text
datamind deployment create [<name>] [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | text | 否 | `null` | 模型名称 |
| `--model-id` | text | 否 | `null` | 模型 ID |
| `--version` | text | 否 | `null` | 模型版本号 |
| `--version-id` | text | 否 | `null` | 版本 ID |
| `--rollout` | text | 否 | `"full"` | 发布方式，可选值：full / canary / shadow |
| `--role` | text | 否 | `null` | 金丝雀发布的部署角色：champion / challenger |
| `--threshold` | float | 否 | `null` | 决策阈值 |
| `--description` | text | 否 | `null` | 部署描述 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- 金丝雀发布必须指定 --role：champion 或 challenger
- 全量发布自动使用 champion，无需指定 --role
- 影子发布自动使用 shadow，无需指定 --role
- 必须提供 <name> 或 --model-id
- <name> 与 --model-id 只能指定一个
- --version 与 --version-id 只能指定一个
- --format 只支持 text 或 json

## datamind deployment enable

启用部署并启动运行实例.

权限：`deployment.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/enable.py)。

```text
datamind deployment enable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind deployment disable

停用部署并停止运行实例.

权限：`deployment.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/disable.py)。

```text
datamind deployment disable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind deployment delete

逻辑删除已停用且已卸载的部署.

权限：`deployment.delete`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/delete.py)。

```text
datamind deployment delete <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--reason` | text | 否 | `null` | 删除原因 |
| `--yes` | boolean | 否 | `false` | 跳过确认 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind deployment restore

恢复逻辑删除的部署.

权限：`deployment.delete`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/restore.py)。

```text
datamind deployment restore <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind deployment list

列出部署.

权限：`deployment.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/list.py)。

```text
datamind deployment list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--model-id` | text | 否 | `null` | 按模型 ID 过滤 |
| `--version-id` | text | 否 | `null` | 按版本 ID 过滤 |
| `--framework` | text | 否 | `null` | 按模型框架过滤，可选值：sklearn / xgboost / lightgbm / catboost |
| `--rollout` | text | 否 | `null` | 按发布方式过滤，可选值：full / canary / shadow |
| `--role` | text | 否 | `null` | 按部署角色过滤，可选值：champion / challenger |
| `--status` | text | 否 | `null` | 按部署状态过滤，可选值：active / inactive |
| `--deployed-by` | text | 否 | `null` | 按部署人过滤 |
| `--include-deleted` | boolean | 否 | `false` | 包含已删除部署 |
| `--limit` | integer | 否 | `10` | 返回记录数量限制 |
| `--offset` | integer | 否 | `0` | 分页偏移量 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json
- --limit 必须大于 0
- --offset 不能小于 0

## datamind deployment show

查看部署详情.

权限：`deployment.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/show.py)。

```text
datamind deployment show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--include-deleted` | boolean | 否 | `false` | 包含已删除部署 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

输出对象字段：`created_at`、`deleted_at`、`deleted_by`、`deletion_reason`、`deployed_by`、`deployment_id`、`description`、`effective_from`、`effective_to`、`environment`、`framework`、`model_id`、`role`、`rollout_type`、`status`、`threshold`、`updated_at`、`version_id`。
