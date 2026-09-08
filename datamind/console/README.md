# 内网管理控制台

管理控制台是独立于评分服务部署的只读 BentoML 服务，用于查看模型、
模型版本、部署、运行实例、API 调用、决策记录、实验和审计记录。

从源码运行时，先在项目根目录构建控制台。需要 Node.js 22.12+（22 系列）
或 24+，推荐 Node.js 24 LTS：

```bash
npm ci
npm run build:console
```

源码保留在 `datamind/console/static/`，构建产物位于
`datamind/console/dist/`。运行服务只读取构建产物，不回退到源码；
缺少构建产物时，页面会返回明确的构建提示。

开发时可以在另一个终端运行 `npm run watch:console`，保存源码后自动
重新构建，再刷新控制台页面。`datamind console run --reload` 负责 Python
代码重载，不代替前端构建。

发布 Python 安装包前也需要执行上述构建命令，然后运行
`python -m pip wheel --no-deps .`。安装包包含 HTML、带内容哈希的 JS/CSS
及构建清单，运行环境无需 Node.js。源码发行包同时包含前端源码与已构建
资源；缺少构建产物时，打包会中止并提示构建命令。

HTML 使用 `Cache-Control: no-cache` 配合 ETag 校验；带内容哈希的资源
使用长期缓存。不要手动修改生成文件或为源码引用添加日期版本号。
每次发布先完成构建，再部署整套产物；已有页面可能仍引用旧资源，反向代理
或 CDN 应保留上一版本的哈希资源，避免发布期间出现 404。

运行控制台测试前执行 `npm run build:console`；`make test` 会自动安装
锁定的前端依赖并构建。前端源码约定与实际构建资源的访问、缓存分别验证。

启动前还需要完成数据库迁移、系统初始化并启用 LOCAL 认证：

```dotenv
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-secure-random-secret

DATAMIND_CONSOLE_HOST=127.0.0.1
DATAMIND_CONSOLE_PORT=8701
```

预发布和生产环境还必须配置允许访问 LOCAL 认证的内网网段。启动服务：

```bash
datamind console run \
  --host 0.0.0.0 \
  --port 8701
```

本地使用时可以直接执行 `datamind console run`。命令未指定网络参数时，
读取 `DATAMIND_CONSOLE_HOST` 和 `DATAMIND_CONSOLE_PORT`，未配置则监听
`127.0.0.1:8701`。底层 BentoML 服务入口仍可用于容器和进程管理器。

浏览器访问 `http://localhost:8701`，使用 `datamind init` 创建的管理员或
其他本地账户登录。页面根据用户权限自动隐藏无权查看的数据区块：

- `model.read`：模型资产和模型版本
- `deployment.read`：部署记录
- `runtime.read`：运行实例
- `request.read`：API 调用和决策记录
- `experiment.read`：实验
- `audit.read`：审计记录
- `data.export`：导出有权查看的查询结果

概览展示最近 24 小时 API 调用量、调用成功率、P95 响应耗时、成功与失败
调用趋势，以及模型调用概况。模型调用概况分别展示全部模型的最近 24 小时
表现与历史累计调用量；影子执行不重复计入 API 调用量。

列表页面显示查询结果总数，支持排序、关键词筛选、每页条数设置、页码跳转和
CSV 导出。每页可以显示 10、20、50 或 100 条记录。
可以导出当前筛选与排序条件下的全部记录，也可以跨页选择记录后仅导出
已选项。单次最多导出 10000 条记录，并写入审计记录。

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
