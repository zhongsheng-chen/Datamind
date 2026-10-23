# 命令索引

<span class="cli-reference cli-index"></span>

按命令组查阅 Datamind 命令的参数、默认值和权限说明。

## 命令分组

| 命令组 | 命令 | 用途 |
| --- | --- | --- |
${groups}

## 查看帮助

查看全部命令和版本信息：

```bash
datamind --help
datamind --version
```

在命令组或具体命令后添加 `--help`，查看可用命令、参数及使用说明：

```bash
datamind model --help
datamind model register --help
datamind experiment variant --help
datamind login --help
```

查看帮助无需登录。启用认证后，执行受保护的命令前需运行 `datamind login`。登录方式见[认证命令](auth.md)，权限说明见[状态与权限](../reference/states-permissions.md)。

## 参数约定

- `<参数名>` 表示位置参数，使用时替换为实际值。
- 方括号表示可省略，例如 `[<name>]`；`[OPTIONS]` 表示命令支持的选项。
- 参数表中的 `null` 表示未指定值，实际行为以参数说明为准。
- 标记“可重复”的选项可多次传入。

## 输出格式

支持 `--format` 的命令可选择 `text` 或 `json` 输出，默认格式见各命令的参数表。例如：

```bash
datamind model list --format json
```

JSON 输出便于脚本读取资源 ID、状态等字段，具体结构见各命令的输出说明。

> **说明**
>
> `init`、`login`、`logout`、`whoami` 和进程启动命令不支持 `--format`。创建用户或重置密码时仍需交互输入密码，选择 JSON 输出不会跳过此步骤。
