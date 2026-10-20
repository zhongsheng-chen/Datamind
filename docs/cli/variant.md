# 分组命令

<span class="cli-reference"></span>

操作流程见[实验分配](../experiments/assignment.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

<a id="datamind-experiment-variant-add"></a>

## `add`

添加实验分组。

```text
datamind experiment variant add <experiment_id> [OPTIONS]
```

| 参数              | 类型   | 必需 | 默认值   | 说明                                             |
|-------------------|--------|------|----------|--------------------------------------------------|
| `<experiment_id>` | 字符串 | 是   | `—`      | 实验 ID                                          |
| `--name`          | 字符串 | 是   | `—`      | 实验分组名称，例如 control / treatment。不能为空 |
| `--deployment-id` | 字符串 | 是   | `—`      | 部署 ID。不能为空                                |
| `--weight`        | 数值   | 是   | `—`      | 实验分组权重，范围 (0, 1]                        |
| `--control`       | 布尔   | 否   | `false`  | 是否为对照组                                     |
| `--description`   | 字符串 | 否   | `null`   | 分组描述                                         |
| `--format`        | 字符串 | 否   | `"text"` | 输出格式：text / json                            |

使用限制：

- 实验已存在启用状态的对照组，不能重复添加对照组

权限：`experiment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/add.py)

<a id="datamind-experiment-variant-update"></a>

## `update`

更新实验分组。

```text
datamind experiment variant update <variant_id> [OPTIONS]
```

| 参数              | 类型   | 必需 | 默认值   | 说明                                             |
|-------------------|--------|------|----------|--------------------------------------------------|
| `<variant_id>`    | 字符串 | 是   | `—`      | 实验分组 ID                                      |
| `--name`          | 字符串 | 否   | `null`   | 实验分组名称，例如 control / treatment。不能为空 |
| `--deployment-id` | 字符串 | 否   | `null`   | 部署 ID。不能为空                                |
| `--weight`        | 数值   | 否   | `null`   | 实验分组权重，范围 (0, 1]                        |
| `--control`       | 布尔   | 否   | `false`  | 设置为对照组                                     |
| `--treatment`     | 布尔   | 否   | `false`  | 设置为实验组                                     |
| `--description`   | 字符串 | 否   | `null`   | 分组描述                                         |
| `--format`        | 字符串 | 否   | `"text"` | 输出格式：text / json                            |

参数组合：

- `--control` 与 `--treatment` 不能同时指定。

使用限制：

- 至少需要提供一个更新参数
- 实验已存在其他启用状态的对照组，不能将该分组设置为对照组

权限：`experiment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/update.py)

<a id="datamind-experiment-variant-list"></a>

## `list`

列出实验分组。

```text
datamind experiment variant list [<experiment_id>] [OPTIONS]
```

| 参数                      | 类型   | 必需 | 默认值   | 说明                                                     |
|---------------------------|--------|------|----------|----------------------------------------------------------|
| `<experiment_id>`         | 字符串 | 否   | `null`   | 按实验 ID 过滤                                           |
| `--deployment-id`         | 字符串 | 否   | `null`   | 按部署 ID 过滤                                           |
| `--status`                | 字符串 | 否   | `null`   | 按实验分组状态过滤，可选值：active / inactive / archived |
| `--control/--non-control` | 布尔   | 否   | `null`   | 按是否对照组过滤                                         |
| `--created-by`            | 字符串 | 否   | `null`   | 按创建人过滤                                             |
| `--include-deleted`       | 布尔   | 否   | `false`  | 包含已删除实验分组                                       |
| `--limit`                 | 整数   | 否   | `10`     | 返回记录数量限制。必须大于 0                             |
| `--offset`                | 整数   | 否   | `0`      | 分页偏移量。不能小于 0                                   |
| `--format`                | 字符串 | 否   | `"text"` | 输出格式：text / json                                    |

权限：`experiment.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/list.py)

<a id="datamind-experiment-variant-show"></a>

## `show`

查看实验分组详情。

```text
datamind experiment variant show <variant_id> [OPTIONS]
```

| 参数                | 类型   | 必需 | 默认值   | 说明                  |
|---------------------|--------|------|----------|-----------------------|
| `<variant_id>`      | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--include-deleted` | 布尔   | 否   | `false`  | 包含已删除实验分组    |
| `--format`          | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/show.py)

<a id="datamind-experiment-variant-activate"></a>

## `activate`

启用实验分组。

```text
datamind experiment variant activate <variant_id> [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<variant_id>` | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/activate.py)

<a id="datamind-experiment-variant-deactivate"></a>

## `deactivate`

停用实验分组。

```text
datamind experiment variant deactivate <variant_id> [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<variant_id>` | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/deactivate.py)

<a id="datamind-experiment-variant-archive"></a>

## `archive`

归档实验分组。

```text
datamind experiment variant archive <variant_id> [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<variant_id>` | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.write` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/archive.py)

<a id="datamind-experiment-variant-delete"></a>

## `delete`

逻辑删除草稿实验中的分组。

```text
datamind experiment variant delete <variant_id> [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<variant_id>` | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--reason`     | 字符串 | 否   | `null`   | 删除原因              |
| `--yes`        | 布尔   | 否   | `false`  | 跳过确认              |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/delete.py)

<a id="datamind-experiment-variant-restore"></a>

## `restore`

恢复逻辑删除的实验分组。

```text
datamind experiment variant restore <variant_id> [OPTIONS]
```

| 参数           | 类型   | 必需 | 默认值   | 说明                  |
|----------------|--------|------|----------|-----------------------|
| `<variant_id>` | 字符串 | 是   | `—`      | 实验分组 ID           |
| `--format`     | 字符串 | 否   | `"text"` | 输出格式：text / json |

权限：`experiment.delete` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/experiment/variant/restore.py)
