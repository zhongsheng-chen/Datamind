# 管理控制台

操作流程见[服务管理](../deployment/processes.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

## datamind console run

启动管理控制台。

```text
datamind console run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--host` | 字符串 | 否 | `null` | 监听地址，默认 127.0.0.1。不能为空 |
| `--port` | 整数 | 否 | `null` | 监听端口，默认 8701。必须在 1 到 65535 之间 |
| `--startup-timeout` | 整数范围 | 否 | `null` | 等待控制台就绪的最长时间（秒），默认 120 |
| `--reload` | 布尔 | 否 | `false` | 代码变更时自动重载 |
| `--verbose` | 布尔 | 否 | `false` | 显示 BentoML 警告和信息日志 |

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/console/run.py)

## datamind console healthcheck

检查管理控制台是否就绪。

```text
datamind console healthcheck [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/console/healthcheck.py)
