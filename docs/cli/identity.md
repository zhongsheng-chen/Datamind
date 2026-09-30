# 用户与角色 CLI

操作流程见[使用指南](../guides/access-control.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind user create

创建用户。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/create.py)

```text
datamind user create <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--display-name` | 字符串 | 否 | `null` | 用户显示名称 |
| `--email` | 字符串 | 否 | `null` | 用户邮箱 |
| `--role` | 字符串（可重复） | 否 | `null` | 初始角色，可重复指定 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

## datamind user list

列出用户。

权限：`identity.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/list.py)

```text
datamind user list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--status` | 字符串 | 否 | `null` | 用户状态：active / disabled / locked |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除用户 |
| `--limit` | 整数 | 否 | `100` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

## datamind user show

查看用户。

权限：`identity.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/show.py)

```text
datamind user show <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--include-deleted` | 布尔 | 否 | `false` | 允许查看已删除用户 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind user enable

启用用户。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/enable.py)

```text
datamind user enable <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

## datamind user disable

停用用户。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/disable.py)

```text
datamind user disable <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

## datamind user reset-password

重置用户密码。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/reset.py)

```text
datamind user reset-password <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

## datamind user delete

逻辑删除用户。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/delete.py)

```text
datamind user delete <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |

## datamind role create

创建角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/create.py)

```text
datamind role create <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |
| `--permission` | 字符串（可重复） | 否 | `null` | 权限标识，可重复指定 |
| `--all-permissions` | 布尔 | 否 | `false` | 授予全部权限 |
| `--description` | 字符串 | 否 | `null` | 角色说明 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --all-permissions 与 --permission 不能同时指定

## datamind role list

列出角色。

权限：`identity.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/list.py)

```text
datamind role list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--status` | 字符串 | 否 | `null` | 角色状态：active / inactive |
| `--include-deleted` | 布尔 | 否 | `false` | 包含已删除角色 |
| `--limit` | 整数 | 否 | `100` | 返回记录数量限制 |
| `--offset` | 整数 | 否 | `0` | 分页偏移量 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

## datamind role show

查看角色。

权限：`identity.read`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/show.py)

```text
datamind role show <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |
| `--include-deleted` | 布尔 | 否 | `false` | 允许查看已删除角色 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

输入校验：

- --format 只支持 text 或 json

## datamind role enable

启用角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/enable.py)

```text
datamind role enable <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |

## datamind role disable

停用角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/disable.py)

```text
datamind role disable <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |

## datamind role grant

授予用户角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/grant.py)

```text
datamind role grant <username> <role_name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `<role_name>` | 字符串 | 是 | `—` | 角色名称 |

## datamind role revoke

撤销用户角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/revoke.py)

```text
datamind role revoke <username> <role_name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `<role_name>` | 字符串 | 是 | `—` | 角色名称 |

## datamind role delete

逻辑删除角色。

权限：`identity.manage`

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/delete.py)

```text
datamind role delete <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |
