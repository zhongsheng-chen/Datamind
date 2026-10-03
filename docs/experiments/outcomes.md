# 业务结果回流

模型预测之后产生的审批、转化、违约等业务结果，作为业务结果（`Outcome`）回流到平台。每条结果关联原始请求或决策，用于比较实验分组的后验表现。

## 结果字段

| 字段 | 含义 |
| --- | --- |
| `outcome_id` | 上游结果唯一标识 |
| `subject_key` / `subject_type` | 主体标识与类型 |
| `decision_id` / `request_id` | 原始决策或请求引用 |
| `approved` / `converted` / `defaulted` | 审批、转化、违约结果 |
| `overdue_days` | 非负逾期天数 |
| `amount` | 非负结果金额 |
| `label` / `context` | 标签与扩展上下文 |
| `outcome_time` | 结果发生时间 |

## 回流入口

HTTP 使用 `POST /feedback/outcomes`。CLI 使用 `datamind outcome submit`。HTTP 请求要求 `outcome_id`，CLI 未指定 `--outcome-id` 时会自动生成。重试或更新同一结果时应复用上游结果标识，避免每次生成新的记录。

## 延迟结果

T+30、T+60、T+90 观察窗口由调用方定义并提交，平台不自动等待标签成熟，也不执行审批策略。把窗口写入 `context`，`outcome_time` 记录实际业务结果时刻。

## 关联与幂等更新

提交必须通过 `request_id` 或 `decision_id` 找到原始决策。同时提供两者时必须指向同一决策。`subject_key` 必须与原决策主体一致。实验（`Experiment`）、实验分组（`Variant`）与实验分配（`Assignment`）归属从该决策复制，不能用客户端指定的新实验覆盖。

同 `outcome_id` 首次提交创建记录，再次提交更新已有记录，但不能改绑其他决策或主体。更新只覆盖非 null 字段，false、0 和空对象属于实际值。省略或 null 不会清空已有字段。上游重试应复用稳定 `outcome_id`，CLI 自动生成的新 ID 不适合重复回流同一结果。

例如同一 T+30 结果先提交 `approved`，标签成熟后补交 `defaulted`，使用相同 `outcome_id` 和 `request_id`。这是一条结果的更新，分析时不会因为重复请求多计一条。

如果 T+30 与 T+60 使用不同 `outcome_id`，它们会成为两条记录。当前分析按业务结果行聚合，不会自动挑选最新窗口或按主体去重。需要单一窗口分析时使用一致的更新约定，或在上游准备适合评估的数据，不要混合不同观察窗口后解释为客户比例。

相关接口见[预测 API](../reference/runtime-api.md)，分析入口见[实验分析](analysis.md)。
