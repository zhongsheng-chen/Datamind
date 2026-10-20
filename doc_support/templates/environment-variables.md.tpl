# 环境变量

本页按功能列出环境变量、类型、默认值及说明。首次配置请参阅[配置与初始化](../getting-started/configuration.md)。

配置优先级从高到低为：显式传入的参数、环境变量、工作目录中的 `.env` 文件、默认值。修改环境变量或 `.env` 文件后，需重启相关进程。

填写环境变量时，请注意：

- 各功能分组使用独立的变量前缀，例如 `DATAMIND_STORAGE_MINIO_`。
- 列表值使用 JSON 格式，例如 `["127.0.0.0/8"]`。
- 相对路径以进程的工作目录为基准。

${sections}
## 使用说明

- **运行环境**：`DATAMIND_ENVIRONMENT` 统一指定资源管理、预测服务、控制台和认证策略使用的环境，必须显式配置。
- **数据库**：`DATAMIND_DATABASE_URL` 使用 PostgreSQL 异步连接地址，以 `postgresql+asyncpg://` 开头。
- **文件存储**：使用本地存储时，各模型加载进程需能访问同一模型文件目录。使用 MinIO 时，`DATAMIND_STORAGE_MINIO_ENDPOINT` 不包含协议前缀，是否启用 TLS 由 `DATAMIND_STORAGE_MINIO_SECURE` 指定。
- **任务队列**：预测服务与任务 Worker 需使用相同的 `DATAMIND_TASK_QUEUE_BROKER_URL` 和队列名称。`DATAMIND_TASK_QUEUE_BATCH_QUEUE` 与 `DATAMIND_TASK_QUEUE_SHADOW_QUEUE` 必须不同。
- **任务执行**：`DATAMIND_TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS` 应覆盖任务运行时长。`DATAMIND_TASK_QUEUE_BATCH_CHUNK_SIZE` 控制批量任务的分片大小，与任务 Worker 的进程并发数分别设置。
- **时区**：`DATAMIND_TIMEZONE` 为应用默认时区，用于日志、命令行显示和未带时区的时间输入解析，默认为 `Asia/Shanghai`。内部时间统一转换为 UTC。
- **审计**：`DATAMIND_AUDIT_FAILURE_MODE` 为 `open` 时，审计失败后业务继续执行；为 `closed` 时，阻止受审计操作。该变量控制审计失败后的处理方式，是否启用审计由 `DATAMIND_AUDIT_ENABLED` 决定。

生产环境的部署要求请参阅[生产部署](../deployment/production.md)。
