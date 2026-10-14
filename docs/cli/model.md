# 模型命令

<span class="cli-reference"></span>

操作流程见[模型管理](../models/index.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

<a id="datamind-model-register"></a>

## `register`

注册模型。

```text
datamind model register <name> [OPTIONS]
```

| 参数                    | 类型   | 必需 | 默认值   | 说明                  |
|-------------------------|--------|------|----------|-----------------------|
| `<name>`                | 字符串 | 是   | `—`      | 模型名称              |
| `--version`             | 字符串 | 是   | `—`      | 模型版本              |
| `--display-name`        | 字符串 | 否   | `null`   | 模型显示名称          |
| `--model-path`          | 字符串 | 是   | `—`      | 模型文件路径          |
| `--framework`           | 字符串 | 是   | `—`      | 模型框架              |
| `--model-type`          | 字符串 | 是   | `—`      | 模型类型              |
| `--task-type`           | 字符串 | 是   | `—`      | 任务类型              |
| `--description`         | 字符串 | 否   | `null`   | 模型描述              |
| `--version-description` | 字符串 | 否   | `null`   | 模型版本描述          |
| `--force`               | 布尔   | 否   | `false`  | 强制重新注册已有版本  |
| `--format`              | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`model.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/register.py)

<a id="datamind-model-list"></a>

## `list`

列出模型。

```text
datamind model list [OPTIONS]
```

| 参数                 | 类型   | 必需 | 默认值   | 说明                                                                                                        |
|----------------------|--------|------|----------|-------------------------------------------------------------------------------------------------------------|
| `--status`           | 字符串 | 否   | `null`   | 按模型状态过滤，可选值：active / deprecated / inactive / archived                                           |
| `--framework`        | 字符串 | 否   | `null`   | 按模型框架过滤，可选值：sklearn / xgboost / lightgbm / catboost                                             |
| `--model-type`       | 字符串 | 否   | `null`   | 按模型类型过滤，可选值：logistic_regression / decision_tree / random_forest / xgboost / lightgbm / catboost |
| `--task-type`        | 字符串 | 否   | `null`   | 按任务类型过滤，可选值：classification / scoring                                                            |
| `--created-by`       | 字符串 | 否   | `null`   | 按创建人过滤                                                                                                |
| `--format`           | 字符串 | 否   | `"text"` | 输出格式：text / json                                                                                       |
| `--limit`            | 整数   | 否   | `10`     | 返回记录数量限制。必须大于 0                                                                                |
| `--offset`           | 整数   | 否   | `0`      | 分页偏移量。不能小于 0                                                                                      |
| `--include-archived` | 布尔   | 否   | `false`  | 包含已归档的模型，默认不显示                                                                                |

权限：`model.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/list.py)

<a id="datamind-model-show"></a>

## `show`

查看模型详情。

```text
datamind model show [<name>] [OPTIONS]
```

| 参数                 | 类型   | 必需 | 默认值   | 说明                  |
|----------------------|--------|------|----------|-----------------------|
| `<name>`             | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`         | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`          | 字符串 | 否   | `null`   | 模型版本号            |
| `--version-id`       | 字符串 | 否   | `null`   | 版本 ID               |
| `--include-archived` | 布尔   | 否   | `false`  | 是否包含归档版本      |
| `--format`           | 字符串 | 否   | `"text"` | 输出格式：text / json |

参数组合：

- `<name>` 与 `--model-id` 二选一，必须提供其中一个。
- `--version` 与 `--version-id` 只能指定一个。

权限：`model.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/show.py)

<a id="datamind-model-activate"></a>

## `activate`

激活模型或指定模型版本。

未指定版本时，同时激活模型的全部 inactive 版本。

```text
datamind model activate [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 模型版本号            |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID               |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

参数组合：

- `<name>` 与 `--model-id` 二选一，必须提供其中一个。
- `--version` 与 `--version-id` 只能指定一个。

权限：`model.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/activate.py)

<a id="datamind-model-deactivate"></a>

## `deactivate`

停用模型或模型版本。

未指定版本时，同时停用模型的全部 active 版本。

```text
datamind model deactivate [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 模型版本号            |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID               |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

参数组合：

- `<name>` 与 `--model-id` 二选一，必须提供其中一个。
- `--version` 与 `--version-id` 只能指定一个。

权限：`model.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/deactivate.py)

<a id="datamind-model-deprecate"></a>

## `deprecate`

弃用模型或模型版本。

未指定版本时，同时弃用模型的全部 active、inactive 版本。

```text
datamind model deprecate [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 模型版本号            |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID               |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

参数组合：

- `<name>` 与 `--model-id` 二选一，必须提供其中一个。
- `--version` 与 `--version-id` 只能指定一个。

权限：`model.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/deprecate.py)

<a id="datamind-model-delete"></a>

## `delete`

删除模型。

```text
datamind model delete [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 版本号（可选）        |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID（可选）       |
| `--reason`     | 字符串 | 否   | `null`   | 删除原因              |
| `--yes`        | 布尔   | 否   | `false`  | 跳过确认              |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`model.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/delete.py)

<a id="datamind-model-restore"></a>

## `restore`

恢复逻辑删除的模型或模型版本。

```text
datamind model restore [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 版本号                |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID               |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`model.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/restore.py)

<a id="datamind-model-purge"></a>

## `purge`

永久删除已逻辑删除的模型或模型版本。

```text
datamind model purge [<name>] [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<name>`       | 字符串 | 否   | `null`   | 模型名称              |
| `--model-id`   | 字符串 | 否   | `null`   | 模型 ID               |
| `--version`    | 字符串 | 否   | `null`   | 版本号                |
| `--version-id` | 字符串 | 否   | `null`   | 版本 ID               |
| `--reason`     | 字符串 | 否   | `null`   | 永久删除原因          |
| `--yes`        | 布尔   | 否   | `false`  | 跳过不可逆操作确认    |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`model.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/model/purge.py)
