# 身份管理命令

<span class="cli-reference"></span>

操作流程见[访问控制](../guides/access-control.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

<a id="datamind-user-create"></a>

## `user create`

创建用户。

部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。

```text
datamind user create <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--display-name` | 字符串 | 否 | `null` | 用户显示名称 |
| `--email` | 字符串 | 否 | `null` | 用户邮箱 |
| `--employee-number` | 字符串 | 否 | `null` | 工号 |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--department` | 字符串 | 否 | `null` | 所属部门名称 |
| `--department-id` | 字符串 | 否 | `null` | 所属部门 ID |
| `--role` | 字符串（可重复） | 否 | `null` | 初始角色，可重复指定 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/create.py)

<a id="datamind-user-list"></a>

## `user list`

列出用户。

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

权限：`identity.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/list.py)

<a id="datamind-user-show"></a>

## `user show`

查看用户。

```text
datamind user show <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--include-deleted` | 布尔 | 否 | `false` | 允许查看已删除用户 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/show.py)

<a id="datamind-user-update"></a>

## `user update`

更新已指定的组织资料字段，未指定字段保留原值。

部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。

```text
datamind user update <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--employee-number` | 字符串 | 否 | `null` | 工号，空字符串表示清空 |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID，空字符串表示清空 |
| `--department` | 字符串 | 否 | `null` | 所属部门名称 |
| `--department-id` | 字符串 | 否 | `null` | 所属部门 ID，空字符串表示清空 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/update.py)

<a id="datamind-user-enable"></a>

## `user enable`

启用用户。

```text
datamind user enable <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/enable.py)

<a id="datamind-user-disable"></a>

## `user disable`

停用用户。

```text
datamind user disable <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/disable.py)

<a id="datamind-user-reset-password"></a>

## `user reset-password`

重置用户密码。

```text
datamind user reset-password <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/reset.py)

<a id="datamind-user-delete"></a>

## `user delete`

逻辑删除用户。

```text
datamind user delete <username> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/user/delete.py)

<a id="datamind-organization-list"></a>

## `organization list`

列出机构。

```text
datamind organization list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-organization-create"></a>

## `organization create`

创建机构。

```text
datamind organization create <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 机构名称 |
| `--code` | 字符串 | 否 | `null` | 机构业务编码（可选） |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-organization-update"></a>

## `organization update`

修改机构编码和名称。

```text
datamind organization update <organization> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<organization>` | 字符串 | 是 | `—` | 机构名称或 ID |
| `--code` | 字符串 | 否 | `null` | 机构编码 |
| `--name` | 字符串 | 是 | `—` | 机构名称 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-organization-delete"></a>

## `organization delete`

删除机构。

机构仍有关联用户或部门时不能删除，须先调整用户归属并删除所属部门。
输出：删除前的机构信息。

```text
datamind organization delete <organization> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<organization>` | 字符串 | 是 | `—` | 机构名称或 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-organization-enable"></a>

## `organization enable`

启用机构。

停用后保留已有用户归属和历史记录，禁止向该机构及其下级部门新增关联。
重新启用不会改变下级部门独立设置的启用状态。
输出：机构信息及启用状态。

```text
datamind organization enable <organization> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<organization>` | 字符串 | 是 | `—` | 机构名称或 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-organization-disable"></a>

## `organization disable`

停用机构。

停用后保留已有用户归属和历史记录，禁止向该机构及其下级部门新增关联。
重新启用不会改变下级部门独立设置的启用状态。
输出：机构信息及启用状态。

```text
datamind organization disable <organization> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<organization>` | 字符串 | 是 | `—` | 机构名称或 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-list"></a>

## `department list`

列出部门。

```text
datamind department list [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-create"></a>

## `department create`

创建部门。

--parent 与 --parent-id 只能指定一个，两者均省略时创建根部门。
上级部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。

```text
datamind department create <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 部门名称 |
| `--code` | 字符串 | 否 | `null` | 部门业务编码（可选） |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--parent` | 字符串 | 否 | `null` | 同一机构内的上级部门名称 |
| `--parent-id` | 字符串 | 否 | `null` | 同一机构内的上级部门 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-update"></a>

## `department update`

修改部门编码、名称与上级部门。

--parent 与 --parent-id 只能指定一个，两者均省略时移至根部门。
上级部门重名时，可使用 / 分隔的完整部门路径，例如“人力资源部/招聘组”。

```text
datamind department update <department> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<department>` | 字符串 | 是 | `—` | 部门名称、完整路径或 ID |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--code` | 字符串 | 否 | `null` | 部门编码 |
| `--name` | 字符串 | 是 | `—` | 部门名称 |
| `--parent` | 字符串 | 否 | `null` | 同一机构内的上级部门名称 |
| `--parent-id` | 字符串 | 否 | `null` | 同一机构内的上级部门 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-delete"></a>

## `department delete`

删除部门。

按名称或完整路径选择部门时，须指定所属机构；也可直接使用部门 ID。
部门仍有关联用户或下级部门时不能删除，须先调整用户归属并移动或删除下级部门。
输出：删除前的部门信息。

```text
datamind department delete <department> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<department>` | 字符串 | 是 | `—` | 部门名称、完整路径或 ID |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-enable"></a>

## `department enable`

启用部门。

停用后保留已有用户归属和历史记录，禁止向该部门及其下级部门新增关联。
重新启用不会改变下级部门独立设置的启用状态。
输出：部门信息及启用状态。

```text
datamind department enable <department> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<department>` | 字符串 | 是 | `—` | 部门名称、完整路径或 ID |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-department-disable"></a>

## `department disable`

停用部门。

停用后保留已有用户归属和历史记录，禁止向该部门及其下级部门新增关联。
重新启用不会改变下级部门独立设置的启用状态。
输出：部门信息及启用状态。

```text
datamind department disable <department> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<department>` | 字符串 | 是 | `—` | 部门名称、完整路径或 ID |
| `--organization` | 字符串 | 否 | `null` | 所属机构名称 |
| `--organization-id` | 字符串 | 否 | `null` | 所属机构 ID |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/organization.py)

<a id="datamind-role-create"></a>

## `role create`

创建角色。

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

参数组合：

- `--all-permissions` 与 `--permission` 不能同时指定。

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/create.py)

<a id="datamind-role-list"></a>

## `role list`

列出角色。

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

权限：`identity.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/list.py)

<a id="datamind-role-show"></a>

## `role show`

查看角色。

```text
datamind role show <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |
| `--include-deleted` | 布尔 | 否 | `false` | 允许查看已删除角色 |
| `--format` | 字符串 | 否 | `"text"` | 输出格式：text / json |

权限：`identity.read` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/show.py)

<a id="datamind-role-enable"></a>

## `role enable`

启用角色。

```text
datamind role enable <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/enable.py)

<a id="datamind-role-disable"></a>

## `role disable`

停用角色。

```text
datamind role disable <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/disable.py)

<a id="datamind-role-grant"></a>

## `role grant`

授予用户角色。

```text
datamind role grant <username> <role_name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `<role_name>` | 字符串 | 是 | `—` | 角色名称 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/grant.py)

<a id="datamind-role-revoke"></a>

## `role revoke`

撤销用户角色。

```text
datamind role revoke <username> <role_name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<username>` | 字符串 | 是 | `—` | 登录用户名 |
| `<role_name>` | 字符串 | 是 | `—` | 角色名称 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/revoke.py)

<a id="datamind-role-delete"></a>

## `role delete`

逻辑删除角色。

```text
datamind role delete <name> [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `<name>` | 字符串 | 是 | `—` | 角色名称 |
| `--reason` | 字符串 | 否 | `null` | 删除原因 |
| `--yes` | 布尔 | 否 | `false` | 跳过确认 |

权限：`identity.manage` · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/role/delete.py)
