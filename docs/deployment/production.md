# 生产部署

Runtime、Console、CLI 与任务 Worker 必须统一服务环境、数据库、存储、Broker 和认证设置。基础配置见[配置 Reference](../reference/configuration.md)，容器入口见[Docker](docker.md)。

## 拓扑与共享状态

PostgreSQL 持久化资源、请求、执行和任务状态，必须使用持久卷或托管数据库。Redis 用作批量与影子消息 Broker。MinIO 用于共享制品。本地存储也可使用，但每个加载模型的进程必须访问相同路径及内容。

多实例 Runtime 通过同一数据库中的运行控制目标协调，模型仍各自在进程内加载，因此内存需求随进程数量增长。负载均衡器转发在线请求。Console 可独立运行。任务 Worker 使用 `all`、`batch` 或 `shadow` 分角色扩容，所有角色使用相同队列名与 Broker。不要为每个实例创建相互隔离的模型目录。

## 上线步骤

1. 准备 PostgreSQL、共享存储及 Redis，确认连接、持久卷、网络和容量。
2. 固定应用版本及框架镜像，设置 `DATAMIND_SERVICE_ENVIRONMENT=production`，配置认证签名密钥、初始化管理员密码及 LOCAL 登录允许网段 `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS`（JSON 数组）。production/staging 要求认证开启且允许网段非空。使用部署系统的 Secret 注入凭据，限制 `.env` 的读取权限。
3. 在一个管理进程执行 `datamind db upgrade`，再按[初始化指南](../getting-started/configuration.md)执行 `datamind init`。迁移应在应用滚动更新前完成，避免多个进程并发迁移。
4. 启动 Runtime、Console 和任务 Worker。Console 默认仅监听本机，经过反向代理公开时配置监听地址与 TLS。代理需要保留认证头和正确的请求来源设置。
5. 检查 `/health`、`/ready`，注册并激活模型，启用部署，再检查 `datamind runtime list --format json` 和一次真实预测。
6. 提交小批次并查询到终态，检查 shadow 执行。确认应用日志、审计、队列与存储没有错误后放量。

签名密钥应在各应用进程间一致。默认 admin/admin 适合首次本地体验，正式部署在初始化前自定义密码。已有账户通过密码重置管理，重复修改初始化配置不会替代账户管理。

## 探针、容量与监控

`/health` 用于判断进程是否响应，`/ready` 用于数据库等依赖检查。二者均不能替代部署加载验证。分别监控在线延迟和失败率、Runtime 心跳与加载错误、批次进度与失败率、影子任务积压、Redis 内存、数据库连接与存储空间。

数据库连接池属于进程：多实例、多服务 Worker 和 Celery 并发共同消耗连接。调整 `DATAMIND_DATABASE_POOL_SIZE`、`MAX_OVERFLOW` 时按所有进程总量计算。模型加载也会占用各进程内存。批量 `chunk_size` 是任务切片大小，Worker `concurrency` 是执行进程并发，二者不等价。

任务执行时间应小于 Redis `visibility_timeout_seconds` 的合理上限，避免长任务过早重新投递。任务消息持久化和数据库任务状态属于不同层次，数据库中的 queued 状态不保证消息已经被消费。

## 备份与恢复

共同备份 PostgreSQL、制品桶或模型目录、应用版本与部署配置。只备份数据库无法恢复模型文件，只备份 MinIO 无法恢复版本、路由和实验关系。备份过程应覆盖同一业务时间点，并在隔离环境实际恢复验证。

恢复时先准备基础设施与凭据，再还原数据库和制品，用兼容的应用版本启动。检查 migration head、制品摘要、部署运行状态及预测。不要直接编辑数据库状态来修复加载问题。

## 升级和回滚

升级前记录当前镜像、数据库版本和备份。在测试环境验证迁移及旧模型兼容性，再迁移、滚动替换应用并执行预测与队列探测。生产镜像使用固定版本标签，框架依赖须与模型匹配。

应用回滚和数据库回滚分开评估。新迁移可能不兼容旧应用。当前 CLI 只提供 `db upgrade`。需要数据恢复时使用已经验证的备份与恢复方案，不能假设切换旧镜像会自动回退数据库。模型发布回滚见[金丝雀发布](canary.md)。

## 常见故障

| 现象 | 检查顺序 |
| --- | --- |
| ready 失败 | 数据库 URL、网络、权限、迁移和连接池 |
| Deployment active，但预测失败 | 模型与版本状态、实际 Runtime 状态、制品可读性、框架依赖和服务环境 |
| 批次长时间 queued | Broker 连接、队列名、Worker 角色、Worker 日志和任务投递结果 |
| 影子没有结果 | shadow 开关、影子路由比例/规则/时间、shadow Worker、执行记录错误 |
| 401 / 403 | 令牌有效性、用户启停、角色权限及签名密钥一致性 |
| 制品清理失败 | 存储凭据、对象是否存在、运行引用、purge_failed 记录 |

调查时保留 request_id、batch_id、deployment_id 和时间范围，通过 Console 请求、执行与审计记录定位。审计 `failure_mode=closed` 会在审计写入失败时阻止操作，须同时排查审计依赖。
