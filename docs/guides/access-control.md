# 访问控制

Datamind 基于用户角色控制资源访问和操作权限。命令行、管理控制台和 HTTP 接口独立登录，分别管理登录凭据。命令参数见[身份管理命令](../cli/identity.md)，权限定义见[状态与权限](../reference/states-permissions.md)。

<a id="初始化与启用认证"></a>

## 配置认证

按照[配置与初始化](../getting-started/configuration.md)完成数据库迁移和系统初始化，然后在 `.env` 文件中启用认证并设置签名密钥：

```dotenv
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
```

将示例值替换为随机生成的密钥，并确保命令行、预测服务、管理控制台和任务 Worker 使用同一签名密钥。在预发布和生产环境中，还须启用认证，并配置允许本地账号登录的来源网段：

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

## 管理控制台登录

打开管理控制台，使用用户名和密码登录。登录后，可点击左侧底部的**管理**，切换到**用户管理**或**角色管理**页签，管理用户和角色权限。操作步骤见[管理控制台](console.md#用户与权限)。

> **说明**
>
> 管理入口和操作按钮根据账号权限显示，每次操作均由服务端校验权限。

<a id="http-与-console"></a>

## HTTP 接口认证

1. 调用 `POST /auth/login`，提交用户名和密码：

    ```bash
    curl -sS http://127.0.0.1:8700/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"<username>","password":"<password>"}'
    ```

2. 使用返回的 `access_token` 调用受保护的接口，在请求头中携带令牌。以下以查询已加载服务为例，需拥有 `runtime.read` 权限：

    ```bash
    curl -sS http://127.0.0.1:8700/admin/services \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <access_token>" \
      -d '{}'
    ```

3. 如需续期，调用 `POST /auth/refresh` 并提交 `refresh_token`，刷新成功后使用新返回的访问令牌和刷新令牌：

    ```bash
    curl -sS http://127.0.0.1:8700/auth/refresh \
      -H "Content-Type: application/json" \
      -d '{"refresh_token":"<refresh_token>"}'
    ```

4. 如需退出登录，调用 `POST /auth/logout`，提交当前刷新令牌以撤销会话：

    ```bash
    curl -i http://127.0.0.1:8700/auth/logout \
      -H "Content-Type: application/json" \
      -d '{"refresh_token":"<refresh_token>"}'
    ```

系统会检查账号、角色和登录凭据的当前状态，令牌尚未过期也不代表原有权限始终有效。相关接口的参数、响应及错误说明见[预测 API](../reference/runtime-api.md)。

<a id="创建用户和角色"></a>

## 用户与角色管理

系统初始化时会创建以下[内置角色](../reference/states-permissions.md#内置角色)，可在创建用户时直接选择：

| 角色 | 用途 |
| --- | --- |
| `administrator` | 管理全部资源、用户和角色 |
| `editor` | 创建和修改业务资源，管理模型运行并调用预测服务 |
| `viewer` | 查看模型、部署、实验、路由及其运行状态 |
| `invoker` | 调用预测服务，提交和管理批量预测任务 |
| `auditor` | 查看审计记录、请求记录，以及用户、角色等身份信息 |

管理用户与角色时，请注意以下事项：

- 用户和角色管理操作需以管理员身份登录后执行。
- 用户可同时拥有多个角色，并获得这些角色授予的所有权限。例如，组合授予 `viewer` 和 `auditor` 可获得全部只读权限。
- 各角色的操作范围不同。例如，`editor` 允许创建和修改业务资源，但不能删除资源或导出数据。

### 用户管理

创建用户时，通过 `--role` 指定初始角色，重复指定可授予多个角色。以下以用户 `alice` 为例，执行后按提示设置密码：

```bash
datamind user create alice --display-name Alice --role viewer
```

查看用户信息：

```bash
datamind user show alice
```

停用用户：

```bash
datamind user disable alice
```

启用用户：

```bash
datamind user enable alice
```

重置密码，按提示输入新密码。重置后，该用户已有的登录会话会被撤销：

```bash
datamind user reset-password alice
```

### 角色管理

用户创建后，可按需调整角色授权。例如，为 `alice` 授予 `auditor` 角色：

```bash
datamind role grant alice auditor
```

撤销角色授权：

```bash
datamind role revoke alice auditor
```

内置角色无法满足需求时，可以创建自定义角色。将 `<role>` 替换为实际角色名：

```bash
datamind role create <role> \
  --permission model.read \
  --permission deployment.read \
  --permission experiment.read \
  --permission routing.read \
  --permission runtime.read \
  --permission prediction.invoke
```

自定义角色名称不能与内置角色重复。

> **注意**
>
> 内置管理员仅允许修改密码，不能停用或删除；内置角色不能修改、停用或删除。系统同时保护当前登录账号和最后一个有效管理员，阻止停用、删除或撤销授权等导致管理权限丢失的操作。

## 组织管理

机构和部门用于记录用户的组织归属，便于人员管理和操作追溯。用户的访问权限由角色单独授予。您可以通过管理控制台或命令行管理机构、部门及用户归属。以下介绍命令行操作。

### 创建

以下以“总行 → 人力资源部 → 招聘组”为例，创建机构和部门：

1. 创建机构“总行”：

    ```bash
    datamind organization create 总行 --code HQ
    ```

2. 在“总行”下创建一级部门“人力资源部”：

    ```bash
    datamind department create 人力资源部 \
      --organization 总行 --code HR
    ```

3. 在“人力资源部”下创建子部门“招聘组”：

    ```bash
    datamind department create 招聘组 \
      --organization 总行 --parent 人力资源部
    ```

设置组织结构时，请注意以下事项：

- 机构编码全局唯一，部门编码在机构内唯一。
- 同一父部门下的部门名称不能重复，不同分支可以同名。
- 上级部门必须属于同一机构，不能选择当前部门或其下级部门。

### 设置用户归属

为已创建的用户设置工号和组织归属：

```bash
datamind user update alice \
  --employee-number 001234 \
  --organization 总行 \
  --department "人力资源部/招聘组"
```

创建用户时，也可通过 `--employee-number`、`--organization` 和 `--department` 指定工号和组织归属。

设置和更新用户归属时，请注意：

- 部门和组使用完整路径表示。用户关联直接所属节点，用户详情展示完整路径。
- 工号可留空；填写后须全局唯一，并保留前导零。
- 未指定的字段保留原值，传入空字符串可清空。
- 跨机构调动时，须同时更新机构和部门；暂不指定部门时，使用 `--department ""` 清空部门归属。

如需调整用户的组织归属，可更新所属部门。例如，将用户从招聘组调整为直接归属人力资源部：

```bash
datamind user update alice --department 人力资源部
```

更新后，可通过 `datamind user show alice` 查看结果。

> **注意**
>
> 使用机构名称和部门路径指定组织归属。存在重名时，可使用完整部门路径，或通过 `--organization-id`、`--department-id` 指定机构和部门 ID。机构或部门改名不影响已有用户的组织归属。

### 停用与启用

机构或部门暂不使用时，可先停用，保留现有人员归属和历史记录。恢复使用时，再重新启用。

停用与启用时，请注意以下事项：

- 停用后，该机构或部门及其下级部门不能新增用户关联，也不能在其下新增部门。
- 已有用户仍可修改资料或调出，访问权限仍由角色决定。
- 重新启用上级机构或部门，不会改变下级部门自身的启停状态。

停用机构：

```bash
datamind organization disable 总行
```

启用机构：

```bash
datamind organization enable 总行
```

停用部门：

```bash
datamind department disable "人力资源部/招聘组" --organization 总行
```

启用部门：

```bash
datamind department enable "人力资源部/招聘组" --organization 总行
```

### 删除

删除机构或部门前，须先解除关联：

- 删除机构：调整关联用户的归属，并清理机构下的所有部门。
- 删除部门：调整直接关联用户的归属，并移动或删除直属下级部门。

停用记录也计入关联，未清理完毕时，系统会提示关联数量并阻止删除。删除不会改变已有审计记录。

删除机构：

```bash
datamind organization delete 总行
```

删除部门：

```bash
datamind department delete "人力资源部/招聘组" --organization 总行
```

<a id="失败处理"></a>

## 常见问题

- **认证失败（401）**：检查令牌是否有效、账号状态是否正常，以及各服务的签名密钥是否一致。
- **权限不足（403）**：检查用户角色是否包含所需权限。
- **账号被锁定**：检查登录失败次数和锁定时间，待锁定结束后重试。
- **本地账号无法登录**：检查来源网段及应急账号限制。
- **无法停用账号或撤销授权**：检查是否触发内置账号、当前账号或最后一个有效管理员的保护规则。
