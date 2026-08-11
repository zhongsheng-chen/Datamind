## CLI 使用说明

Datamind 提供统一的命令行工具，用于管理模型注册、模型生命周期、部署、路由、实验和运行服务。

### 快速开始

在项目虚拟环境中安装 CLI：

```bash
pip install -e .
datamind --help
```

复制统一环境变量模板。Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

Linux：

```bash
cp .env.example .env
```

至少需要修改以下配置：

- `DATAMIND_SERVICE_ENVIRONMENT`：当前运行环境。
- `DATAMIND_DATABASE_URL`：PostgreSQL 异步连接地址。
- `DATAMIND_AUTH_SECRET_KEY`：高强度 JWT 签名密钥。
- `DATAMIND_INIT_ADMIN_PASSWORD`：首次初始化使用的管理员密码；生产环境应
  覆盖默认值。
- `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS`：development 可留空；staging 和
  production 必须配置实际的服务器地址或内网网段。
- 使用 MinIO 时填写 `DATAMIND_STORAGE_MINIO_ACCESS_KEY` 和
  `DATAMIND_STORAGE_MINIO_SECRET_KEY`。

CLI 采用单环境模式。资源创建、更新、查询和服务启动统一使用
`DATAMIND_SERVICE_ENVIRONMENT`，不提供 `--environment` 参数。

初始化或升级数据库：

```bash
alembic upgrade head
```

首次部署前在 `.env` 中配置管理员凭据：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=<strong-password>
```

随后执行一次性系统初始化：

```bash
datamind init
```

初始化命令不会在终端读取用户名或密码。用户名和密码未配置时均使用 `admin`。
生产环境应在初始化前通过环境变量或 `.env` 覆盖密码；初始化完成后，应从
运行环境中移除 `DATAMIND_INIT_ADMIN_PASSWORD`。

初始化完成后登录：

```bash
datamind login --username admin
```

登录成功后，CLI 自动保存当前用户的访问令牌和刷新令牌。后续业务命令
自动读取本地凭据；访问令牌失效时，CLI 会自动轮换刷新令牌并更新凭据。
不需要手工设置 `DATAMIND_ACCESS_TOKEN`。

Linux 凭据默认保存在 `~/.config/datamind/credentials.json`，文件权限为
`0600`。Windows 凭据默认保存在
`%APPDATA%\datamind\credentials.json`。`DATAMIND_ACCESS_TOKEN` 仅作为
CI、容器和临时自动化任务的覆盖入口，不应写入共享的 `.env`。

### 命令总览

```bash
datamind --help
datamind --version
datamind init --help

datamind login --help
datamind logout --help
datamind whoami --help
datamind user --help
datamind role --help
datamind model --help
datamind deployment --help
datamind route --help
datamind experiment --help
datamind service --help
datamind runtime --help
datamind console --help
```

主要命令组：

| 命令组 | 说明                                                 |
|--------|------------------------------------------------------|
| `init` | 一次性创建首个管理员、系统管理员角色和初始化状态     |
| `login` / `logout` / `whoami` | 登录、退出和身份查询                                 |
| `user` | 本地用户创建、查询、启停、密码重置和逻辑删除         |
| `role` | 角色创建、查询、授予、撤销和逻辑删除                 |
| `model` | 模型注册、查询、激活、停用、删除                     |
| `deployment` | 模型部署创建、查询、启用、禁用                       |
| `route` | 模型路由规则创建、查询、更新、启用、禁用             |
| `experiment` | A/B 实验创建、更新、生命周期管理、分组管理和效果分析 |
| `service` | 启动 Runtime Service                               |
| `runtime` | 部署模型加载、卸载、重载和运行状态查询             |
| `console` | 启动管理控制台                                       |

### 业务命令常用参数

| 参数 | 说明 |
|------|------|
| `--format text/json` | 输出格式，默认 `text` |

认证开启时，实际操作人始终来自访问令牌。开发和测试环境
关闭认证时，命令以 `system` 身份运行。

时间字段说明：

- 数据库中保存 UTC 时间。
- CLI JSON 输出使用 ISO UTC 字符串。
- CLI 文本输出显示为本地配置时区时间。
- `--effective-from`、`--effective-to` 使用 ISO 日期时间格式，例如 `2026-07-01T09:00:00+08:00`。

JSON 参数说明：

- `--config-file`、`--rules-file` 建议使用 JSON 文件。
- Windows PowerShell 中 JSON 字符串容易因为引号被解析失败，推荐优先使用 JSON 文件参数，例如 `--config-file config.json`、`--rules-file route_rules.json`。
- 如需直接传 JSON，请确保 key 使用双引号并正确转义。

---

## 身份认证

Datamind 仅支持数据库中的本地用户。密码通过隐藏提示输入，命令行
不会接收认证来源、操作人或资源所有者参数：

```powershell
datamind login --username alice
```

首次管理员由顶层 `datamind init` 命令根据初始化配置创建。该命令仅在系统
未初始化且用户表为空时可执行，不接收用户名或密码参数，也不支持强制覆盖或
重复初始化。
预发布和生产环境启用认证时必须配置 LOCAL 认证允许网段。

普通本地账户登录后签发访问令牌和刷新令牌。应急账户使用同一登录命令，
但只签发有效期更短的访问令牌，不签发刷新令牌：

```powershell
datamind login --username emergency-admin
```

登录命令不会在终端显示完整令牌。登录成功后可以直接查询当前身份：

```bash
datamind whoami
```

后续业务命令会自动使用令牌中的用户名、角色和权限：

```powershell
datamind model list
datamind model activate scorecard --version 1.0.0
```

普通账户的访问令牌过期后，业务命令会自动完成续期并更新本地凭据。

退出登录会撤销刷新令牌并删除本地凭据；当前访问令牌仍会在自身过期时间
到达后失效：

```bash
datamind logout
```

当自动化任务显式设置了 `DATAMIND_ACCESS_TOKEN` 时，该环境变量优先于
本地凭据。`datamind logout` 无法修改父 Shell 的环境变量，需要由调用方清除。

业务命令所需权限：

| 命令组 | 查询权限 | 变更权限 | 高风险权限 |
|--------|----------|----------|------------|
| `model` | `model.read` | `model.write` | `model.delete` |
| `deployment` | `deployment.read` | `deployment.write` | `deployment.delete` |
| `route` | `routing.read` | `routing.write` | `routing.delete` |
| `experiment` | `experiment.read` | `experiment.write` | `experiment.delete` |
| `service` | - | `runtime.manage` | - |
| `runtime` | `runtime.read` | `runtime.manage` | - |
| `outcome` | - | `outcome.write` | - |
| `user` / `role` | `identity.read` | `identity.manage` | `identity.manage` |

`staging` 和 `production` 环境不允许关闭认证。`development` 和
`testing` 环境可以关闭认证，以 `system` 身份执行本地维护命令。

### 用户与角色管理

Datamind 支持多个 LOCAL 用户。`datamind init` 只创建首个管理员，后续
用户由已登录且具有 `identity.manage` 权限的管理员创建：

```bash
datamind role create developer \
  --permission model.read \
  --permission model.write

datamind user create alice \
  --display-name "模型分析员" \
  --role developer
```

密码通过隐藏提示输入，不会作为命令行参数保存到 shell 历史。用户登录后
即可使用所属角色提供的权限：

```bash
datamind login --username alice
datamind model list
```

管理员可以查询、授予和撤销角色：

```bash
datamind user list
datamind user show alice
datamind role list
datamind role grant alice developer
datamind role revoke alice developer
```

重置密码会立即撤销该用户的全部刷新令牌；若重置的是当前登录用户，CLI
还会删除本地会话并要求重新登录：

```bash
datamind user reset-password alice
```

停用和删除用户同样会撤销已有刷新令牌。删除采用逻辑删除，以保留审计和
历史关联；不能停用或删除当前登录用户，也不能移除最后一个有效的
`administrator` 角色的用户：

```bash
datamind user disable alice
datamind user enable alice
datamind user delete alice --reason "员工离职" --yes
```

Datamind 不预置任何用户。`datamind init` 根据初始化配置创建首个管理员，
并创建唯一的内置角色 `administrator`，授予全部权限 `*`。该角色不能通过普通
角色命令创建、停用或删除；管理员可以将其授予其他受信任用户，但系统始终保留
至少一个有效管理员。其他业务角色由管理员按需创建。普通角色仍授予给用户时，
必须先撤销角色授予：

```bash
datamind role revoke alice developer
datamind role delete developer --reason "角色停用" --yes
```

---

## 模型管理

### 注册模型：`model register`

#### 命令格式

```bash
datamind model register <name>
  --version <version>
  --model-path <path>
  --framework <framework>
  --model-type <model-type>
  --task-type <task-type>
  [--input-schema-file <file>]
  [--output-schema-file <file>]
  [--description <description>]
  [--version-description <description>]
  [--force]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称，业务唯一标识，例如 `scorecard` |
| `--version <version>` | 模型版本号，例如 `1.0.0` |
| `--model-path <path>` | 模型文件路径 |
| `--framework <framework>` | 模型框架，例如 `sklearn`、`xgboost`、`lightgbm`、`catboost` |
| `--model-type <model-type>` | 模型类型，例如 `logistic_regression`、`random_forest`、`xgboost` |
| `--task-type <task-type>` | 任务类型，例如 `classification`、`scoring` |
| `--input-schema-file <file>` | 输入 Schema 文件，JSON 格式 |
| `--output-schema-file <file>` | 输出 Schema 文件，JSON 格式 |
| `--description <description>` | 模型描述 |
| `--version-description <description>` | 模型版本描述 |
| `--force` | 强制覆盖已有版本 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --description "信用评分卡模型" \
  --version-description "信用评分卡模型 v1.0.0"

datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --force \
  --format json
```

### 列出模型：`model list`

#### 命令格式

```bash
datamind model list
  [--status <status>]
  [--framework <framework>]
  [--model-type <model-type>]
  [--task-type <task-type>]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--include-archived]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--status <status>` | 按模型状态过滤，例如 `active`、`inactive`、`archived` |
| `--framework <framework>` | 按模型框架过滤 |
| `--model-type <model-type>` | 按模型类型过滤 |
| `--task-type <task-type>` | 按任务类型过滤 |
| `--created-by <user>` | 按创建人过滤 |
| `--limit <n>` | 返回记录数量限制 |
| `--offset <n>` | 分页偏移量 |
| `--include-archived` | 包含已归档模型，默认不显示 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind model list
datamind model list --status active
datamind model list --framework sklearn
datamind model list --include-archived
datamind model list --limit 20 --offset 0
datamind model list --format json
```

### 查看模型详情：`model show`

#### 命令格式

```bash
datamind model show (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称，与 `--model-id` 二选一 |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 版本号，与 `--version-id` 二选一 |
| `--version-id <version-id>` | 版本 ID |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind model show scorecard
datamind model show scorecard --version 1.0.0
datamind model show --model-id mdl_a1b2c3d4 --format json
```

### 激活模型：`model activate`

#### 命令格式

```bash
datamind model activate (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--format <text|json>]
```

未指定版本时，命令会激活模型及其全部 inactive 版本；指定版本时，
只激活该版本及其模型。deprecated 和 archived 版本不受影响。

#### 使用示例

```bash
datamind model activate scorecard --version 1.0.0
datamind model activate --model-id mdl_a1b2c3d4 --version-id ver_a1b2c3d4 --format json
```

### 停用模型：`model deactivate`

#### 命令格式

```bash
datamind model deactivate (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--format <text|json>]
```

未指定版本时，命令会停用模型及其全部 active 版本；指定版本时，
只停用该版本，并在其为最后一个 active 版本时同时停用模型。

#### 使用示例

```bash
datamind model deactivate scorecard --version 1.0.0
datamind model deactivate --model-id mdl_a1b2c3d4 --format json
```

### 弃用模型：`model deprecate`

#### 命令格式

```bash
datamind model deprecate (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--format <text|json>]
```

未指定版本时，命令会弃用模型及其全部 active、inactive 版本；
指定版本时，只弃用该版本，并在其为最后一个 active 版本时停用模型。
存在活动部署时，必须先禁用相关部署。

#### 使用示例

```bash
datamind model deprecate scorecard
datamind model deprecate scorecard --version 1.0.0
datamind model deprecate --model-id mdl_a1b2c3d4 \
  --version-id ver_a1b2c3d4 --format json
```

### 删除模型：`model delete`

#### 命令格式

```bash
datamind model delete (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--reason <reason>]
  [--yes]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称，与 `--model-id` 二选一 |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 删除指定版本，与 `--version-id` 二选一 |
| `--version-id <version-id>` | 删除指定版本 ID |
| `--reason <reason>` | 删除原因，可选 |
| `--yes` | 跳过交互确认 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind model delete scorecard
datamind model delete scorecard --version 1.0.0
datamind model delete --model-id mdl_a1b2c3d4 --yes
datamind model delete --model-id mdl_a1b2c3d4 \
  --version-id ver_a1b2c3d4 --yes
```

### 永久清理模型：`model purge`

永久清理是不可恢复操作，只接受已经逻辑删除的模型或版本。

```bash
datamind model purge (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--reason <reason>]
  [--yes]
  [--format <text|json>]

datamind model purge scorecard --version 1.0.0 --yes
```

---

## 部署管理

### 创建部署：`deployment create`

#### 命令格式

```bash
datamind deployment create (<name> | --model-id <model-id>)
  [--version <version> | --version-id <version-id>]
  [--rollout <full|canary|shadow>]
  [--role <champion|challenger|shadow>]
  [--config-file <file>]
  [--description <description>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<name>` | 模型名称，与 `--model-id` 二选一 |
| `--model-id <model-id>` | 模型 ID |
| `--version <version>` | 模型版本号，与 `--version-id` 二选一；不传时由服务层按默认逻辑解析 |
| `--version-id <version-id>` | 版本 ID |
| `--rollout <full|canary|shadow>` | 发布方式，默认 `full` |
| `--role <champion|challenger|shadow>` | 部署角色，默认 `champion`；影子发布必须使用 `shadow` |
| `--config-file <file>` | 运行时配置文件，JSON 对象 |
| `--description <description>` | 部署描述 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### config 示例

评分任务：

```json
{
  "pdo": 50,
  "base_score": 600
}
```

分类任务：

```json
{
  "threshold": 0.5
}
```

#### 使用示例

```bash
datamind deployment create scorecard \
  --version 1.0.0 \
  --rollout full \
  --role champion \
  --config-file config.json \
  --description "信用评分模型生产部署"

datamind deployment create scorecard \
  --version 1.0.0 \
  --rollout canary \
  --role challenger \
  --config-file config.json

datamind deployment create --model-id mdl_a1b2c3d4 \
  --version-id ver_a1b2c3d4 \
  --format json
```

### 列出部署：`deployment list`

#### 命令格式

```bash
datamind deployment list
  [--model-id <model-id>]
  [--version-id <version-id>]
  [--framework <framework>]
  [--rollout <full|canary|shadow>]
  [--role <champion|challenger>]
  [--status <status>]
  [--deployed-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--model-id <model-id>` | 按模型 ID 过滤 |
| `--version-id <version-id>` | 按版本 ID 过滤 |
| `--framework <framework>` | 按模型框架过滤 |
| `--rollout <full|canary|shadow>` | 按发布方式过滤 |
| `--role <champion|challenger>` | 按部署角色过滤 |
| `--status <status>` | 按部署状态过滤，例如 `active`、`inactive` |
| `--deployed-by <user>` | 按部署人过滤 |
| `--limit <n>` | 返回记录数量限制，默认 `10` |
| `--offset <n>` | 分页偏移量，默认 `0` |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind deployment list
datamind deployment list --model-id mdl_a1b2c3d4
datamind deployment list --version-id ver_a1b2c3d4
datamind deployment list --rollout canary
datamind deployment list --role challenger
datamind deployment list --status active
datamind deployment list --limit 50 --offset 0
datamind deployment list --format json
```

### 查看部署详情：`deployment show`

#### 命令格式

```bash
datamind deployment show <deployment-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind deployment show dep_a1b2c3d4
datamind deployment show dep_a1b2c3d4 --format json
```

### 启用部署：`deployment enable`

#### 命令格式

```bash
datamind deployment enable <deployment-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind deployment enable dep_a1b2c3d4
```

### 禁用部署：`deployment disable`

#### 命令格式

```bash
datamind deployment disable <deployment-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind deployment disable dep_a1b2c3d4
```

### 删除与恢复部署

只能删除已经停用、卸载且未被有效路由或实验引用的部署；恢复后的部署
保持 `inactive`，需要显式启用后才能重新接收流量。

```bash
datamind deployment delete dep_a1b2c3d4 [--reason <reason>] [--yes]
datamind deployment restore dep_a1b2c3d4
```

---

## 路由管理

### 创建路由：`route create`

#### 命令格式

```bash
datamind route create <deployment-id>
  --traffic-ratio <ratio>
  [--rules-file <file>]
  [--description <description>]
  [--enabled | --disabled]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<deployment-id>` | 部署 ID |
| `--traffic-ratio <ratio>` | 路由流量比例，范围 `0~1` |
| `--rules-file <file>` | 路由规则文件，JSON 对象 |
| `--description <description>` | 路由描述 |
| `--enabled / --disabled` | 是否启用路由，默认启用 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind route create dep_a1b2c3d4 \
  --traffic-ratio 1.0

datamind route create dep_a1b2c3d4 \
  --traffic-ratio 0.2 \
  --rules-file route_rules.json

datamind route create dep_a1b2c3d4 \
  --traffic-ratio 0.0 \
  --disabled \
  --description "预创建但暂不启用"
```

### 列出路由：`route list`

#### 命令格式

```bash
datamind route list
  [--deployment-id <deployment-id>]
  [--rollout <full|canary|shadow>]
  [--group <group> | --rollout-group <group>]
  [--enabled | --disabled]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--deployment-id <deployment-id>` | 按部署 ID 过滤 |
| `--rollout <full|canary|shadow>` | 按发布方式过滤 |
| `--group / --rollout-group <group>` | 按发布分组过滤 |
| `--enabled / --disabled` | 按启用状态过滤 |
| `--created-by <user>` | 按创建人过滤 |
| `--limit <n>` | 返回记录数量限制，默认 `10` |
| `--offset <n>` | 分页偏移量，默认 `0` |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind route list
datamind route list --deployment-id dep_a1b2c3d4
datamind route list --rollout canary
datamind route list --group challenger
datamind route list --enabled
datamind route list --disabled
datamind route list --format json
```

### 查看路由详情：`route show`

#### 命令格式

```bash
datamind route show <routing-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind route show rtn_a1b2c3d4
datamind route show rtn_a1b2c3d4 --format json
```

### 更新路由：`route update`

#### 命令格式

```bash
datamind route update <routing-id>
  [--traffic-ratio <ratio>]
  [--rules-file <file>]
  [--description <description>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<routing-id>` | 路由 ID |
| `--traffic-ratio <ratio>` | 更新路由流量比例，范围 `0~1` |
| `--rules-file <file>` | 更新路由规则文件，JSON 对象 |
| `--description <description>` | 更新路由描述 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind route update rtn_a1b2c3d4 --traffic-ratio 0.3

datamind route update rtn_a1b2c3d4 \
  --rules-file route_rules.json

datamind route update rtn_a1b2c3d4 \
  --description "调整灰度流量到 30%" \
  --format json
```

### 启用路由：`route enable`

#### 命令格式

```bash
datamind route enable <routing-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind route enable rtn_a1b2c3d4
```

### 禁用路由：`route disable`

#### 命令格式

```bash
datamind route disable <routing-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind route disable rtn_a1b2c3d4
```

### 删除与恢复路由

只能删除已禁用的路由；恢复后的路由保持禁用。

```bash
datamind route delete rtn_a1b2c3d4 [--reason <reason>] [--yes]
datamind route restore rtn_a1b2c3d4
```

---

## 实验管理

### 创建实验：`experiment create`

#### 命令格式

```bash
datamind experiment create
  --model-id <model-id>
  [--name <name>]
  [--strategy <hash|manual>]
  [--traffic-ratio <ratio>]
  [--bucket-key <key>]
  [--description <description>]
  [--effective-from <datetime>]
  [--effective-to <datetime>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明                                                                               |
|------|------------------------------------------------------------------------------------|
| `--model-id <model-id>` | 模型 ID                                                                            |
| `--name <name>` | 实验名称                                                                           |
| `--strategy <hash| manual>`                                                                           | 实验分配策略，默认 `hash` |
| `--traffic-ratio <ratio>` | 实验流量比例；`hash` 策略范围为 `(0, 1]`，`manual` 策略范围为 `[0, 1]`             |
| `--bucket-key <key>` | 分桶主体字段，例如 `customer_id`、`order_id`、`application_id`，默认 `customer_id` |
| `--description <description>` | 实验描述                                                                           |
| `--effective-from <datetime>` | 生效开始时间；默认当前 UTC 时间                                                    |
| `--effective-to <datetime>` | 生效结束时间；默认不限制结束时间                                                   |
| `--format <text| json>`                                                                             | 输出格式，默认 `text` |

#### 补充说明

| 配置项 | 说明 |
|------|------|
| `strategy` | 写入实验配置，用于指定实验分配策略 |
| `traffic_ratio` | 写入实验配置，用于控制实验总流量 |
| `bucket_key` | 写入实验配置，用于从请求数据中提取分桶主体 |

#### 使用示例

```bash
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --strategy hash \
  --traffic-ratio 0.5 \
  --bucket-key customer_id

datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name manual_ab_test \
  --strategy manual \
  --traffic-ratio 0 \
  --bucket-key customer_id

datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --traffic-ratio 0.5 \
  --bucket-key customer_id \
  --effective-from 2026-07-01T09:00:00+08:00 \
  --effective-to 2026-07-31T23:59:59+08:00
```

### 更新实验：`experiment update`

#### 命令格式

```bash
datamind experiment update <experiment-id>
  [--name <name>]
  [--strategy <hash|manual>]
  [--traffic-ratio <ratio>]
  [--bucket-key <key>]
  [--description <description>]
  [--effective-from <datetime>]
  [--effective-to <datetime>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--name <name>` | 更新实验名称 |
| `--strategy <hash|manual>` | 更新实验分配策略 |
| `--traffic-ratio <ratio>` | 更新实验流量比例；`hash` 策略范围为 `(0, 1]`，`manual` 策略范围为 `[0, 1]` |
| `--bucket-key <key>` | 更新分桶主体字段 |
| `--description <description>` | 更新实验描述 |
| `--effective-from <datetime>` | 更新生效开始时间 |
| `--effective-to <datetime>` | 更新生效结束时间 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 更新限制

| 实验状态 | 允许修改 |
|------|------|
| `draft` | `name`、`description`、`strategy`、`traffic_ratio`、`bucket_key`、`effective_from`、`effective_to` |
| `paused` | `description`、`effective_to` |
| `running`、`stopped`、`completed`、`archived` | 不允许修改 |

#### 使用示例

```bash
datamind experiment update exp_a1b2c3d4 \
  --name scorecard_ab_test_v2 \
  --traffic-ratio 0.3 \
  --bucket-key customer_id

datamind experiment update exp_a1b2c3d4 \
  --description "暂停期间补充说明" \
  --effective-to 2026-07-31T23:59:59+08:00

datamind experiment update exp_a1b2c3d4 --format json
```

### 列出实验：`experiment list`

#### 命令格式

```bash
datamind experiment list
  [--model-id <model-id>]
  [--status <status>]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <text|json>]
```

#### 使用示例

```bash
datamind experiment list
datamind experiment list --model-id mdl_a1b2c3d4
datamind experiment list --status running
datamind experiment list --created-by admin
datamind experiment list --limit 20 --offset 0
datamind experiment list --format json
```

### 查看实验详情：`experiment show`

#### 命令格式

```bash
datamind experiment show <experiment-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind experiment show exp_a1b2c3d4
datamind experiment show exp_a1b2c3d4 --format json
```

### 启动实验：`experiment start`

```bash
datamind experiment start <experiment-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment start exp_a1b2c3d4
```

### 暂停实验：`experiment pause`

```bash
datamind experiment pause <experiment-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment pause exp_a1b2c3d4
```

### 停止实验：`experiment stop`

```bash
datamind experiment stop <experiment-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment stop exp_a1b2c3d4
```

### 完成实验：`experiment complete`

```bash
datamind experiment complete <experiment-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment complete exp_a1b2c3d4
```

### 归档实验：`experiment archive`

```bash
datamind experiment archive <experiment-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment archive exp_a1b2c3d4
```

### 实验状态说明

| 命令 | 状态 | 说明 |
|------|------|------|
| `experiment create` | `draft` | 创建实验，尚未开始分流 |
| `experiment start` | `running` | 启动实验，开始分配实验流量 |
| `experiment pause` | `paused` | 暂停实验，后续可再次启动 |
| `experiment stop` | `stopped` | 停止实验，通常用于异常中止或不再继续 |
| `experiment complete` | `completed` | 标记实验正常完成 |
| `experiment archive` | `archived` | 归档实验，作为历史记录保留 |

推荐生命周期：

```text
draft -> running -> completed -> archived
draft -> running -> paused -> running -> completed -> archived
draft -> running -> stopped -> archived
```

### 删除与恢复实验

只能删除 `draft` 或 `archived` 实验。删除实验会以同一批次逻辑删除其
分组，恢复实验时同步恢复该批次分组。

```bash
datamind experiment delete exp_a1b2c3d4 [--reason <reason>] [--yes]
datamind experiment restore exp_a1b2c3d4
```

### 分析实验：`experiment analyze`

#### 命令格式

```bash
datamind experiment analyze <experiment-id>
  [--baseline-variant-id <variant-id>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--baseline-variant-id <variant-id>` | 基准分组 ID，用于计算其他分组相对基准分组的 Lift |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind experiment analyze exp_a1b2c3d4

datamind experiment analyze exp_a1b2c3d4 \
  --baseline-variant-id var_control

datamind experiment analyze exp_a1b2c3d4 --format json
```

---

## 实验分组管理

### 添加实验分组：`experiment variant add`

#### 命令格式

```bash
datamind experiment variant add <experiment-id>
  --name <name>
  --deployment-id <deployment-id>
  --weight <weight>
  [--control]
  [--config <json>]
  [--description <description>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<experiment-id>` | 实验 ID |
| `--name <name>` | 分组名称，例如 `control`、`treatment` |
| `--deployment-id <deployment-id>` | 分组关联的部署 ID |
| `--weight <weight>` | 分组权重，范围 `(0, 1]` |
| `--control` | 是否为对照组 |
| `--config <json>` | 分组配置 JSON 对象 |
| `--description <description>` | 分组描述 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind experiment variant add exp_a1b2c3d4 \
  --name control \
  --deployment-id dep_control \
  --weight 0.5 \
  --control

datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5

datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5 \
  --config '{"model_role":"challenger"}'
```

### 更新实验分组：`experiment variant update`

#### 命令格式

```bash
datamind experiment variant update <variant-id>
  [--name <name>]
  [--deployment-id <deployment-id>]
  [--weight <weight>]
  [--control | --treatment]
  [--description <description>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `<variant-id>` | 实验分组 ID |
| `--name <name>` | 更新实验分组名称 |
| `--deployment-id <deployment-id>` | 更新分组关联的部署 ID |
| `--weight <weight>` | 更新分组权重，范围 `(0, 1]` |
| `--control` | 设置为对照组 |
| `--treatment` | 设置为实验组 |
| `--description <description>` | 更新分组描述 |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 更新限制

| 实验状态 | 分组状态 | 允许修改 |
|------|------|------|
| `draft` | `active`、`inactive` | `name`、`deployment_id`、`weight`、`control/treatment`、`description` |
| `paused` | `active`、`inactive` | `description` |
| `running`、`stopped`、`completed`、`archived` | 任意状态 | 不允许修改 |
| 任意状态 | `archived` | 不允许修改 |

#### 使用示例

```bash
datamind experiment variant update var_a1b2c3d4 \
  --name treatment_v2 \
  --deployment-id dep_treatment_v2 \
  --weight 0.4 \
  --treatment

datamind experiment variant update var_a1b2c3d4 \
  --description "暂停期间补充分组说明"

datamind experiment variant update var_a1b2c3d4 --format json
```

### 列出实验分组：`experiment variant list`

#### 命令格式

```bash
datamind experiment variant list [<experiment-id>]
  [--deployment-id <deployment-id>]
  [--status <status>]
  [--control | --non-control]
  [--created-by <user>]
  [--limit <n>]
  [--offset <n>]
  [--format <text|json>]
```

#### 使用示例

```bash
datamind experiment variant list
datamind experiment variant list exp_a1b2c3d4
datamind experiment variant list exp_a1b2c3d4 --status active
datamind experiment variant list --deployment-id dep_a1b2c3d4
datamind experiment variant list --control
datamind experiment variant list --non-control
datamind experiment variant list --format json
```

### 查看实验分组详情：`experiment variant show`

```bash
datamind experiment variant show <variant-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment variant show var_a1b2c3d4
datamind experiment variant show var_a1b2c3d4 --format json
```

### 启用实验分组：`experiment variant activate`

```bash
datamind experiment variant activate <variant-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment variant activate var_a1b2c3d4
```

### 停用实验分组：`experiment variant deactivate`

```bash
datamind experiment variant deactivate <variant-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment variant deactivate var_a1b2c3d4
```

### 归档实验分组：`experiment variant archive`

```bash
datamind experiment variant archive <variant-id>
  [--format <text|json>]
```

示例：

```bash
datamind experiment variant archive var_a1b2c3d4
```

### 删除与恢复实验分组

实验分组只能在所属实验处于 `draft` 时单独删除或恢复。

```bash
datamind experiment variant delete var_a1b2c3d4 \
  [--reason <reason>] [--yes]
datamind experiment variant restore var_a1b2c3d4
```

---

## 服务进程管理

### 启动 Runtime Service：`service run`

#### 命令格式

```bash
datamind service run
  [--host <host>]
  [--port <port>]
  [--reload]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--host <host>` | 监听地址；不传时使用服务配置 |
| `--port <port>` | 监听端口；不传时使用服务配置 |
| `--reload` | 代码变更时自动重载，适合开发环境 |

#### 使用示例

```bash
datamind service run

datamind service run \
  --host 0.0.0.0 \
  --port 8700

datamind service run --reload
```

## 运行实例查询

### 列出运行状态：`runtime list`

#### 命令格式

```bash
datamind runtime list
  [--desired-status <loaded|unloaded>]
  [--limit <n>]
  [--offset <n>]
  [--format <text|json>]
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--desired-status <loaded|unloaded>` | 按期望运行状态过滤 |
| `--limit <n>` | 返回记录数量限制，默认 `10` |
| `--offset <n>` | 分页偏移量，默认 `0` |
| `--format <text|json>` | 输出格式，默认 `text` |

#### 使用示例

```bash
datamind runtime list
datamind runtime list --desired-status loaded
datamind runtime list --format json
```

### 查看部署运行状态：`runtime show`

#### 命令格式

```bash
datamind runtime show <deployment-id>
  [--format <text|json>]
```

#### 使用示例

```bash
datamind runtime show dep_a1b2c3d4
datamind runtime show dep_a1b2c3d4 --format json
```

---

## 常见操作流程

### 1. 注册模型并激活

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path ./models/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring

datamind model activate scorecard --version 1.0.0

datamind model show scorecard --version 1.0.0
```

### 2. 创建部署并配置路由

```bash
datamind deployment create scorecard \
  --version 1.0.0 \
  --rollout full \
  --role champion \
  --config-file config.json

datamind deployment list

datamind route create dep_a1b2c3d4 \
  --traffic-ratio 1.0

datamind route list
```

### 3. 启用部署并启动 Runtime Service

```bash
datamind deployment enable dep_a1b2c3d4

datamind service run \
  --host 0.0.0.0 \
  --port 8700

datamind runtime show dep_a1b2c3d4
```

### 4. 创建并启动 A/B 实验

```bash
datamind experiment create \
  --model-id mdl_a1b2c3d4 \
  --name scorecard_ab_test \
  --strategy hash \
  --traffic-ratio 0.5 \
  --bucket-key customer_id

datamind experiment variant add exp_a1b2c3d4 \
  --name control \
  --deployment-id dep_control \
  --weight 0.5 \
  --control

datamind experiment variant add exp_a1b2c3d4 \
  --name treatment \
  --deployment-id dep_treatment \
  --weight 0.5

datamind experiment show exp_a1b2c3d4

datamind experiment start exp_a1b2c3d4
```

### 5. 暂停并恢复实验

```bash
datamind experiment pause exp_a1b2c3d4

datamind experiment update exp_a1b2c3d4 \
  --description "暂停期间补充说明" \
  --effective-to 2026-07-31T23:59:59+08:00

datamind experiment start exp_a1b2c3d4
```

### 6. 分析并完成实验

```bash
datamind experiment analyze exp_a1b2c3d4 \
  --baseline-variant-id var_control

datamind experiment complete exp_a1b2c3d4

datamind experiment archive exp_a1b2c3d4
```

### 7. 异常中止实验

```bash
datamind experiment stop exp_a1b2c3d4

datamind experiment archive exp_a1b2c3d4
```

---

## CLI 冒烟测试建议

每次调整 CLI 后，建议先执行以下命令确认命令组注册正常：

```bash
datamind --help
datamind model --help
datamind deployment --help
datamind route --help
datamind experiment --help
datamind experiment variant --help
datamind service --help
datamind runtime --help
```

再逐个检查子命令帮助：

```bash
datamind model register --help
datamind model list --help
datamind model show --help
datamind model activate --help
datamind model deactivate --help
datamind model deprecate --help
datamind model delete --help

datamind deployment create --help
datamind deployment list --help
datamind deployment show --help
datamind deployment enable --help
datamind deployment disable --help

datamind route create --help
datamind route list --help
datamind route show --help
datamind route update --help
datamind route enable --help
datamind route disable --help

datamind experiment create --help
datamind experiment update --help
datamind experiment list --help
datamind experiment show --help
datamind experiment start --help
datamind experiment pause --help
datamind experiment stop --help
datamind experiment complete --help
datamind experiment archive --help
datamind experiment analyze --help
datamind experiment variant add --help
datamind experiment variant update --help
datamind experiment variant list --help
datamind experiment variant show --help
datamind experiment variant activate --help
datamind experiment variant deactivate --help
datamind experiment variant archive --help

datamind service run --help
datamind runtime list --help
datamind runtime show --help
```
