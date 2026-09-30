# 初始化、认证与数据库 CLI

操作流程见[使用指南](../getting-started/configuration.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind init

初始化系统，已初始化时跳过。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/init.py)

```text
datamind init [OPTIONS]
```

无额外参数。


输入校验：

- Datamind 已经完成初始化
- 未配置管理员密码，请设置 DATAMIND_INIT_ADMIN_PASSWORD

## datamind login

使用本地用户名和密码登录。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/login.py)

```text
datamind login [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--username` | 字符串 | 否 | `null` | 登录用户名 |

输入校验：

- 登录服务未返回有效凭据

## datamind logout

退出当前登录。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/logout.py)

```text
datamind logout [OPTIONS]
```

无额外参数。


## datamind whoami

查看当前登录用户。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/whoami.py)

```text
datamind whoami [OPTIONS]
```

无额外参数。


## datamind db upgrade

将数据库升级到当前安装包的最新版本。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)

```text
datamind db upgrade [OPTIONS]
```

无额外参数。
