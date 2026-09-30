# 初始化、认证与数据库 CLI

任务步骤见[使用指南](../getting-started/configuration.md)。本页列出当前命令、全部显式参数、默认值、权限和入口校验；服务层的状态转换见[状态与权限](../reference/states-permissions.md)。

位置参数用大写表示；`null` 表示未指定。布尔开关默认关闭时，传入选项将其开启。重复选项和路径要求以类型/说明为准。所有命令还支持 `--help`。

## datamind init

初始化系统，已初始化时跳过.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/init.py)。

```text
datamind init [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |

入口校验与错误：

- Datamind 已经完成初始化
- 未配置管理员密码，请设置 DATAMIND_INIT_ADMIN_PASSWORD

## datamind login

使用本地用户名和密码登录.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/login.py)。

```text
datamind login [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--username` | text | 否 | `null` | 登录用户名 |

入口校验与错误：

- 登录服务未返回有效凭据

## datamind logout

退出当前登录.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/logout.py)。

```text
datamind logout [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |

## datamind whoami

查看当前登录用户.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/whoami.py)。

```text
datamind whoami [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |

## datamind db upgrade

将数据库升级到当前安装包的最新版本.

权限：入口不要求资源权限；认证和初始化条件见对应指南。

[当前实现](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)。

```text
datamind db upgrade [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
