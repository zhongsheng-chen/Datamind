# 访问控制

Datamind 基于用户角色控制资源访问和操作权限。命令行、HTTP 接口和管理控制台独立登录，分别管理登录凭据。

<a id="初始化与启用认证"></a>

## 配置认证

按照[配置与初始化](../getting-started/configuration.md)完成数据库迁移和系统初始化，然后在 `.env` 文件中启用认证并设置签名密钥：

```dotenv
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
```

将示例值替换为随机生成的密钥。命令行、预测服务、管理控制台和任务 Worker 须使用同一签名密钥。

预发布和生产环境必须启用认证，并配置允许本地账号登录的来源网段：

```dotenv
DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS=["<可信来源网段>"]
```

> **说明**
>
> 开发环境可按需限制登录来源。配置方法见[认证](../reference/environment-variables.md#认证)和[本地认证](../reference/environment-variables.md#本地认证)。

<a id="cli-登录"></a>

## 命令行登录

1. 执行以下命令，按提示输入用户名和密码：

    ```bash
    datamind login
    ```

2. 登录后，查看当前身份：

    ```bash
    datamind whoami
    ```

3. 如需退出登录，执行：

    ```bash
    datamind logout
    ```

命令行会将登录凭据保存在本地。退出后，需重新登录才能执行受保护的命令。详细参数见[认证命令](../cli/auth.md)。

> **注意**
>
> 本地登录凭据包含认证令牌，请勿提交到代码仓库或与其他用户共享。

<a id="创建用户和角色"></a>

## 用户与角色管理

以管理员身份登录后，创建角色并为用户授权。例如，创建可查询模型和部署的只读角色：

1. 创建只读角色：

    ```bash
    datamind role create model-reader \
      --permission model.read \
      --permission deployment.read
    ```

2. 创建用户，按提示设置密码：

    ```bash
    datamind user create analyst --display-name 分析员
    ```

3. 授予角色：

    ```bash
    datamind role grant analyst model-reader
    ```

4. 查看用户信息：

    ```bash
    datamind user show analyst
    ```

创建用户后，可执行以下管理操作：

撤销角色授权：

```bash
datamind role revoke analyst model-reader
```

停用账号：

```bash
datamind user disable analyst
```

重新启用账号：

```bash
datamind user enable analyst
```

重置密码：

```bash
datamind user reset-password analyst
```

按提示输入新密码。密码重置后，该用户已有的登录会话会被撤销。服务端会检查账号、角色和登录凭据的当前状态，令牌尚未过期也不代表原有权限始终有效。完整参数见[用户与角色命令](../cli/identity.md)，权限定义见[状态与权限](../reference/states-permissions.md)。

> **说明**
>
> 使用 `datamind role grant` 为用户授予已有角色。如需调整角色权限，请在管理控制台的**角色管理**中修改。

> **说明**
>
> 内置管理员不能停用或删除，其用户名、显示名称和 `administrator` 角色不可变更，但可以修改密码。内置角色不能停用或删除。系统会阻止停用或删除当前登录账号，以及移除最后一个有效管理员的操作。

<a id="http-与-console"></a>

## HTTP 接口认证

1. 调用 `POST /auth/login`，提交用户名和密码：

    ```json
    {
      "username": "<username>",
      "password": "<password>"
    }
    ```

2. 使用返回的 `access_token` 调用受保护的接口，在请求头中设置：

    ```http
    Authorization: Bearer <access_token>
    ```

3. 如需续期，调用 `POST /auth/refresh` 并提交 `refresh_token`。刷新成功后，使用新返回的访问令牌和刷新令牌。
4. 如需退出登录，调用 `POST /auth/logout`，提交刷新令牌以撤销会话。

接口参数、响应和错误说明见[预测 API](../reference/runtime-api.md)。

## 管理控制台登录

打开管理控制台，使用用户名和密码登录。登录后，可通过右上角账号菜单进入**用户管理**或**角色管理**，管理用户和角色权限。操作步骤见[管理控制台](console.md#用户与权限)。

> **说明**
>
> 管理入口和操作按钮根据账号权限显示，每次操作均由服务端校验权限。

<a id="失败处理"></a>

## 常见问题

- **认证失败（401）**：检查令牌是否有效、账号状态是否正常，以及各服务的签名密钥是否一致。
- **权限不足（403）**：检查用户角色是否包含所需权限。
- **账号被锁定**：检查登录失败次数和锁定时间，待锁定结束后重试。
- **本地账号无法登录**：检查来源网段及应急账号限制。
- **无法停用账号或撤销授权**：检查是否触发内置账号、当前账号或最后一个有效管理员的保护规则。
