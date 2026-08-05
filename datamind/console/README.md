# 内网管理控制台

管理控制台是独立于评分服务部署的只读 BentoML 服务，用于查看模型、
模型版本、部署、运行实例、API 调用、决策记录、实验和审计记录。

启动前需要完成数据库迁移、系统初始化并启用 LOCAL 认证：

```dotenv
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-secure-random-secret
```

预发布和生产环境还必须配置允许访问 LOCAL 认证的内网网段。启动服务：

```bash
datamind console run \
  --host 0.0.0.0 \
  --port 3100
```

本地使用时可以直接执行 `datamind console run`，默认监听
`127.0.0.1:3100`。底层 BentoML 服务入口仍可用于容器和进程管理器。

浏览器访问 `http://localhost:3100`，使用 `datamind init` 创建的管理员或
其他本地账户登录。页面根据用户权限自动隐藏无权查看的数据区块：

- `model.read`：模型资产和模型版本
- `deployment.read`：部署记录
- `runtime.read`：运行实例
- `request.read`：API 调用和决策记录
- `experiment.read`：实验
- `audit.read`：审计记录

页面通过 SSE 接收数据库提交后的变更通知，并自动刷新只读快照。事件
使用 Outbox 游标支持断线恢复；实时连接不可用时，每 30 秒自动更新
作为降级机制。切换到后台时暂停连接和查询，重新回到页面后立即同步。
也可以使用页面中的“刷新数据”按钮手动更新。

首次启用实时更新前需要升级数据库：

```bash
alembic upgrade head
```

生产环境应在控制台服务前配置 HTTPS 反向代理，并关闭 SSE 路径的响应
缓冲、设置足够长的读取超时。应用已经为事件流返回
`X-Accel-Buffering: no`。访问令牌和刷新令牌仅保存在 HttpOnly、
SameSite=Strict Cookie 中，不暴露给页面脚本。
