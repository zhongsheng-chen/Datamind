# 实验管理 CLI

操作流程见[使用指南](../experiments/index.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind experiment create

创建实验.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/create.py)

```text
datamind experiment create [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--model-id` | 字符串 | 是 | `—` | 模型 ID |
| `--name` | 字符串 | 否 | `null` | 实验名称 |
| `--traffic-ratio` | 数值 | 否 | `1.0` | 实验流量比例；hash 策略取值范围为 (0, 1]，manual 策略不参与分配 |
| `--bucket-key` | 字符串 | 否 | `"customer_id"` | 分桶主体字段，例如 customer_id / order_id / application_id |
| `--strategy` | 字符串 | 否 | `"hash"` | 实验分配策略，可选值：hash / manual |
| `--description` | 字符串 | 否 | `null` | 实验描述 |
| `--effective-from` | 字符串 | 否 | `null` | 生效时间。默认在实验启动时确定 |
| `--effective-to` | 字符串 | 否 | `null` | 失效时间。默认不设置 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --traffic-ratio 必须在 0 到 1 之间
- hash 策略下 --traffic-ratio 必须大于 0
- --format 只支持 text 或 json
- --bucket-key 不能为空
- --effective-to 必须晚于 --effective-from
- --strategy 只支持 hash 或 manual
- 生效时间格式无效，请使用 YYYY-MM-DD HH:MM:SS 或带时区的 ISO 8601 格式

## datamind experiment update

更新实验.

时间格式：YYYY-MM-DD HH:MM:SS，可附加 ±HH:MM
时区偏移。未提供时区偏移时，按配置时区解析。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/update.py)

```text
datamind experiment update <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--name` | 字符串 | 否 | `null` | 实验名称 |
| `--strategy` | 字符串 | 否 | `null` | 实验分配策略，可选值：hash / manual |
| `--traffic-ratio` | 数值 | 否 | `null` | 实验流量比例；hash 策略取值范围为 (0, 1]，manual 策略取值范围为 [0, 1] |
| `--bucket-key` | 字符串 | 否 | `null` | 分桶主体字段，例如 customer_id / order_id / application_id |
| `--description` | 字符串 | 否 | `null` | 实验描述 |
| `--effective-from` | 字符串 | 否 | `null` | 生效时间 |
| `--effective-to` | 字符串 | 否 | `null` | 失效时间 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --traffic-ratio 必须在 0 到 1 之间
- hash 策略下 --traffic-ratio 必须大于 0
- 实验配置 config 必须是 JSON 对象
- --format 只支持 text 或 json
- 至少需要提供一个更新参数
- --name 不能为空
- --bucket-key 不能为空
- 暂停状态下只允许修改 description 和 effective_to
- --strategy 只支持 hash 或 manual
- 实验配置中的 traffic_ratio 不是有效数字
- --effective-to 必须晚于 --effective-from

## datamind experiment list

列出实验。

权限：`experiment.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/list.py)

```text
datamind experiment list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--model-id` | 字符串 | 否 | `null` | 按模型 ID 过滤 |
| `--status` | 字符串 | 否 | `null` | 按实验状态过滤，可选值：draft / running / paused / stopped / completed / archived |
| `--created-by` | 字符串 | 否 | `null` | 按创建人过滤 |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除实验 |
| `--limit` | 整数 | 否 | `null` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `null` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json
- --limit 必须大于 0
- --offset 不能小于 0

## datamind experiment show

查看实验详情。

权限：`experiment.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/show.py)

```text
datamind experiment show <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除实验及分组 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment start

启动实验。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/start.py)

```text
datamind experiment start <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- 实验配置 config 必须是 JSON 对象
- --format 只支持 text 或 json
- 实验没有可用的启用状态分组，请先添加实验分组
- 实验必须且只能包含一个启用状态的对照组
- 实验至少需要包含一个启用状态的实验组
- hash 策略下启用状态分组的权重之和必须等于 1

## datamind experiment pause

暂停实验。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/pause.py)

```text
datamind experiment pause <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment stop

停止实验。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/stop.py)

```text
datamind experiment stop <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment complete

完成实验。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/complete.py)

```text
datamind experiment complete <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment archive

归档实验。

权限：`experiment.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/archive.py)

```text
datamind experiment archive <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment analyze

分析实验效果。

权限：`experiment.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/analyze.py)

```text
datamind experiment analyze <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--baseline-variant-id` | 字符串 | 否 | `null` | 基准分组 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment delete

逻辑删除草稿或已归档实验及其分组。

权限：`experiment.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/delete.py)

```text
datamind experiment delete <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind experiment restore

恢复逻辑删除的实验及同批分组。

权限：`experiment.delete`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/restore.py)

```text
datamind experiment restore <experiment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<experiment_id>` | 字符串 | 是 | `—` | 实验 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json
