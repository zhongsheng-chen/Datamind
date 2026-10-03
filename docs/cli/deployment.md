# 部署管理

相关说明见[对应文档](../deployment/full.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind deployment create

创建部署.

全量发布自动使用 champion，影子发布自动使用 shadow；
金丝雀发布需要通过 --role 指定 champion 或 challenger。

权限：`deployment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/create.py)

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

输入校验：

- 金丝雀发布必须指定 --role：champion 或 challenger
- 全量发布自动使用 champion，无需指定 --role
- 影子发布自动使用 shadow，无需指定 --role
- 必须提供 <name> 或 --model-id
- <name> 与 --model-id 只能指定一个
- --version 与 --version-id 只能指定一个
- --format 只支持 text 或 json

## datamind deployment enable

启用部署并启动运行实例。

权限：`deployment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/enable.py)

```text
datamind deployment enable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind deployment disable

停用部署并停止运行实例。

权限：`deployment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/disable.py)

```text
datamind deployment disable <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind deployment delete

逻辑删除已停用且已卸载的部署。

权限：`deployment.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/delete.py)

```text
datamind deployment delete <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind deployment restore

恢复逻辑删除的部署。

权限：`deployment.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/restore.py)

```text
datamind deployment restore <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind deployment list

列出部署。

权限：`deployment.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/list.py)

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
| `--limit` | 整数 | 否 | `10` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json
- --limit 必须大于 0
- --offset 不能小于 0

## datamind deployment show

查看部署详情。

权限：`deployment.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/deployment/show.py)

```text
datamind deployment show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除部署 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

输出对象字段：`created_at`、`deleted_at`、`deleted_by`、`deletion_reason`、`deployed_by`、`deployment_id`、`description`、`effective_from`、`effective_to`、`environment`、`framework`、`model_id`、`role`、`rollout_type`、`status`、`threshold`、`updated_at`、`version_id`。
