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

datamind deploy create
datamind deploy stop

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

| 参数 | 说明                                        |
|------|-------------------------------------------|
| `--status <status>` | 按模型状态过滤，例如 `active`、`inactive`、`archived` |
| `--framework <framework>` | 按模型框架过滤，例如 `sklearn`、`xgboost`、`pytorch`  |
| `--model-type <model-type>` | 按模型类型过滤，例如 `batch`、`online`               |
| `--task-type <task-type>` | 按任务类型过滤，例如 `classification`、`scoring`     |
| `--owner <owner>` | 按创建人过滤                                    |
| `--format <format>` | 输出格式，例如 `table` 或 `json`，默认 `table`       |
| `--limit <n>` | 返回记录数量限制，用于分页，默认从起始位置返回指定数量               |
| `--offset <n>` | 分页偏移量，跳过前 `n` 条记录后开始返回                    |
| `--include-archived` | 包含已归档的模型，默认不显示                            |
| `--verbose` | 显示调试日志                                    |

#### 使用示例
```bash
datamind model list
datamind model list --include-archived
datamind model list --status active
datamind model list --limit 20 --offset 0
```

### model show 命令
#### 命令格式
```bash
datamind model show (<name> | --model-id <model-id>)
  [--format <table|json>]
  [--verbose]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称（人类友好，推荐） |
| `--model-id <model-id>` | 模型 ID（机器友好接口） |
| `--format <table\|json>` | 输出格式，默认 `table` |
| `--verbose` | 显示调试日志 |

#### 使用示例
```bash
datamind model show scorecard
```

## 删除模型
### model delete 命令
#### 命令格式
```bash
datamind model delete (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--purge]
  [--yes]
```

#### 使用示例
```bash
# 删除模型（所有版本）
datamind model delete scorecard

# 删除版本
datamind model delete scorecard --version 1.0.0

# 按模型 ID 删除（机器友好接口，不推荐用户使用）
datamind model delete --model-id mdl_a1b2c3d4

# 按版本 ID 删除（机器友好接口，不推荐用户使用）
datamind model delete --version-id ver_a1b2c3d4

# 强制物理删除，交互确认（推荐生产）
datamind model delete scorecard --version 1.0.0 --purge

# 跳过确认
datamind model delete scorecard --version 1.0.0 --purge --yes
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