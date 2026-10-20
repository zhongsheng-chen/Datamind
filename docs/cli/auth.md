# 认证命令

<span class="cli-reference"></span>

操作流程见[配置与初始化](../getting-started/configuration.md#cli-登录)，状态说明见[状态与权限](../reference/states-permissions.md)。

<a id="datamind-login"></a>

## `login`

使用本地用户名和密码登录。

```text
datamind login [OPTIONS]
```

| 参数         | 类型   | 必需 | 默认值 | 说明       |
|--------------|--------|------|--------|------------|
| `--username` | 字符串 | 否   | `null` | 登录用户名 |

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/login.py)

<a id="datamind-logout"></a>

## `logout`

退出当前登录。

```text
datamind logout [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/logout.py)

<a id="datamind-whoami"></a>

## `whoami`

查看当前登录用户。

```text
datamind whoami [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/auth/whoami.py)
