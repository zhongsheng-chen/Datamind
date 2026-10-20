# 数据库命令

<span class="cli-reference"></span>

操作流程见[配置与初始化](../getting-started/configuration.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

<a id="datamind-db-upgrade"></a>

## `upgrade`

将数据库升级到最新迁移版本。

```text
datamind db upgrade [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)

<a id="datamind-db-downgrade"></a>

## `downgrade`

将数据库降级到指定迁移版本。

指定迁移版本号可降级到对应版本，使用 -1 回退一步，使用 base 撤销全部迁移。

> **注意**
>
> 降级可能删除表或数据，执行前应完成备份。

```text
datamind db downgrade [OPTIONS]
```

| 参数            | 类型   | 必需 | 默认值  | 说明         |
|-----------------|--------|------|---------|--------------|
| `--revision/-r` | 字符串 | 是   | `—`     | 降级目标版本 |
| `--yes/-y`      | 布尔   | 否   | `false` | 跳过降级确认 |

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)
