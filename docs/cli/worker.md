# 任务 Worker

操作流程见[本地部署](../deployment/local.md)，状态说明见[状态与权限](../reference/states-permissions.md)。

## datamind worker run

启动任务 Worker。

```text
datamind worker run [OPTIONS]
```

| 参数 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--role` | all/batch/shadow | 否 | `null` | 处理的任务类型，默认使用配置值 |
| `--concurrency` | 整数范围 | 否 | `null` | Worker 并发数，默认使用配置值 |

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/worker/run.py)

## datamind worker healthcheck

检查任务 Worker 是否就绪。

```text
datamind worker healthcheck [OPTIONS]
```

权限：无需资源权限 · [源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/cli/worker/healthcheck.py)
