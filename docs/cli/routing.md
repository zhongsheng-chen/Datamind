# 路由管理 CLI

任务步骤见[使用指南](../routing/index.md)。本页列出当前命令、全部显式参数、默认值、权限和入口校验；服务层的状态转换见[状态与权限](../reference/states-permissions.md)。

位置参数用大写表示；`null` 表示未指定。布尔开关默认关闭时，传入选项将其开启。重复选项和路径要求以类型/说明为准。所有命令还支持 `--help`。

## datamind route create

创建路由规则.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`routing.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/create.py)。

```text
datamind route create <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | text | 是 | `—` | 部署 ID |
| `--name` | text | 是 | `—` | 路由名称 |
| `--traffic-ratio` | float | 是 | `—` | 路由流量比例，范围 0~1 |
| `--rules-file` | text | 否 | `null` | 路由规则文件(JSON) |
| `--description` | text | 否 | `null` | 路由描述 |
| `--effective-from` | text | 否 | `null` | 生效时间。默认不设置 |
| `--effective-to` | text | 否 | `null` | 失效时间。默认不设置 |
| `--enabled/--disabled` | boolean | 否 | `false` | 是否启用路由 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --name 不能为空
- --name 不能超过 128 个字符
- --format 只支持 text 或 json
- --traffic-ratio 必须在 0 到 1 之间
- --effective-to 必须晚于 --effective-from
- 生效时间格式无效，请使用 YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式
- --rules-file 必须是 JSON 对象

## datamind route list

列出路由规则.

权限：`routing.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/list.py)。

```text
datamind route list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--name` | text | 否 | `null` | 按路由名称过滤 |
| `--deployment-id` | text | 否 | `null` | 按部署 ID 过滤 |
| `--rollout` | text | 否 | `null` | 按发布方式过滤，可选值：full / canary / shadow |
| `--group/--rollout-group` | text | 否 | `null` | 按发布分组过滤，可选值：champion / challenger |
| `--enabled/--disabled` | boolean | 否 | `null` | 按是否启用过滤 |
| `--created-by` | text | 否 | `null` | 按创建人过滤 |
| `--include-deleted` | boolean | 否 | `false` | 包含已删除路由 |
| `--limit` | integer | 否 | `10` | 返回记录数量限制 |
| `--offset` | integer | 否 | `0` | 分页偏移量 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json
- --limit 必须大于 0
- --offset 不能小于 0

## datamind route show

查看路由规则详情.

权限：`routing.read`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/show.py)。

```text
datamind route show <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--include-deleted` | boolean | 否 | `false` | 包含已删除路由 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind route enable

启用路由规则.

权限：`routing.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/enable.py)。

```text
datamind route enable <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind route disable

禁用路由规则.

权限：`routing.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/disable.py)。

```text
datamind route disable <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind route update

更新路由规则.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`routing.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/update.py)。

```text
datamind route update <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--name` | text | 否 | `null` | 路由名称 |
| `--traffic-ratio` | float | 否 | `null` | 路由流量比例，范围 0~1 |
| `--rules-file` | text | 否 | `null` | 路由规则文件(JSON) |
| `--description` | text | 否 | `null` | 路由描述 |
| `--effective-from` | text | 否 | `null` | 生效时间 |
| `--effective-to` | text | 否 | `null` | 失效时间 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json
- --traffic-ratio 必须在 0 到 1 之间
- 至少需要提供一个更新参数
- --name 不能为空
- --name 不能超过 128 个字符
- --rules-file 必须是 JSON 对象
- --effective-to 必须晚于 --effective-from
- 生效时间格式无效，请使用 YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式

## datamind route delete

逻辑删除已禁用的路由规则.

权限：`routing.delete`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/delete.py)。

```text
datamind route delete <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--reason` | text | 否 | `null` | 删除原因 |
| `--yes` | boolean | 否 | `false` | 跳过确认 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json

## datamind route restore

恢复逻辑删除的路由规则.

权限：`routing.delete`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/restore.py)。

```text
datamind route restore <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | text | 是 | `—` | 路由 ID |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --format 只支持 text 或 json
