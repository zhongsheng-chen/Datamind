# 初始化与认证

相关说明见[对应文档](../getting-started/configuration.md)，状态限制见[状态与权限](../reference/states-permissions.md)。

`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。

## datamind init

初始化系统，已初始化时跳过。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/init.py)

```text
datamind init [OPTIONS]
```

无额外参数。


输入校验（命令函数内的显式检查）：

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

输入校验（命令函数内的显式检查）：

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

将数据库升级到最新迁移版本。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)

```text
datamind db upgrade [OPTIONS]
```

无额外参数。


## datamind db downgrade

将数据库降级到指定迁移版本.

指定迁移版本号可降级到对应版本，使用 -1 回退一步，使用 base 撤销全部迁移。

注意：
    降级可能删除表或数据，执行前应完成备份。

权限：无需资源权限

[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/db.py)

```text
datamind db downgrade [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--revision/-r` | 字符串 | 是 | `—` | 降级目标版本 |
| `--yes/-y` | 布尔 | 否 | `false` | 跳过降级确认 |
