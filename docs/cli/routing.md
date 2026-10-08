# 路由管理

相关说明见[对应文档](../routing/rules.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind route create

创建路由规则.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`routing.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/create.py)

```text
datamind route create <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--name` | 字符串 | 是 | `—` | 路由名称 |
| `--traffic-ratio` | 数值 | 是 | `—` | 路由流量比例，范围 0~1 |
| `--rules-file` | 字符串 | 否 | `null` | 路由规则文件(JSON) |
| `--description` | 字符串 | 否 | `null` | 路由描述 |
| `--effective-from` | 字符串 | 否 | `null` | 生效时间。默认不设置 |
| `--effective-to` | 字符串 | 否 | `null` | 失效时间。默认不设置 |
| `--enabled/--disabled` | 布尔 | 否 | `false` | 是否启用路由 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --name 不能为空
- --name 不能超过 128 个字符
- --format 只支持 text 或 json
- --traffic-ratio 必须在 0 到 1 之间
- --effective-to 必须晚于 --effective-from
- 生效时间格式无效，请使用 YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式
- --rules-file 必须是 JSON 对象

## datamind route list

列出路由规则。

权限：`routing.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/list.py)

```text
datamind route list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--name` | 字符串 | 否 | `null` | 按路由名称过滤 |
| `--deployment-id` | 字符串 | 否 | `null` | 按部署 ID 过滤 |
| `--rollout` | 字符串 | 否 | `null` | 按发布方式过滤，可选值：full / canary / shadow |
| `--group/--rollout-group` | 字符串 | 否 | `null` | 按发布分组过滤，可选值：champion / challenger |
| `--enabled/--disabled` | 布尔 | 否 | `null` | 按是否启用过滤 |
| `--created-by` | 字符串 | 否 | `null` | 按创建人过滤 |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除路由 |
| `--limit` | 整数 | 否 | `10` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json
- --limit 必须大于 0
- --offset 不能小于 0

## datamind route show

查看路由规则详情。

权限：`routing.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/show.py)

```text
datamind route show <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除路由 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json

## datamind route enable

启用路由规则。

权限：`routing.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/enable.py)

```text
datamind route enable <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json

## datamind route disable

禁用路由规则。

权限：`routing.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/disable.py)

```text
datamind route disable <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json

## datamind route update

更新路由规则.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`routing.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/update.py)

```text
datamind route update <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--name` | 字符串 | 否 | `null` | 路由名称 |
| `--traffic-ratio` | 数值 | 否 | `null` | 路由流量比例，范围 0~1 |
| `--rules-file` | 字符串 | 否 | `null` | 路由规则文件(JSON) |
| `--description` | 字符串 | 否 | `null` | 路由描述 |
| `--effective-from` | 字符串 | 否 | `null` | 生效时间 |
| `--effective-to` | 字符串 | 否 | `null` | 失效时间 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json
- --traffic-ratio 必须在 0 到 1 之间
- 至少需要提供一个更新参数
- --name 不能为空
- --name 不能超过 128 个字符
- --rules-file 必须是 JSON 对象
- --effective-to 必须晚于 --effective-from
- 生效时间格式无效，请使用 YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式

## datamind route delete

逻辑删除已禁用的路由规则。

权限：`routing.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/delete.py)

```text
datamind route delete <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json

## datamind route restore

恢复逻辑删除的路由规则。

权限：`routing.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/route/restore.py)

```text
datamind route restore <routing_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<routing_id>` | 字符串 | 是 | `—` | 路由 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验（命令函数内的显式检查）：

- --format 只支持 text 或 json
