# 使用方式

## 安装依赖

```bash
pip install typer
```

## CLI 运行

### 注册模型
```bash
python -m datamind.cli.main model register \
    --name scorecard \
    --version 1.0.0 \
    --framework sklearn \
    --model-type logistic_regression \
    --task-type scoring \
    --model-path datamind/demo/scorecard.pkl \
    --description "信用评分卡模型" \
    --created-by admin \
    --force
```

### 列出模型
```bash
python -m datamind.cli.main model list \
  --framework sklearn \
  --model-type logistic_regression \
  --verbose
```

### 删除所有 bentoml 模型
```bash
bentoml models list | awk 'NR>2 {print $1}' | xargs -r bentoml models delete -y
```

### 查看版本
```bash
python -m datamind.cli.main model version \
  --framework sklearn \
  --model-type logistic_regression \
  --verbose
```




## 下一步你可以自然扩展成

```bash
datamind model register
datamind model list
datamind model delete
datamind model get
datamind model versions
datamind model delete
datamind model archive
datamind model show

datamind version list
datamind version rollback

datamind deployment create
datamind deployment stop

datamind routing ...
datamind experiment ...
```

这时候 `Datamind` 就开始像：

- `MLflow`
- `Docker`
- `kubectl`

这种“平台入口”了。

而且你现在的分层，其实已经很接近这个方向。

list = 多个模型
show = 单个模型

datamind model list
datamind model show <name>
datamind model delete <name>

datamind model version list <name>
datamind model version show <version-id>
datamind model version delete <version-id>

datamind deployment list --model <name>
datamind deployment show <deployment-id>

datamind routing show <model>
datamind experiment list <model>
datamind assignment list <model>

如果你下一步要统一 CLI 文档，我可以帮你把：

model list
model show
model delete
model version list / show / delete
model register

全部统一成同一份 CLI spec（可以直接放 README 或 docs）。


## 注册模型
### model register 命令
#### 命令格式

```bash
datamind model register <name>
  --version <version>
  --model-path <path>
  --framework <framework>
  --model-type <model-type>
  --task-type <task-type>
  --input-schema-file <file>
  --output-schema-file <file>
  --description <description>
  --owner <owner>
  --force
  --format <format>
  --verbose
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（业务唯一标识，例如 scorecard） |
| `--version <version>` | 模型版本号，例如 1.0.0 |
| `--model-path <path>` | 模型文件路径（本地或存储路径） |
| `--framework <framework>` | 模型框架，例如 `sklearn`、`xgboost`、`lightgbm`、`catboost` |
| `--model-type <model-type>` | 模型类型，例如 logistic_regression、random_forest、xgboost |
| `--task-type <task-type>` | 任务类型，例如 `classification`、`scoring` |
| `--input-schema-file <file>` | 输入 Schema 文件（JSON）|
| `--output-schema-file <file>` | 输出 Schema 文件（JSON）|
| `--description <description>` | 模型描述 |
| `--owner <owner>` | 创建人/注册人，默认 `system` |
| `--force` | 是否强制覆盖已有版本（存在则更新） |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 是否输出调试日志 |

#### 使用示例
```bash
# 注册
datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --description "信用评分卡模型" \
  --owner admin

# 强制覆盖已存在版本
datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --force
```

## 列出模型
### model list 命令

#### 命令格式

```bash
datamind model list
  [--status <status>]
  [--framework <framework>]
  [--model-type <model-type>]
  [--task-type <task-type>]
  [--owner <owner>]
  [--format <format>]
  [--limit <n>]
  [--offset <n>]
  [--include-archived]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--status <status>` | 按模型状态过滤，例如 `active`、`inactive`、`archived` |
| `--framework <framework>` | 按模型框架过滤，例如 `sklearn`、`xgboost`、`pytorch` |
| `--model-type <model-type>` | 按模型类型过滤，例如 `batch`、`online` |
| `--task-type <task-type>` | 按任务类型过滤，例如 `classification`、`scoring` |
| `--owner <owner>` | 按创建人过滤 |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--limit <n>` | 返回记录数量限制，用于分页，默认从起始位置返回指定数量 |
| `--offset <n>` | 分页偏移量，跳过前 `n` 条记录后开始返回 |
| `--include-archived` | 包含已归档的模型，默认不显示 |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
datamind model list
datamind model list --include-archived
datamind model list --status active
datamind model list --limit 20 --offset 0
```

## 查看模型详情命令
### model show 命令

#### 命令格式

```bash
datamind model show (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（与 `--model-id` 二选一） |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 版本号（与 `--version-id` 二选一） |
| `--version-id <version-id>` | 版本 ID |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
datamind model show scorecard
```

## 激活模型命令
### model activate 命令

#### 命令格式

```bash
datamind model activate (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（与 `--model-id` 二选一） |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 版本号（与 `--version-id` 二选一） |
| `--version-id <version-id>` | 版本 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
datamind model activate scorecard --version 1.0.0 --operator admin
```

## 停用模型命令
### model deactivate 命令

#### 命令格式

```bash
datamind model deactivate (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（与 `--model-id` 二选一） |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 版本号（与 `--version-id` 二选一） |
| `--version-id <version-id>` | 版本 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
datamind model deactivate scorecard --version 1.0.0 --operator admin
```

## 删除模型
### model delete 命令

#### 命令格式

```bash
datamind model delete (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--operator <user>]
  [--purge]
  [--yes]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（与 `--model-id` 二选一） |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 版本号（与 `--version-id` 二选一） |
| `--version-id <version-id>` | 版本 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--purge` | 是否执行物理删除（默认执行归档删除） |
| `--yes` | 跳过交互确认 |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash id="model_delete_examples"
# 删除模型（所有版本）
datamind model delete scorecard

# 删除指定版本
datamind model delete scorecard --version 1.0.0

# 按模型 ID 删除（机器友好接口，不推荐用户使用）
datamind model delete --model-id mdl_a1b2c3d4

# 按版本 ID 删除（机器友好接口，不推荐用户使用）
datamind model delete --version-id ver_a1b2c3d4

# 强制物理删除，跳过确认
datamind model delete scorecard --version 1.0.0 --purge --yes
```

## 部署模型

### deployment list 命令

#### 命令格式

```bash
datamind deployment list
  [--framework <framework>]
  [--environment <environment>]
  [--rollout-type <full|canary|shadow>]
  [--role <champion|challenger>]
  [--status <status>]
  [--deployed-by <user>]
  [--exclude-status <status>]
  [--limit <number>]
  [--offset <number>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--framework <framework>` | 模型框架过滤，例如 `sklearn`、`xgboost`、`lightgbm` |
| `--environment <environment>` | 部署环境，例如 `production`、`staging`、`development`、`testing` |
| `--rollout-type <full|canary|shadow>` | 发布方式过滤 |
| `--role <champion|challenger>` | 部署角色过滤 |
| `--status <status>` | 部署状态，例如 `active`、`inactive` |
| `--deployed-by <user>` | 按部署人过滤 |
| `--exclude-status <status>` | 排除指定状态 |
| `--limit <number>` | 返回记录数限制，默认 `20` |
| `--offset <number>` | 分页偏移量 |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash id="deployment_list_examples"
datamind deployment list
datamind deployment list --verbose
datamind deployment list fraud_model
datamind deployment list fraud_model --version v1.0.0
datamind deployment list --model-id mdl_a1b2c3d4
datamind deployment list --environment production
datamind deployment list --rollout-type canary
datamind deployment list --status active
datamind deployment list --format json
datamind deployment list --limit 50 --offset 100
```

### deployment show 命令

#### 命令格式

```bash
datamind deployment show <deployment-id>
  [--format <text|json>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<deployment-id>` | 部署 ID |
| `--format <text|json>` | 输出格式，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash id="deployment_show_examples"
datamind deployment show dep_a1b2c3d4
datamind deployment show dep_123456 --format json
datamind deployment show dep_123456 --verbose
```

### deployment create 命令

#### 命令格式

```bash
datamind deployment create (<name> | --model-id <model-id>)
  --version <version> | --version-id <version-id>
  --environment <environment>
  --rollout <rollout>
  --config-file <file>
  [--description <text>]
  [--owner <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（与 `--model-id` 二选一） |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 模型版本号（与 `--version-id` 二选一） |
| `--version-id <version-id>` | 版本 ID |
| `--environment <environment>` | 部署环境，例如 `production` / `staging` / `development` / `testing` |
| `--rollout <rollout>` | 发布策略，例如`full`（全量发布） / `canary`（灰度发布） / `shadow`（影子发布） |
| `--config-file <file>` | 运行时配置文件（JSON） |
| `--description <text>` | 部署描述信息 |
| `--owner <user>` | 创建人 / 负责人 |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 是否输出调试日志 |

#### 使用示例

```bash id="deployment_create_file_examples"
datamind deployment create scorecard \
  --version 1.0.0 \
  --environment production \
  --rollout full \
  --config-file config.json \
  --description "信用评分模型生产部署" \
  --owner admin
```

#### config 示例

##### 评分任务
```json
{
  "pdo": 50,
  "base_score": 600
}
```

##### 分类任务
```json
{
  "threshold": 0.5
}
```


#### 使用示例

```bash
# 创建全量部署
datamind deployment create scorecard \
  --version 1.0.0 \
  --environment production \
  --rollout full \
  --config '{
    "pdo": 50,
    "base_score": 600
  }' \
  --description "创建全量发布版本 1.0.0" \
  --owner admin

# 创建灰度部署
datamind deployment create scorecard \
  --version 1.0.0 \
  --environment production \
  --rollout canary \
  --config '{
    "threshold": 0.5
  }' \
  --description "创建灰度发布版本 1.0.0" \
  --owner admin

# 创建影子部署
datamind deployment create scorecard \
  --version 1.0.0 \
  --environment production \
  --rollout shadow \
  --config '{
    "pdo": 50,
    "base_score": 600
  }' \
  --description "创建影子发布版本 1.0.0" \
  --owner admin
```

### deployment enable 命令

#### 命令格式

```bash
datamind deployment enable <deployment-id>
  [--operator <user>]
  [--format <text|json>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<deployment-id>` | 部署 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <text\|json>` | 输出格式，默认 `text` |
| `--verbose` | 显示调试日志 |


#### 使用示例

```bash

# 启用部署
datamind deployment enable dep_a1b2c3d4

# 显示调试日志
datamind deployment enable dep_a1b2c3d4 --verbose
```

### deployment disable 命令

#### 命令格式

```bash
datamind deployment disable <deployment-id>
  [--operator <user>]
  [--format <text|json>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<deployment-id>` | 部署 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <text|json>` | 输出格式，默认 `text` |
| `--verbose` | 显示调试日志 |


#### 使用示例

```bash

# 禁用部署
datamind deployment disable dep_a1b2c3d4

# 显示调试日志
datamind deployment disable dep_a1b2c3d4 --verbose
```

## 创建实验
### experiment create 命令

#### 命令格式

```bash
datamind experiment create
  --model-id <model-id>
  [--name <name>]
  [--traffic-ratio <ratio>]
  [--bucket-key <key>]
  [--config <json>]
  [--description <description>]
  [--owner <owner>]
  [--effective-from <datetime>]
  [--effective-to <datetime>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--model-id <model-id>` | 模型 ID |
| `--name <name>` | 实验名称，例如 `scorecard_ab_test` |
| `--traffic-ratio <ratio>` | 实验流量比例，范围 `0~1`，默认 `1.0` |
| `--bucket-key <key>` | 分桶主体字段，例如 `customer_id`、`order_id`、`apply_id`，默认 `customer_id` |
| `--config <json>` | 实验配置 JSON 字符串 |
| `--description <description>` | 实验描述 |
| `--owner <owner>` | 创建人，默认 `system` |
| `--effective-from <datetime>` | 生效开始时间，ISO 格式，例如 `2026-07-01T09:00:00+08:00`；默认当前时间 |
| `--effective-to <datetime>` | 生效结束时间，ISO 格式，例如 `2026-07-31T23:59:59+08:00`；默认不限制结束时间 |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 补充说明

| 配置项 | 说明 |
|------|------|
| `bucket_key` | 表示分桶主体字段，用于从请求数据中提取 `subject_key` |
| `effective_from` | 默认当前 UTC 时间；CLI 文本输出时显示为本地时间 |
| `effective_to` | 默认 `None`，表示不限制结束时间 |
| `strategy` | 默认写入实验配置为 `hash` |

#### 使用示例

```bash
# 创建实验
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --traffic-ratio 0.5 \
  --bucket-key customer_id \
  --owner admin

# 创建指定生效时间的实验
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --traffic-ratio 0.5 \
  --bucket-key customer_id \
  --effective-from 2026-07-01T09:00:00+08:00 \
  --effective-to 2026-07-31T23:59:59+08:00 \
  --owner admin

# 使用 JSON 配置创建实验
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --config '{"strategy":"hash","remark":"scorecard ab test"}' \
  --owner admin
```

## 列出实验
### experiment list 命令

#### 命令格式

```bash
datamind experiment list
  [--model-id <model-id>]
  [--status <status>]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--model-id <model-id>` | 按模型 ID 过滤 |
| `--status <status>` | 按实验状态过滤，例如 `draft`、`running`、`paused`、`stopped`、`completed`、`archived` |
| `--created-by <user>` | 按创建人过滤 |
| `--limit <n>` | 返回记录数量限制，默认 `10` |
| `--offset <n>` | 分页偏移量，默认 `0` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 列出全部实验
datamind experiment list

# 列出指定模型下的实验
datamind experiment list --model-id mdl_a1b2c3d4

# 按实验状态过滤
datamind experiment list --status running

# 按创建人过滤
datamind experiment list --created-by admin

# 分页查询
datamind experiment list --limit 20 --offset 0

# JSON 格式输出
datamind experiment list --format json
```

## 查看实验详情
### experiment show 命令

#### 命令格式

```bash
datamind experiment show <experiment-id>
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 查看实验详情
datamind experiment show exp_a1b2c3d4

# JSON 格式输出
datamind experiment show exp_a1b2c3d4 --format json
```

## 启动实验
### experiment start 命令

#### 命令格式

```bash
datamind experiment start <experiment-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 启动实验
datamind experiment start exp_a1b2c3d4 --operator admin
```

## 暂停实验
### experiment pause 命令

#### 命令格式

```bash
datamind experiment pause <experiment-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 暂停实验
datamind experiment pause exp_a1b2c3d4 --operator admin
```

## 停止实验
### experiment stop 命令

#### 命令格式

```bash
datamind experiment stop <experiment-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 停止实验
datamind experiment stop exp_a1b2c3d4 --operator admin
```

## 完成实验
### experiment complete 命令

#### 命令格式

```bash
datamind experiment complete <experiment-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 标记实验完成
datamind experiment complete exp_a1b2c3d4 --operator admin
```

## 归档实验
### experiment archive 命令

#### 命令格式

```bash
datamind experiment archive <experiment-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 归档实验
datamind experiment archive exp_a1b2c3d4 --operator admin
```

## 实验状态说明

| 命令 | 状态 | 说明 |
|------|------|------|
| `experiment start` | `running` | 启动实验，开始分配实验流量 |
| `experiment pause` | `paused` | 临时暂停实验，后续可以再次启动 |
| `experiment stop` | `stopped` | 停止实验，通常表示实验异常中止或不再继续 |
| `experiment complete` | `completed` | 标记实验正常完成，通常用于达到观察周期或样本量后 |
| `experiment archive` | `archived` | 归档实验，作为历史记录保留 |

#### 推荐生命周期

```text
draft -> running -> completed -> archived
draft -> running -> paused -> running -> completed -> archived
draft -> running -> stopped -> archived
```

## 分析实验
### experiment analyze 命令

#### 命令格式

```bash
datamind experiment analyze <experiment-id>
  [--baseline-variant-id <variant-id>]
  [--limit <n>]
  [--offset <n>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--baseline-variant-id <variant-id>` | 基准分组 ID，用于计算其他分组相对基准分组的 lift |
| `--limit <n>` | 实验结果数量限制，用于分页 |
| `--offset <n>` | 分页偏移量，跳过前 `n` 条记录后开始返回 |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 分析实验
datamind experiment analyze exp_a1b2c3d4

# 指定对照组进行分析
datamind experiment analyze exp_a1b2c3d4 \
  --baseline-variant-id var_control

# 分页分析实验结果
datamind experiment analyze exp_a1b2c3d4 \
  --baseline-variant-id var_control \
  --limit 1000 \
  --offset 0
```

## 添加实验分组
### experiment variant add 命令

#### 命令格式

```bash
datamind experiment variant add <experiment-id>
  --name <name>
  --deployment-id <deployment-id>
  --weight <weight>
  [--control]
  [--config <json>]
  [--description <description>]
  [--owner <owner>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--name <name>` | 实验分组名称，例如 `control`、`treatment` |
| `--deployment-id <deployment-id>` | 分组关联的部署 ID |
| `--weight <weight>` | 分组权重，范围 `0~1` |
| `--control` | 是否为对照组 |
| `--config <json>` | 分组配置 JSON 字符串 |
| `--description <description>` | 分组描述 |
| `--owner <owner>` | 创建人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 添加对照组
datamind experiment variant add exp_a1b2c3d4 \
  --name control \
  --deployment-id dep_control \
  --weight 0.5 \
  --control \
  --owner admin

# 添加实验组
datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5 \
  --owner admin

# 添加带配置的实验组
datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5 \
  --config '{"model_role":"challenger"}' \
  --owner admin
```

## 列出实验分组
### experiment variant list 命令

#### 命令格式

```bash
datamind experiment variant list [<experiment-id>]
  [--deployment-id <deployment-id>]
  [--status <status>]
  [--control | --non-control]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 按实验 ID 过滤，可选 |
| `--deployment-id <deployment-id>` | 按部署 ID 过滤 |
| `--status <status>` | 按实验分组状态过滤，例如 `active`、`inactive`、`archived` |
| `--control` | 只查看对照组 |
| `--non-control` | 只查看非对照组 |
| `--created-by <user>` | 按创建人过滤 |
| `--limit <n>` | 返回记录数量限制，默认 `10` |
| `--offset <n>` | 分页偏移量，默认 `0` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 列出所有实验分组
datamind experiment variant list

# 列出实验下所有分组
datamind experiment variant list exp_a1b2c3d4

# 只查看启用状态的分组
datamind experiment variant list exp_a1b2c3d4 --status active

# 按部署 ID 查询分组
datamind experiment variant list --deployment-id dep_a1b2c3d4

# 只查看对照组
datamind experiment variant list --control

# 只查看非对照组
datamind experiment variant list --non-control

# 按创建人过滤
datamind experiment variant list --created-by admin

# 分页查询
datamind experiment variant list --limit 20 --offset 0
```

## 查看实验分组详情
### experiment variant show 命令

#### 命令格式

```bash
datamind experiment variant show <variant-id>
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<variant-id>` | 实验分组 ID |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 查看实验分组详情
datamind experiment variant show var_a1b2c3d4

# JSON 格式输出
datamind experiment variant show var_a1b2c3d4 --format json
```

## 启用实验分组
### experiment variant activate 命令

#### 命令格式

```bash
datamind experiment variant activate <variant-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<variant-id>` | 实验分组 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 启用实验分组
datamind experiment variant activate var_a1b2c3d4 --operator admin
```

## 停用实验分组
### experiment variant deactivate 命令

#### 命令格式

```bash
datamind experiment variant deactivate <variant-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<variant-id>` | 实验分组 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 停用实验分组
datamind experiment variant deactivate var_a1b2c3d4 --operator admin
```

## 归档实验分组
### experiment variant archive 命令

#### 命令格式

```bash
datamind experiment variant archive <variant-id>
  [--operator <user>]
  [--format <format>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<variant-id>` | 实验分组 ID |
| `--operator <user>` | 操作人，默认 `system` |
| `--format <format>` | 输出格式，例如 `text` 或 `json`，默认 `text` |
| `--verbose` | 显示调试日志 |

#### 使用示例

```bash
# 归档实验分组
datamind experiment variant archive var_a1b2c3d4 --operator admin
```

## 常见操作流程

### 创建并启动一个 A/B 实验

```bash
# 1. 创建实验
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --traffic-ratio 0.5 \
  --bucket-key customer_id \
  --owner admin

# 2. 添加对照组
datamind experiment variant add exp_a1b2c3d4 \
  --name control \
  --deployment-id dep_control \
  --weight 0.5 \
  --control \
  --owner admin

# 3. 添加实验组
datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5 \
  --owner admin

# 4. 查看实验详情
datamind experiment show exp_a1b2c3d4

# 5. 启动实验
datamind experiment start exp_a1b2c3d4 --operator admin
```

### 暂停并恢复实验

```bash
# 1. 暂停实验
datamind experiment pause exp_a1b2c3d4 --operator admin

# 2. 恢复实验
datamind experiment start exp_a1b2c3d4 --operator admin
```

### 分析并完成实验

```bash
# 1. 分析实验效果
datamind experiment analyze exp_a1b2c3d4 \
  --baseline-variant-id var_control

# 2. 标记实验完成
datamind experiment complete exp_a1b2c3d4 --operator admin

# 3. 归档实验
datamind experiment archive exp_a1b2c3d4 --operator admin
```

### 异常中止实验

```bash
# 1. 停止实验
datamind experiment stop exp_a1b2c3d4 --operator admin

# 2. 归档实验
datamind experiment archive exp_a1b2c3d4 --operator admin
```

deployment create
deployment enable
deployment disable
deployment list
deployment show

route create
route update
route delete
route list
route show
route enable
route disable



datamind deployment traffic <deployment-id>
  --ratio <0-1>

datamind deployment canary
  --model-id <model-id>
  --version <version>
  --ratio <ratio>
  [--environment <env>]

datamind deployment rollback
  --deployment-id <deployment-id>
  [--to-version <version> | --to-version-id <version-id>]

布升级（promote）
datamind deployment promote <deployment-id>

👉 canary → primary



## 命令模板
### command template 命令
#### 命令格式
```bash
```
#### 参数说明

#### 使用示例
```bash
```







## 列出版本

### model version list 命令

#### 命令格式

```bash
datamind model version list <name>
```

#### 使用示例

```bash
datamind model version list scorecard
datamind model version list mdl_a1b2c3d4
```

### model version show 命令

#### 命令格式

```bash
datamind model version show <version-id>
```

#### 使用示例

```bash
datamind model version show ver_a1b2c3d4
```

## 删除版本

### model version delete 命令

#### 命令格式

```bash
datamind model version delete <version-id>
  [--purge]
  [--yes]
```

#### 使用示例

```bash
# 软删除（推荐默认）
datamind model version delete ver_a1b2c3d4

# 物理删除
datamind model version delete ver_a1b2c3d4 --purge

# 跳过确认
datamind model version delete ver_a1b2c3d4 --purge --yes
```

```text
datamind
 ├── model
 │    ├── list
 │    ├── show
 │    ├── delete
 │    └── version
 ├── deployment
 ├── experiment
 └── routing
```

```text
datamind/cli/
├── __init__.py
├── main.py
├── model/
│   ├── __init__.py
│   ├── list.py
│   ├── show.py
│   ├── delete.py
│   └── version/
│       ├── __init__.py
│       ├── list.py
│       ├── show.py
│       └── delete.py
```