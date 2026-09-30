# Outcome 回流 CLI

任务步骤见[使用指南](../experiments/outcomes.md)。本页列出当前命令、全部显式参数、默认值、权限和入口校验；服务层的状态转换见[状态与权限](../reference/states-permissions.md)。

位置参数用大写表示；`null` 表示未指定。布尔开关默认关闭时，传入选项将其开启。重复选项和路径要求以类型/说明为准。所有命令还支持 `--help`。

## datamind outcome submit

提交或更新实验结果.

权限：`outcome.write`

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/outcome/submit.py)。

```text
datamind outcome submit <subject_key> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<subject_key>` | text | 是 | `—` | 结果主体标识 |
| `--decision-id` | text | 否 | `null` | 原始决策 ID |
| `--request-id` | text | 否 | `null` | 原始请求 ID |
| `--outcome-id` | text | 否 | `null` | 上游结果唯一标识，默认自动生成 |
| `--subject-type` | text | 否 | `null` | 结果主体类型 |
| `--approved/--not-approved` | boolean | 否 | `null` | 是否审批通过 |
| `--converted/--not-converted` | boolean | 否 | `null` | 是否发生转化 |
| `--defaulted/--not-defaulted` | boolean | 否 | `null` | 是否发生违约 |
| `--overdue-days` | integer | 否 | `null` | 最大逾期天数 |
| `--amount` | float | 否 | `null` | 结果金额 |
| `--label` | text | 否 | `null` | 结果标签 |
| `--context` | text | 否 | `null` | 结果上下文 JSON 对象 |
| `--outcome-time` | parse_datetime | 否 | `null` | 结果发生时间，ISO 8601 格式 |
| `--format` | text | 否 | `"text"` | 输出格式：text / json |

入口校验与错误：

- --context 必须是 JSON 对象
