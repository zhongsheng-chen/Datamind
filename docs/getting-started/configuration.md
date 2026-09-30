# 配置与初始化

安装完成后，先配置数据库、存储和认证，再执行迁移与初始化。CLI、Runtime、Console 和任务 Worker 应使用同一部署环境的配置。

## 本地配置

在运行命令的工作目录创建 `.env`：

```dotenv
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DATAMIND_STORAGE_TYPE=local
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
```

替换数据库连接地址与签名密钥，提前创建数据库。默认使用本地制品存储。跨进程共享方式见[生产部署](../deployment/production.md)。环境变量和配置分组见[配置 Reference](../reference/configuration.md)。

## 数据库迁移与系统初始化

```bash
datamind db upgrade
datamind init
```

默认管理员用户名和密码均为 `admin`。如需自定义，请在执行 `datamind init` 前将以下配置写入 `.env`：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=replace-with-a-strong-password
```

迁移负责创建或更新数据库结构，初始化负责创建管理员及内置角色，两者不能相互替代。

## CLI 登录

```bash
datamind login --username admin
datamind whoami
```

按提示输入初始化时设置的密码。CLI 将保存登录凭据。HTTP 调用需要单独取得访问令牌。用户与权限见[访问控制指南](../guides/access-control.md)。

下一步按照[快速上手](quickstart.md)注册模型、部署并发起预测。
