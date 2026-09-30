# 路由规则与生效时间

`route create` 与 `route update` 的 `--rules-file` 读取 JSON 对象，由 RuleMatcher 校验。空规则匹配所有请求；规范写法如下：

```json
{
  "match": "all",
  "conditions": [
    {"field": "features.age", "op": "gte", "value": 18},
    {"field": "features.annual_income", "op": "between", "value": [50000, 200000]}
  ]
}
```

将文件保存为 `routing-rules.json` 后应用：

```bash
datamind route update <routing_id> --rules-file routing-rules.json
```

示例字段来自违约概率模型的贷款特征，不适用于申请评分卡的另一套输入。规则使用字段点路径读取请求载荷；模型特征可写 `features.<字段>`，也可按 matcher 支持的载荷解析方式读取。规则条件不会生成或变更模型输入。

## 条件组合和运算符

`match=all` 要求所有条件成立，`any` 要求至少一个成立，默认 all。单条条件可用 `negate=true` 取反。

| 运算符 | 含义与 value |
| --- | --- |
| eq / ne | 等于 / 不等于指定值 |
| gt / gte / lt / lte | 大于 / 大于等于 / 小于 / 小于等于 |
| in / not_in | 属于 / 不属于 value 集合 |
| between | 位于两个边界之间，value 为两个值的数组 |
| exists / missing | 字段存在且非 null / 字段缺失或为 null，不需要 value |
| is_null / not_null | 值为 null / 非 null，不需要 value |
| contains / not_contains | 字符串或集合包含 / 不包含 value |
| startswith / endswith | 字符串前缀 / 后缀 |
| regex | 字符串匹配正则表达式 |

missing 对不存在或 null 都成立，is_null 仅对实际 null 成立；exists 要求字段存在且非 null。数字比较会尝试将数字字符串转为数字，但布尔值不作为数字；无法转换时不匹配。between 包含两个边界。非法运算符、between 数组长度或正则表达式会被校验拒绝。可使用多个 all/any 条件表达筛选，无需把业务条件写入说明字段。

`bucket_key`、`bucket_range`、`customer_id`、`hash_salt`、`salt`、`description`、`note`、`version` 属于 matcher 的兼容元数据键，不能单靠它们表达条件筛选。新规则优先使用上面的 conditions 结构。完整实现与验证用例位于 `datamind/runtime/routing/matcher.py` 和 `tests/unit/routing/test_matcher.py`。

## 生效时间

Deployment 和 Routing 都可设置 effective_from / effective_to。解析时以 UTC 比较：起点包含，终点不包含，即 `[from, to)`。省略一侧表示该侧不限制；终点必须晚于起点。CLI 时间输入和显示受日志时区配置影响，跨时区操作优先提交明确带时区的 ISO 时间。

```bash
datamind route update <routing_id> \
  --effective-from '2026-10-01T00:00:00+08:00' \
  --effective-to '2026-11-01T00:00:00+08:00'
```

路由需要同时满足启用状态、时间、规则和部署可用性。规则不匹配并不保证请求被拒绝：之后仍可能走默认部署回退，见[Routing](index.md)。
