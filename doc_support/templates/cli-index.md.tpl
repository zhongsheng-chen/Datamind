# 命令索引

按命令组查阅参数、默认值与权限。完整操作流程见各组对应指南，生命周期见[状态与权限](../reference/states-permissions.md)。

## 使用命令

```bash
datamind --help
datamind --version
datamind <命令组> <命令> --help
```

`--help` 无需登录即可查看。认证启用时，资源命令使用本地 CLI 登录凭据，请先运行 `datamind login`。调用 HTTP 接口时，需按[在线预测](../guides/online-prediction.md)获取访问令牌。

## 命令分组

| 命令组 | 说明 |
| --- | --- |
${groups}

## 阅读约定

命令语法中，`<参数名>` 为位置参数，方括号表示可省略的参数。参数表中的 `null` 表示未指定；此时是否使用配置值，以参数说明为准。标记“可重复”的选项可多次传入。

## 自动化输出

支持 `--format` 的命令可选择 `text` 或 `json` 输出，默认格式见各命令的参数表。人工操作使用文本输出；脚本可使用 JSON 读取资源 ID、状态和其他字段。

模型注册的 JSON 输出包含以下关键字段，模型 ID 和版本 ID 可用于后续查询与部署：

```json
{
  "name": "scorecard-demo",
  "model_id": "<model_id>",
  "version": "1.0.0",
  "version_id": "<version_id>",
  "action": "created"
}
```

`action` 表示注册结果：`created` 为新建，`revised` 为更新，`unchanged` 为未发生变更。

各命令的输出结构不同。例如，`datamind model list` 返回数组，`datamind model show` 返回对象。列表的分页参数控制返回范围，输出不一定包含总数或分页信息。

脚本应检查退出码，并解析完整的 JSON 输出。命令失败时返回非零退出码，日志可能写入标准错误或日志文件。

> **提示**
>
> `init`、`login`、`logout`、`whoami` 和进程启动命令不支持 `--format`。用户创建与密码重置需要交互输入密码，选择 JSON 输出不会取消交互。
