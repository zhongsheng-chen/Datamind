# 预测服务

操作流程见[本地部署](../deployment/local.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

## datamind service run

启动 Datamind 预测服务。

```text
datamind service run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | 字符串 | 否 | `null` | 监听地址，默认 0.0.0.0。不能为空 |
| `--port` | 整数 | 否 | `null` | 监听端口，默认 8700。必须在 1 到 65535 之间 |
| `--reload` | 布尔 | 否 | `false` | 代码变更后自动重载 |
| `--verbose` | 布尔 | 否 | `false` | 显示 BentoML 警告和信息日志 |

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/service/run.py)

## datamind service healthcheck

检查预测服务是否就绪。

```text
datamind service healthcheck [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/service/healthcheck.py)
