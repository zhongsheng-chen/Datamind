# 业务结果回流

相关说明见[对应文档](../experiments/outcomes.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind outcome submit

提交或更新实验结果。

权限：`outcome.write`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/outcome/submit.py)

```text
datamind outcome submit <subject_key> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<subject_key>` | 字符串 | 是 | `—` | 结果主体标识 |
| `--decision-id` | 字符串 | 否 | `null` | 原始决策 ID |
| `--request-id` | 字符串 | 否 | `null` | 原始请求 ID |
| `--outcome-id` | 字符串 | 否 | `null` | 上游结果唯一标识，默认自动生成 |
| `--subject-type` | 字符串 | 否 | `null` | 结果主体类型 |
| `--approved/--not-approved` | 布尔 | 否 | `null` | 是否审批通过 |
| `--converted/--not-converted` | 布尔 | 否 | `null` | 是否发生转化 |
| `--defaulted/--not-defaulted` | 布尔 | 否 | `null` | 是否发生违约 |
| `--overdue-days` | 整数 | 否 | `null` | 最大逾期天数 |
| `--amount` | 数值 | 否 | `null` | 结果金额 |
| `--label` | 字符串 | 否 | `null` | 结果标签 |
| `--context` | 字符串 | 否 | `null` | 结果上下文 JSON 对象 |
| `--outcome-time` | parse_datetime | 否 | `null` | 结果发生时间，ISO 8601 格式 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --context 必须是 JSON 对象
