# 用户、角色与认证

用户通过认证登录后，按角色权限查询资源或执行管理操作。CLI、HTTP 与 Console 分别登录，各自管理凭据。

## 初始化与启用认证

`datamind init` 创建内置 administrator 角色与首个管理员。默认凭据和初始化前自定义配置见[配置与初始化](../getting-started/configuration.md)。通过 `DATAMIND_AUTH_ENABLED=true` 启用认证，配置非空签名密钥并在预测服务（`Runtime`）、Console、CLI 与 Worker 之间保持一致。`staging` 和 `production` 必须启用认证，`LOCAL` 登录还必须设置 `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS`，例如仅本机开发验证可用 `["127.0.0.0/8"]`。正式部署填写真实可信来源网段，不能只打开认证而省略网络配置。

## CLI 登录

```bash
datamind login
datamind whoami
datamind logout
```

login 交互读取账户凭据并保存本地登录状态。不要把本地 CLI 凭据文件加入仓库或共享给其他用户。退出后重新执行受保护资源命令需要重新认证。

## 创建用户和角色

以管理员身份创建只读角色和用户：

```bash
datamind role create model-reader --permission model.read --permission deployment.read
datamind user create analyst --display-name 分析员
datamind role grant analyst model-reader
datamind user show analyst --format json
```

用户创建交互设置密码。重复 grant 不用于修改角色权限。需要变更权限时在 Console 编辑角色，或创建新角色再授予。当前 CLI 的角色命令不提供任意更新参数。撤销角色和停用账户：

```bash
datamind role revoke analyst model-reader
datamind user disable analyst
datamind user enable analyst
datamind user reset-password analyst
```

密码重置通过交互输入。用户、角色和凭据的当前有效性由服务端检查，不能把尚未到期的 JWT 理解为权限永远不变。完整参数见[用户与角色 CLI](../cli/identity.md)。

内置初始化管理员不能被停用或删除，其固定身份和 administrator 角色受到保护。内置角色不能停用或删除。最后一个有效 administrator 也不能被移除。当前登录用户的危险自身操作会被拒绝。管理员密码可以通过账户密码管理调整。

## HTTP 与 Console

HTTP 使用 POST `/auth/login`，直接发送 `{"username":"…","password":"…"}`，后续请求使用 Bearer `access_token`。`/auth/refresh` 使用 `refresh_token` 并轮换凭据。`/auth/logout` 撤销刷新凭据。访问令牌与刷新令牌用途不同，客户端需保存刷新响应中的新令牌。接口见[Runtime API](../reference/runtime-api.md)。

Console 登录页面建立自身会话，可在用户与角色页面管理账户和授权，截图与步骤见[Console 手册](console.md)。页面按钮按权限显示，服务端仍对每次操作授权。

## 失败处理

| 现象 | 检查 |
| --- | --- |
| 401 | 缺少或过期令牌、无效凭据、用户状态、签名密钥 |
| 403 | 当前角色缺少实际操作权限 |
| 登录被锁定 | 本地认证失败次数和锁定时间配置 |
| 无法停用用户或撤销角色 | 内置账户、自身操作、最后管理员保护 |

例如 model-reader 可以查询模型，但不能注册或删除。应授予确切的 `model.write` 或 `model.delete`，而非仅隐藏错误提示。完整权限与对应资源见[状态与权限](../reference/states-permissions.md)。本地认证的 break-glass-only 与允许网络配置属于专门的访问约束，部署前按[配置表](../reference/configuration.md)和认证测试验证实际入口。
