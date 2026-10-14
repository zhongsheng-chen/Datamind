# 运行实例

操作流程见[本地部署](../deployment/local.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

## datamind runtime list

查询部署运行状态列表。

```text
datamind runtime list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--desired-status` | 字符串 | 否 | `null` | 按期望运行状态过滤，可选值：loaded / unloaded。只支持 loaded 或 unloaded |
| `--limit` | 整数 | 否 | `10` | 返回记录数量限制。必须大于 0 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量。不能小于 0 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`runtime.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/list.py)

## datamind runtime show

查看部署运行状态。

```text
datamind runtime show <deployment_id> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<deployment_id>` | 字符串 | 是 | `—` | 部署 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`runtime.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/runtime/show.py)
