#
我想设计一个银行贷款模型部署平台Datamind, 用于部署模型开发人员用Python跑出来的评分卡模型,分类任务等模型。
不用考虑批量预测，零售信贷贷款都是单笔处理的。
模型部署工具考虑用bentoml实现，支持模型注册、注销，支持模型文件热更换，支持模型框架：sklearn|xgboost|lightgbm|torch|tensorflow|onnx|catboost。
支持模型类型：模型类型：decision_tree|random_forest|xgboost|lightgbm|logistic_regression。
能支持AB test.能跑评分卡任务也能跑分类任务，并提供API服务。对于评分卡模型，应该返回模型总评分和模型的特征分.不要直接输出决策结果。决策交给下游的内评系统
只负责模型注册、部署与推理。评分刻度参数保存在 Scorecard 模型中，分类与评分的决策阈值属于部署配置。
模型ID应该是Datamind后台维护的识别模型的唯一主键。不应该作为模型注册参数。
模型元数据保存在数据库,金融场景要能审计，要有完善的日志系统。
只对LR才有评分能力呀，其他的decision_tree / random_forest / xgboost / lightgbm / catboost，应该没有评分能力
我已经有了常量组件，配置组件，日志组件，审计组件，存储组件，数据库组件。

我已经有了配置组件，日志组件，AB测试组件，存储组件，数据库组件，评分组件，模型组件，服务组件。

对要对model / version / deployment / experiment进行审计
```text
datamind/core/

├── capability.py
│
├── model/
│   └── adapters/
│
├── inference/
│   ├── __init__.py
│   └── inference.py
│
└── scoring/
    ├── __init__.py
    ├── transformer.py
    ├── scorer.py
    ├── contrib.py
    └── scorecard.py
```

```text
datamind/
├── models/
│   ├── artifact/
│   ├── enums.py
│   ├── errors.py
│   ├── guard.py
│   └── resolver.py
│
├── services/
│   ├── register.py
│   ├── deployer.py
│   └── deleter.py
│
└── runtime/
    ├── backend.py
    ├── loader.py
    ├── router.py
    └── serving/
        ├── classifier_service.py
        └── scoring_service.py
```

```text
datamind/
│
├── core/
│   │
│   ├── scoring/                     # ⭐评分卡系统（核心）
│   │   ├── engine.py                # rule / lr / pipeline scoring
│   │   ├── scorecard.py             # 对外统一Scorecard封装
│   │   ├── runtime.py               # scoring runtime（轻量执行层）
│   │   ├── explain.py               # explain入口
│   │   ├── contrib.py               # feature贡献计算
│   │   ├── transform.py             # WOE / binning 等
│   │   ├── capability.py            # 能力声明
│   │   └── utils.py
│
│   ├── classification/              # ⭐通用分类模型系统
│   │   ├── predictor.py             # sklearn / xgb / lgb统一predict
│   │   ├── explain.py               # feature importance / 可选SHAP接口
│   │   └── utils.py
││   └── common/
│       ├── types.py            # ScoreResponse / ClassifyResponse
│       └── errors.py

├── runtime/                         # ⭐统一推理调度层
│   ├── base.py                     # BaseRuntime
│   ├── scorecard_runtime.py        # scoring runtime封装
│   ├── ml_runtime.py               # ml runtime封装
│   └── factory.py                  # 自动识别模型类型并路由
│
│
├── service/                      # ⭐ BentoML服务层（极薄）
│   ├── app.py                  # BentoML entrypoint
│   ├── schemas.py              # 请求/响应定义
│   ├── deps.py                 # runtime注入
│
│
├── model/                          # ⭐模型加载层
│   ├── loader.py                  # load from file / minio / local
│   ├── registry.py                # model registry（轻量）
│   └── artifacts/
│
│
├── storage/                      # ⭐ 存储层（极简）
│   ├── base.py
│   ├── local.py
│   ├── minio.py
│   └── factory.py
│
│
├── config/                    # ⭐ 配置系统（.env驱动）
│   ├── settings.py            # 总入口
│   ├── scorecard.py           # 评分卡配置
│   ├── classification.py      # 分类配置
│   ├── database.py            # DB配置
│   ├── storage.py             # storage配置
│   └── logging.py             # 日志配置
│
│
├── logging/                        # ⭐最小可观测日志
│   ├── logger.py                  # get_logger
│   ├── context.py                 # trace_id / request_id
│   └── formatter.py               # JSON结构化日志
│
── db/                           # ⭐ 数据库（轻量）
│   ├── session.py
│   ├── models/
│   └── repository.py          # CRUD封装（统一数据访问）
│
├── abtest/                       # ⭐ AB测试（轻量）
│   ├── router.py
│   └── tracker.py

├── utils/
│   ├── json.py
│   ├── time.py
│   └── validation.py
│
│
└── __init__.py
```

```text
datamind/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── model_api.py
│   │   ├── scoring_api.py
│   │   ├── fraud_api.py
│   │   └── management_api.py
│   └── middlewares/
│       ├── __init__.py
│       ├── auth.py
│       └── logging.py
│
├── core/
│   ├── __init__.py
│   ├── enums.py
│   ├── models.py
│   ├── database.py
│   ├── exceptions.py
│   ├── model_registry.py
│   ├── model_loader.py
│   ├── inference.py
│   ├── ab_test.py
│   └── log_manager.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── logging_config.py
│
├── utils/
│   ├── __init__.py
│   └── validators.py
│
├── bento_services/
│   ├── __init__.py
│   ├── scoring_service.py
│   └── fraud_service.py
│
├── migrations/
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   └── test_api.py
│
├── logs/
│   └── .gitkeep
│
└── models_storage/
    └── .gitkeep

datamind/
│
├── api/
│   ├── routers/
│   │   ├── model.py
│   │   ├── scoring.py
│   │   ├── fraud.py
│   │   └── management.py
│   │
│   └── middlewares/
│       ├── auth_middleware.py
│       └── logging_middleware.py
│
├── core/
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── ml/
│   │   ├── model_registry.py
│   │   ├── model_loader.py
│   │   └── inference.py
│   │
│   ├── experiment/
│   │   └── ab_test.py
│   │
│   └── logging/
│       ├── manager.py
│       ├── formatters.py
│       ├── filters.py
│       ├── handlers.py
│       └── cleanup.py
│
├── config/
│   ├── settings.py
│   └── logging_config.py
│
├── services/
│   ├── scoring_service.py
│   └── fraud_service.py
│
├── utils/
│   └── validators.py
│
├── migrations/
│
├── tests/
│   ├── api/
│   ├── core/
│   └── integration/
│
├── logs/
│
├── models_storage/
│
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── README.md
```


最新的项目结构
```text
datamind/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── Makefile
│
├── api/                              # API接口层
│   ├── __init__.py
│   ├── dependencies.py               # API依赖（认证、用户等）
│   ├── middlewares/                  # 中间件
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── logging_middleware.py
│   └── routes/                       # 路由模块
│       ├── __init__.py
│       ├── model_api.py               # 模型管理API
│       ├── scoring_api.py              # 评分卡API
│       ├── fraud_api.py                 # 反欺诈API
│       └── management_api.py            # 管理API
│
├── core/                              # 核心业务逻辑
│   ├── __init__.py
│   │
│   ├── db/                            # 数据库模块
│   │   ├── __init__.py
│   │   ├── database.py                 # 数据库连接管理
│   │   ├── models.py                    # SQLAlchemy数据库模型
│   │   └── enums.py                      # 枚举定义
│   │
│   ├── ml/                             # 机器学习模块
│   │   ├── __init__.py
│   │   ├── model_registry.py            # 模型注册中心
│   │   ├── model_loader.py               # 模型热加载器
│   │   ├── inference.py                   # 统一推理引擎
│   │   └── exceptions.py                   # 异常定义
│   │
│   ├── experiment/                      # 实验模块
│   │   ├── __init__.py
│   │   └── ab_test.py                     # A/B测试管理器
│   │
│   └── logging/                         # 日志模块（您的完整实现）
│       ├── __init__.py
│       ├── manager.py
│       ├── formatters.py
│       ├── filters.py
│       ├── handlers.py
│       ├── cleanup.py
│       ├── context.py
│       └── debug.py
│
├── config/                             # 配置文件
│   ├── __init__.py
│   ├── settings.py                       # 应用配置
│   └── logging_config.py                  # 日志配置
│
├── utils/                               # 工具函数
│   ├── __init__.py
│   └── validators.py                      # 数据验证器
│
├── templates/                           # HTML模板（UI界面）
│   ├── base.html                          # 基础模板
│   ├── index.html                          # 首页/仪表盘
│   ├── models.html                          # 模型列表
│   ├── model_detail.html                      # 模型详情
│   ├── register.html                          # 模型注册
│   ├── deployments.html                        # 部署管理
│   ├── audit.html                              # 审计日志
│   ├── 404.html                                # 404错误页面
│   └── error.html                              # 错误页面
│
├── static/                              # 静态文件
│   ├── css/
│   │   ├── style.css                      # 主样式
│   │   └── admin.css                       # 管理样式
│   └── js/
│       ├── main.js                          # 主脚本
│       ├── models.js                          # 模型管理脚本
│       ├── register.js                         # 注册页面脚本
│       └── charts.js                            # 图表脚本
│
├── migrations/                         # 数据库迁移
│             ├── alembic.ini
│             ├── cript.py.mako
│             ├── env.py
│             ├── __init__.py
│             └── versions
│                 └── 20240315_initial.py
│
├── scripts/                            # 脚本工具
│   ├── init_db.py
│   ├── backup_db.py
│   └── migrate_data.py
│
├── tests/                              # 测试目录
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_api.py
│   └── test_inference.py
│
├── logs/                               # 日志目录（运行时创建）
│   ├── Datamind.log
│   ├── Datamind.error.log
│   ├── access.log
│   ├── audit.log
│   └── performance.log
│
├── models/                             # 模型文件存储
│   ├── MDL_20240315_ABCD1234/          # 每个模型一个目录
│   │   ├── versions/
│   │   │   ├── model_1.0.0.pkl
│   │   │   └── model_2.0.0.pkl
│   │   └── latest -> versions/model_2.0.0.pkl
│   └── MDL_20240316_EFGH5678/
│       ├── versions/
│       │   └── model_1.0.0.json
│       └── latest -> versions/model_1.0.0.json
├── storage                           # 存储
│      ├── __init__.py
│      ├── base.py
│      ├── local_storage.py
│      ├── s3_storage.py
│      ├── minio_storage.py
│      ├── models
│            ├── __init__.py
│            ├── model_storage.py
│            └── version_manager.py
│
├── docs/                               # 文档
│   ├── api.md
│   ├── deployment.md
│   └── user_guide.md
│
├── main.py                             # 应用入口
├── .env                                 # 本地环境变量（不提交）
└── .flake8                              # 代码检查配置
```

# 安装CLI
pip install -e .

# 注册模型
datamind model register \
    --file models/credit_model.pkl \
    --name "信用评分卡v1" \
    --type logistic_regression \
    --framework sklearn \
    --task scoring \
    --version 1.0.0 \
    --features age,income,education \
    --user admin

# 列出模型
datamind model list --task scoring --format table

# 查看模型详情
datamind model info mod_202401151030_abc12345

# 查询审计日志
datamind audit list --days 7 --user admin

# 实时查看日志
datamind log tail --file app --follow

# 搜索日志
datamind log search "ERROR" --file error --days 1

# 导出审计日志
datamind audit export --days 30 --output audit.json

# 查看帮助
datamind --help
datamind model --help

# 管理控制台

管理控制台根据当前用户的权限显示可用页面和操作入口。具备对应写权限时，
可直接注册模型、创建部署与路由、配置实验及分组、管理用户与角色，并提交
模型装载、重新装载和卸载请求。危险操作通过二次确认执行，所有写操作均受
权限校验、CSRF 防护和审计记录约束。

模型注册采用文件上传；其他创建操作使用结构化表单。列表行末的“管理”入口
只展示当前资源状态允许且当前用户有权执行的操作。

## 查询与导出

管理控制台的列表页面支持普通关键词查询和字段化查询。查询条件在当前
页面的数据范围内生效，并会同时应用于分页、排序和数据导出。

### 查询方式

| 查询方式 | 格式 | 示例 | 说明 |
|---|---|---|---|
| 普通关键词 | `<关键词>` | `scorecard` | 在当前页面支持的文本字段中进行不区分大小写的模糊匹配 |
| 字段查询 | `<字段>:<值>` | `status:active` | 对指定文本字段进行不区分大小写的完整匹配 |
| 带空格的值 | `<字段>:"<值>"` | `model:"credit score"` | 使用引号保留值中的空格 |
| 组合查询 | `<条件> <条件>` | `model:scorecard status:active` | 多个条件之间使用 AND 关系 |
| 字段与关键词组合 | `<字段>:<值> <关键词>` | `status:active sklearn` | 字段条件与普通关键词同时生效 |

字段名支持连字符和下划线两种写法，例如 `model-name` 与
`model_name` 等价。输入当前页面不支持的字段时，控制台会返回该页面
可用的字段列表。

### 时间查询

时间字段支持日期、具体时间、闭合范围和开放范围。`time` 是当前页面
主要时间字段的别名。

| 查询方式 | 示例 | 说明 |
|---|---|---|
| 单日 | `time:2026-08-18` | 查询该本地自然日的全部记录 |
| 单日（斜线格式） | `time:2026/08/18` | 与 `2026-08-18` 等价 |
| 日期范围 | `time:2026-08-17..2026-08-18` | 包含起始日和结束日全天 |
| 时间范围 | `time:2026/08/17 00:00:00..2026/08/18 23:59:59` | 按具体时间查询，范围两端均包含 |
| 起始时间开放 | `created_at:2026-08-17..` | 查询指定日期及其后的记录 |
| 结束时间开放 | `occurred_at:..2026-08-18` | 查询截至指定日期结束的记录 |
| ISO 8601 时间 | `started_at:2026-08-18T09:30:00+08:00..` | 支持 `T`、`Z` 和 `±HH:MM` 时区偏移 |

未提供时区偏移的时间按 `DATAMIND_LOG_TIMEZONE` 配置解析，再统一转换为
UTC 查询。单独输入具体时间表示匹配该时间点；日期范围的结束日期则
自动扩展到当天结束。

### 页面查询字段

- 模型：`model_id`、`name`、`framework`、`model_type`、`task_type`、
  `status`、`created_at`、`updated_at`、`deleted_at`、`restored_at`、
  `archived_at`。别名：`id`、`model`、`time`；`time` 对应
  `updated_at`。
- 版本：`version_id`、`model_id`、`model_name`、`model_version`、
  `framework`、`status`、`created_at`、`updated_at`、`deleted_at`、
  `restored_at`、`archived_at`。别名：`id`、`model`、`version`、
  `time`；`time` 对应 `updated_at`。
- 部署：`deployment_id`、`model_id`、`version_id`、`model_name`、
  `model_version`、`environment`、`framework`、`rollout_type`、`role`、
  `status`、`created_at`、`updated_at`、`effective_from`、
  `effective_to`。别名：`id`、`model`、`version`、`time`；`time`
  对应 `updated_at`。
- 路由：`routing_id`、`deployment_id`、`model_name`、`model_version`、
  `environment`、`rollout_type`、`rollout_group`、`description`、
  `created_at`、`updated_at`。别名：`id`、`model`、`version`、
  `time`；`time` 对应 `updated_at`。
- 运行实例：`runtime_id`、`deployment_id`、`model_id`、`version_id`、
  `model_name`、`model_version`、`worker_id`、`framework`、`status`、
  `created_at`、`updated_at`、`loaded_at`、`unloaded_at`、
  `last_heartbeat_at`。别名：`id`、`model`、`version`、`worker`、
  `time`；`time` 对应 `updated_at`。
- API 调用：`request_id`、`model_id`、`model_name`、`model_version`、
  `source`、`status`、`user`、`ip`、`created_at`、`updated_at`。
  别名：`id`、`model`、`version`、`time`；`time` 对应
  `created_at`。
- 决策记录：`decision_id`、`request_id`、`model_id`、`version_id`、
  `deployment_id`、`model_name`、`model_version`、`source`、`strategy`、
  `subject_key`、`subject_type`、`decision`、`created_at`、`updated_at`、
  `decided_at`。别名：`id`、`model`、`version`、`subject`、`time`；
  `time` 对应 `decided_at`。
- 执行记录：`execution_id`、`decision_id`、`request_id`、`model_id`、
  `version_id`、`deployment_id`、`model_name`、`model_version`、
  `execution_type`、`status`、`error_type`、`error`、`created_at`、
  `updated_at`、`started_at`、`finished_at`。别名：`id`、`model`、
  `version`、`type`、`time`；`time` 对应 `started_at`。
- 实验：`experiment_id`、`model_id`、`name`、`model_name`、
  `environment`、`status`、`created_at`、`updated_at`、
  `effective_from`、`effective_to`。别名：`id`、`experiment`、`model`、
  `time`；`time` 对应 `updated_at`。
- 分组：`variant_id`、`experiment_id`、`experiment_name`、`name`、
  `deployment_id`、`model_name`、`model_version`、`status`、`created_at`、
  `updated_at`。别名：`id`、`variant`、`experiment`、`model`、
  `version`、`time`；`time` 对应 `updated_at`。
- 审计记录：`audit_id`、`action`、`target_type`、`target_id`、`user`、
  `source`、`status`、`request_id`、`trace_id`、`created_at`、
  `updated_at`、`occurred_at`。别名：`id`、`time`；`time` 对应
  `occurred_at`。
- 用户：`user_id`、`username`、`display_name`、`email`、`status`、
  `created_at`、`updated_at`、`deleted_at`、`last_login_at`。别名：
  `id`、`user`、`time`；`time` 对应 `updated_at`。
- 角色：`role_id`、`name`、`description`、`status`、`created_at`、
  `updated_at`、`deleted_at`。别名：`id`、`role`、`time`；`time`
  对应 `updated_at`。

# 测试
python -m unittest tests/test_logging_config.py
python -m unittest tests/test_logging_config.py -v

# 测试确保project.toml:
[tool.pytest.ini_options]
pythonpath = ["."]

pytest tests/ --cov=datamind --cov-branch --cov-report=term-missing

python -m pytest tests\ab_test --cov=datamind/ab_test --cov-branch --cov-report=term-missing

from core.logging import LogManager

现在您的 Datamind 平台拥有完整的UI管理界面，包括：

    仪表盘 - 系统概览、统计图表

    模型管理 - 列表查看、详情页面、模型操作

    模型注册 - 表单上传、特征定义

    部署管理 - 创建部署、查看状态、健康检查

    审计日志 - 日志筛选、查看、导出

所有页面都与您现有的API和日志系统完美集成。

这些静态文件提供了完整的UI交互功能：

    admin.css - 管理界面样式，包括：

        侧边栏布局

        卡片和表格样式

        表单和按钮样式

        响应式设计

    models.js - 模型管理功能：

        模型列表渲染

        筛选和搜索

        模型操作（激活、停用、设为生产等）

        状态徽章显示

    register.js - 模型注册功能：

        表单验证

        JSON编辑器

        文件上传

        预览功能

    charts.js - 图表功能：

        调用趋势图表

        模型类型分布

        性能监控图表

        响应式更新

这些脚本提供了完整的项目管理功能：

    init_db.py - 数据库初始化

    backup_db.py - 数据库备份和恢复

    migrate_data.py - 数据迁移

    benchmark.py - 性能测试

    Makefile - 项目管理命令

    requirements-dev.txt - 开发依赖

    pre-commit - 代码质量检查

这些中间件提供了完整的功能：

    认证中间件 - JWT、API Key、Basic Auth支持

    日志中间件 - 详细的请求/响应日志

    限流中间件 - 基于Redis或内存的限流

    CORS中间件 - 跨域支持

    性能中间件 - 性能监控

    安全中间件 - 安全头、IP白名单、请求大小限制

    请求验证中间件 - 时间戳、签名验证

所有中间件都与您的日志系统完美集成，提供完整的审计和监控功能。

这个更新后的 main.py 具有以下特点：

    完整的中间件集成 - 按照正确顺序注册所有中间件

    启动时加载生产模型 - 自动加载生产环境的模型

    改进的错误处理 - UI和API有不同的错误处理

    更详细的健康检查 - 包含模型加载状态

    调试模式配置信息 - 仅在调试模式可用

    完善的审计日志 - 所有重要操作都有日志记录

    用户信息传递 - 从认证中间件获取用户信息

中间件执行顺序：

    请求ID（最外层）

    CORS和安全头

    IP白名单和请求大小限制

    请求验证（时间戳、签名）

    性能监控

    认证

    限流

    日志（最内层，记录所有信息）

##
``` model_registry 使用示例
# 注册评分卡模型
model_id = model_registry.register_model(
    model_name="credit_score_v2",
    model_version="1.0.0",
    task_type="scoring",
    model_type="xgboost",
    framework="xgboost",
    input_features=["age", "income", "credit_history"],
    created_by="admin",
    model_file=open("scorecard.pkl", "rb")
)

# 注册反欺诈模型并配置风险等级
model_id = model_registry.register_model(
    model_name="fraud_detector_v3",
    model_version="1.0.0",
    task_type="fraud_detection",
    model_type="lightgbm",
    framework="lightgbm",
    input_features=["ip_address", "device_id", "amount"],
    created_by="admin",
    model_file=open("model.txt", "rb"),
    risk_config={
        "levels": {
            "low": {"max": 0.2},
            "medium": {"min": 0.2, "max": 0.5},
            "high": {"min": 0.5, "max": 0.8},
            "very_high": {"min": 0.8}
        }
    }
)

```

# 启动 Datamind 服务

根据项目的架构，Datamind 有多个服务组件需要启动。以下是完整的启动指南：

---

# 1. 环境准备

## 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

## 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，修改数据库连接等配置
vim .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

`.env` 包含数据库密码、存储密钥和 JWT 签名密钥，不应提交到版本库。
CLI 登录成功后会在当前操作系统用户目录保存受限凭据，后续命令自动
认证和续期。`DATAMIND_ACCESS_TOKEN` 仅用于自动化覆盖，不应写入
共享的 `.env`。

首次初始化前还需要配置管理员凭据：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=<strong-password>
```

管理员用户名默认使用 `admin`。初始化完成后，应从运行环境中移除
`DATAMIND_INIT_ADMIN_PASSWORD`。管理员密码未配置时同样使用 `admin`；生产
环境应在初始化前覆盖该默认值。

## 启动依赖服务

```bash
# 使用 Docker Compose 启动 PostgreSQL 和 Redis
docker-compose up -d postgres redis

# 或手动启动 PostgreSQL 和 Redis
```

## 初始化数据库

```bash
# 执行数据库迁移
alembic upgrade head

# 首次部署时创建系统管理员
datamind init

# 使用初始化时设置的管理员密码登录
datamind login --username admin
```

---

# 2. 启动主 API 服务

## 开发模式

```bash
# 使用 uvicorn 直接启动（支持热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 或使用 Python 直接运行
python main.py
```

## 生产模式

```bash
# 使用 gunicorn + uvicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# 或使用 uvicorn 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 验证服务

```bash
# 访问健康检查接口
curl http://localhost:8000/health
```

浏览器访问：

```
http://localhost:8000/api/docs
```

---

# 3. 启动 BentoML 模型服务

## 评分卡服务

```bash
# 进入 serving 目录
cd serving

# 启动评分卡服务
bentoml serve scoring_service:service --reload --port 3001

# 或生产模式
bentoml serve scoring_service:service --production --port 3001
```

## 反欺诈服务

```bash
cd serving

bentoml serve fraud_service:service --reload --port 3002

# 或生产模式
bentoml serve fraud_service:service --production --port 3002
```

## 验证模型服务

```bash
# 健康检查
curl http://localhost:3001/health
curl http://localhost:3002/health
```

测试预测：

```bash
curl -X POST http://localhost:3001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "MDL_20240315_ABCD1234",
    "application_id": "TEST001",
    "features": {"age": 35, "income": 50000}
  }'
```

---

# 4. 使用 Docker Compose 一键启动所有服务

## 启动

```bash
docker-compose up -d
```

## 查看日志

```bash
docker-compose logs -f
```

## 停止

```bash
docker-compose down
```

---

# docker-compose.yml 示例

```yaml
version: '3.8'

services:

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: datamind
      POSTGRES_USER: datamind
      POSTGRES_PASSWORD: datamind123
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - datamind-network

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - datamind-network

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio-data:/data
    command: server /data --console-address ":9001"
    networks:
      - datamind-network

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://datamind:datamind123@postgres:5432/datamind
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./models_storage:/app/models_storage
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - datamind-network

  scoring-service:
    build:
      context: datamind/serving
      dockerfile: docker/Dockerfile
    ports:
      - "3001:3000"
    environment:
      - SERVICE_TYPE=scoring
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://datamind:datamind123@postgres:5432/datamind
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./models_storage:/app/models_storage
    depends_on:
      - postgres
      - redis
      - api
    networks:
      - datamind-network

  fraud-service:
    build:
      context: datamind/serving
      dockerfile: docker/Dockerfile
    ports:
      - "3002:3000"
    environment:
      - SERVICE_TYPE=fraud
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://datamind:datamind123@postgres:5432/datamind
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./models_storage:/app/models_storage
    depends_on:
      - postgres
      - redis
      - api
    networks:
      - datamind-network

networks:
  datamind-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
  minio-data:
```

---

# 5. Makefile 快捷命令

```bash
make help
make init-db
make run
make docker-up
make docker-down
make docker-logs
make test
make format
make lint
```

---

# 6. CLI 工具

```bash
datamind --help

datamind health check
datamind health db
datamind health redis

datamind model list

datamind log tail access -f
```

---

# 7. 访问服务

## API 服务

```
http://localhost:8000/api/docs
http://localhost:8000/health
http://localhost:8000/ui
```

## 评分卡服务

```
http://localhost:3001/predict
http://localhost:3001/health
http://localhost:3001/metrics
```

## 反欺诈服务

```
http://localhost:3002/predict
http://localhost:3002/explain
http://localhost:3002/health
```

## 其他服务

```
MinIO Console
http://localhost:9001
用户名: minioadmin
密码: minioadmin

PostgreSQL
localhost:5432

Redis
localhost:6379
```

---

# 8. 启动顺序建议

```bash
# 启动依赖
docker-compose up -d postgres redis minio

# 初始化数据库
python scripts/init_db.py
alembic upgrade head

# 启动 API
uvicorn main:app --host 0.0.0.0 --port 8000 &

# 注册初始模型
python scripts/seed_data.py

# 启动模型服务
cd serving && bentoml serve scoring_service:service --port 3001 &
cd serving && bentoml serve fraud_service:service --port 3002 &
```

---

# 开发环境一键启动

```bash
./scripts/start-dev.sh
```

---

# 9. 健康检查脚本

`scripts/check-health.sh`

```bash
#!/bin/bash

echo "检查 Datamind 服务状态"

curl -s http://localhost:8000/health
curl -s http://localhost:3001/health
curl -s http://localhost:3002/health
```

---

# 10. 常见问题

## 数据库连接失败

```bash
docker ps | grep postgres
echo $DATABASE_URL
psql $DATABASE_URL
```

## 端口占用

```bash
lsof -i :8000
lsof -i :3001
lsof -i :3002
```

## 模型加载失败

```bash
ls -la models_storage/
datamind model list
```

## 查看日志

```bash
tail -f logs/datamind.log
tail -f logs/access.log
tail -f logs/datamind.error.log
```

---

# 总结

启动 Datamind 的基本流程：

1. 安装依赖
2. 配置环境变量
3. 启动 PostgreSQL / Redis / MinIO
4. 初始化数据库
5. 启动 API
6. 启动模型服务
7. 验证服务健康状态

---

# 最简单启动方式

```bash
docker-compose up -d
```

或

```bash
./scripts/start-dev.sh
```

# Makefile 使用方法

## 基础命令

```bash
# 查看所有可用命令
make help

# 安装依赖
make install
make dev

# 运行服务
make run           # 开发模式
make run-prod      # 生产模式
make run-all       # 运行所有服务

# 数据库操作
make init-db
make migrate
make migrate-create
make backup

# Docker 操作
make docker-up
make docker-down
make docker-logs

# 代码质量
make lint
make format
make test

# 监控调试
make health
make logs
make stats
make shell
```

---

## 组合命令示例

```bash
# 完整开发流程
make clean        # 清理缓存
make dev          # 安装依赖
make init-db      # 初始化数据库
make migrate      # 执行迁移
make run          # 启动服务

# Docker 部署
make docker-build  # 构建镜像
make docker-up     # 启动容器
make docker-logs   # 查看日志
make docker-down   # 停止容器
```

---

该 `Makefile` 提供了完整的项目管理功能，涵盖：

- 开发环境初始化
- 服务运行
- 数据库迁移
- Docker 部署
- 代码质量检查
- 监控与调试

基本覆盖了 **开发、测试、部署、运维** 的全部流程。
例如，如果要覆盖 master 分支：

## 拉取最新代码
```bash
git fetch origin
git reset --hard origin/master
```

# Datamind 组件调试顺序建议

按照依赖关系，从底层到上层逐步调试。以下是推荐的调试顺序：

---

# 第一阶段：基础组件（无外部依赖）

## 1. core/logging/ - 日志系统

```bash
# 测试日志系统
python -c "
from core.logging import log_manager
from config.logging_config import LoggingConfig

config = LoggingConfig.load()
log_manager.initialize(config)
log_manager.log_audit('TEST', 'system', details={'test': 'logging'})
print('✅ 日志系统测试完成')
"
```

## 2. core/db/enums.py - 枚举定义

```bash
python -c "
from core.db.enums import TaskType, ModelType, Framework
print(f'任务类型: {list(TaskType)}')
print(f'模型类型: {list(ModelType)}')
print(f'框架: {list(Framework)}')
"
```

## 3. config/settings.py - 配置系统

```bash
python -c "
from config import settings
print(f'应用名称: {settings.APP_NAME}')
print(f'环境: {settings.ENV}')
print(f'数据库: {settings.DATABASE_URL}')
"
```

## 4. core/db/models.py - 数据库模型

```bash
python -c "
from core.db.models import Base
print(f'模型数量: {len(Base.metadata.tables)}')
for table in Base.metadata.tables:
    print(f'  - {table}')
"
```

---

# 第二阶段：数据层

## 5. core/db/database.py - 数据库连接

```bash
python -c "
from core.db import db_manager
from config import settings

db_manager.initialize(settings.DATABASE_URL)
with db_manager.session_scope() as session:
    result = session.execute('SELECT 1').scalar()
    print(f'数据库连接: {result}')
"
```

## 6. migrations/ - 数据库迁移

```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
alembic current
```

---

# 第三阶段：核心业务层

## 7. core/ml/exceptions.py - 异常定义

```bash
python -c "
from core.ml.exceptions import ModelNotFoundException
try:
    raise ModelNotFoundException('test')
except ModelNotFoundException as e:
    print(f'✅ 异常测试: {e}')
"
```

## 8. core/ml/model_registry.py - 模型注册

```bash
python -c "
from core.ml import model_registry
models = model_registry.list_models()
print(f'当前模型数量: {len(models)}')
"
```

## 9. core/ml/model_loader.py - 模型加载器

```bash
python -c "
from core.ml import model_loader
loaded = model_loader.get_loaded_models()
print(f'已加载模型: {loaded}')
"
```

## 10. core/ml/inference.py - 推理引擎

```bash
python -c "
from core.ml import inference_engine
stats = inference_engine.get_stats()
print(f'推理引擎统计: {stats}')
"
```

## 11. core/experiment/ab_test.py - A/B测试

```bash
python -c "
from core.experiment import ab_test_manager
stats = ab_test_manager.get_stats()
print(f'AB测试统计: {stats}')
"
```

---

# 第四阶段：API层

## 12. api/dependencies.py - API依赖

```bash
python -c "
from api.dependencies import get_api_key, get_current_user
print('✅ API依赖测试通过')
"
```

## 13. api/middlewares/ - 中间件

```bash
python -c "
from api.middlewares import (
    AuthenticationMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware
)
print('✅ 中间件导入成功')
"
```

## 14. api/routes/ - API路由

```bash
cd tests

pytest test_model_api.py -v
pytest test_scoring_api.py -v
pytest test_fraud_api.py -v
pytest test_management_api.py -v
```

## 15. main.py - 主应用

```bash
uvicorn main:app --reload --port 8000
```

测试：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/docs
```

---

# 第五阶段：服务层

## 16. serving/base.py - 基础服务类

```bash
cd serving

python -c "
from base import BaseModelService
service = BaseModelService('test', 'scoring')
print('✅ 基础服务测试通过')
"
```

## 17. serving/scoring_service.py - 评分卡服务

```bash
cd serving

bentoml serve scoring_service:service --reload --port 3001
```

测试：

```bash
curl http://localhost:3001/health
```

## 18. serving/fraud_service.py - 反欺诈服务

```bash
cd serving

bentoml serve fraud_service:service --reload --port 3002
```

测试：

```bash
curl http://localhost:3002/health
```

---

# 第六阶段：存储层

## 19. storage/base.py - 存储基类

```bash
python -c "
from storage.base import StorageBackend
print('✅ 存储基类测试通过')
"
```

## 20. storage/local_storage.py - 本地存储

```bash
python -c "
from storage.local_storage import LocalStorage
storage = LocalStorage('./test_storage')
print('✅ 本地存储测试通过')
"
```

## 21. storage/models/ - 模型存储

```bash
python -c "
from storage.models import ModelStorage, VersionManager
print('✅ 模型存储测试通过')
"
```

---

# 第七阶段：CLI工具

```bash
pip install -e .

datamind --help
datamind health check
datamind model list
datamind log config
```

---

# 第八阶段：UI界面

启动主服务后访问：

```
http://localhost:8000/ui
http://localhost:8000/ui/models
http://localhost:8000/ui/register
```

---

# 完整调试脚本

`scripts/debug_order.sh`

```bash
#!/bin/bash

set -e

echo "========================================="
echo "Datamind 组件调试顺序"
echo "========================================="

echo -e "\n📦 阶段1: 基础组件"
python -c "from core.logging import log_manager; print('✅ 日志系统')"
python -c "from core.db.enums import TaskType; print('✅ 枚举定义')"
python -c "from config import settings; print('✅ 配置系统')"
python -c "from core.db.models import Base; print('✅ 数据库模型')"

echo -e "\n🗄️ 阶段2: 数据层"
python -c "
from core.db import db_manager
from config import settings
db_manager.initialize(settings.DATABASE_URL)
print('✅ 数据库连接')
"

echo -e "\n⚙️ 阶段3: 核心业务"
python -c "from core.ml import model_registry; print('✅ 模型注册')"
python -c "from core.ml import model_loader; print('✅ 模型加载')"
python -c "from core.ml import inference_engine; print('✅ 推理引擎')"
python -c "from core.experiment import ab_test_manager; print('✅ AB测试')"

echo -e "\n🌐 阶段4: API层"
python -c "from api import api_router; print('✅ API路由')"

echo -e "\n🚀 阶段5: 服务层"
python -c "from serving.base import BaseModelService; print('✅ 服务基类')"

echo -e "\n💾 阶段6: 存储层"
python -c "from storage.base import StorageBackend; print('✅ 存储基类')"

echo -e "\n⌨️ 阶段7: CLI工具"
command -v datamind >/dev/null && echo "✅ CLI工具" || echo "⚠️ CLI未安装"

echo -e "\n========================================="
echo "所有组件导入测试完成"
echo "========================================="
```

---

# 调试建议

## 1. 先单元测试，后集成测试

```bash
pytest tests/unit/
pytest tests/integration/
```

## 2. 使用调试模式

```bash
export DATAMIND_LOG_LEVEL=DEBUG
export DATAMIND_DEBUG=true

make run
```

## 3. 监控日志

```bash
tail -f logs/datamind.log
grep "ModelRegistry" logs/datamind.log
```

## 4. 使用健康检查

```bash
make health
curl http://localhost:8000/health | jq '.'
```

## 5. 逐步添加数据

```bash
datamind model register --name test_model ...
datamind model predict ...
```

---

# 调试检查清单

- 日志系统正常工作
- 数据库连接成功
- 配置加载正确
- 模型可以注册
- 模型可以加载
- API路由可访问
- 中间件正常工作
- 评分卡服务可启动
- 反欺诈服务可启动
- 存储功能正常
- CLI命令可用
- UI界面可访问

---

按照这个顺序调试，可以确保 **每个组件在依赖它的组件之前就被验证为正常工作**。


您要的是这样的纯文本（所有 markdown 符号都原样显示，不进行任何渲染）：


## 安装成包
```bash
 pip install -e .
```
## 删除目录下所有文件
```bash
 rm -rf ./* ./.[!.]* ./..?* 2>/dev/null
```

测试
```bash
pytest tests/test_logging.py -v -W default

# 运行所有测试
pytest tests/core/ml/ -v

# 运行特定测试文件
pytest tests/core/ml/test_model_registry.py -v
pytest tests/core/ml/test_model_loader.py -v
pytest tests/core/ml/test_inference.py -v

# 运行特定测试类
pytest tests/core/ml/test_model_registry.py::TestModelRegistry -v

# 运行特定测试方法
pytest tests/core/ml/test_inference.py::TestInferenceEngine::test_predict_scorecard_success -v

# 带覆盖率报告
pytest tests/core/ml/ --cov=datamind.core.ml --cov-report=html
```
## 安装包
```bash
pip install semver -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# 安装 BentoML
pip install bentoml

# 本地启动评分卡服务
python scripts/start_bentoml_service.py serve --service scoring --port 8700

# 启动反欺诈服务
python scripts/start_bentoml_service.py serve --service fraud --port 3001

# 构建 Bento 包
python scripts/start_bentoml_service.py build --service scoring --version 1.0.0

# 容器化服务
python scripts/start_bentoml_service.py containerize --service scoring --tag datamind-scoring:latest

# 测试服务
curl -X POST http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "TEST_001",
    "features": {"age": 35, "income": 50000}
  }'

# 健康检查
curl http://localhost:8700/health
```



## 训练
```bash
python examples/scorecard/train.py
python examples/classification/train.py
```

详细说明参见 `examples/README.md`。

步骤
docker compose down -v
docker compose up -d

# 1. 删除现有数据库
docker exec -it postgres psql -U datamind -d postgres -c "DROP DATABASE IF EXISTS datamind;"

# 2. 重新创建数据库
docker exec -it postgres psql -U datamind -d postgres -c "CREATE DATABASE datamind OWNER datamind;"

# 3. 重新初始化数据库（现在会创建小写枚举）
python -m alembic upgrade head

# 4.确认枚举类型
docker exec -it postgres psql -U datamind -d datamind -c "SELECT enum_range(NULL::audit_action_enum);"


docker exec -it postgres psql -U datamind -d postgres -c "DROP DATABASE IF EXISTS datamind;"
docker exec -it postgres psql -U datamind -d postgres -c "CREATE DATABASE datamind OWNER datamind;"
python -m alembic upgrade head

## 检查生产模型
```bash
python -c "
from datamind.core.db.database import db_manager
from datamind.core.model import get_model_registry

db_manager.initialize()
registry = get_model_registry()

# 列出所有评分卡模型
models = registry.list_models(task_type='scoring')
print('所有评分卡模型:')
for m in models:
    print(f'  {m[\"model_id\"]}: {m[\"model_name\"]} v{m[\"model_version\"]} (生产: {m[\"is_production\"]}, 状态: {m[\"status\"]})')
"
```

## 创建部署记录
```bash
python -c "
from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models import ModelDeployment
from datamind.core.model import get_model_registry
from datamind.config import get_settings
from datetime import datetime

db_manager.initialize()
settings = get_settings()
registry = get_model_registry()

models = registry.list_models(task_type='scoring', is_production=True)

if models:
    print(f'找到 {len(models)} 个生产模型')
    for model in models:
        model_id = model['model_id']
        model_version = model['model_version']
        
        with get_db() as session:
            existing = session.query(ModelDeployment).filter_by(
                model_id=model_id,
                environment=settings.app.environment.value
            ).first()
            
            if not existing:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                deployment = ModelDeployment(
                    deployment_id=f'DEPLOY_{model_id}_{timestamp}',
                    model_id=model_id,
                    model_version=model_version,
                    environment=settings.app.environment.value,
                    is_active=True,
                    deployed_by='system'
                )
                session.add(deployment)
                session.commit()
                print(f'部署记录创建成功: {model_id} v{model_version} -> {settings.app.environment.value}')
            else:
                print(f'部署记录已存在: {model_id} v{model_version} -> {settings.app.environment.value}')
else:
    print('没有找到生产环境的评分卡模型')
"
```

## 创建 A/B 测试
```bash
python -c "
from datetime import datetime, timedelta
from datamind.core.db.database import db_manager
from datamind.core.experiment.ab_test import ab_test_manager

db_manager.initialize()

# 替换成你实际的模型ID（去掉末尾的冒号）
champion_model_id = 'MDL_20260416110014_C9A03CA7'
challenger_model_id = 'MDL_20260416110010_89F0A2FF'

# 创建 A/B 测试
test_id = ab_test_manager.create_test(
    test_name='评分卡模型对比测试',
    task_type='scoring',
    groups=[
        {
            'name': 'control',
            'model_id': champion_model_id,
            'weight': 50,
            'description': '对照组，使用主模型'
        },
        {
            'name': 'treatment',
            'model_id': challenger_model_id,
            'weight': 50,
            'description': '实验组，使用挑战者模型'
        }
    ],
    created_by='admin',
    description='测试不同评分卡模型的效果对比',
    traffic_allocation=100.0,
    assignment_strategy='consistent',
    start_date=datetime.now(),
    end_date=datetime.now() + timedelta(days=7),
    metrics=['score', 'probability', 'latency_ms']
)

print(f'A/B测试创建成功！')
print(f'测试ID: {test_id}')
"
```

## 启动 A/B 测试
```bash
python -c "
from datamind.core.db.database import db_manager
from datamind.core.experiment.ab_test import ab_test_manager

db_manager.initialize()

# 替换成上一步创建的 test_id
test_id = 'ABT_20260416110128_6464'

ab_test_manager.start_test(test_id, operator='admin')
print(f'A/B测试已启动: {test_id}')
"

```

## 检查 A/B 测试配置
```bash
python -c "
from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models import ABTestConfig
import json

db_manager.initialize()

with get_db() as session:
    # 查看最新的 A/B 测试
    test = session.query(ABTestConfig).order_by(
        ABTestConfig.created_at.desc()
    ).first()
    
    if test:
        print(f'测试ID: {test.test_id}')
        print(f'测试名称: {test.test_name}')
        print(f'状态: {test.status}')
        print(f'分组配置:')
        for group in test.groups:
            print(f'  - {group[\"name\"]}: model_id={group[\"model_id\"]}, weight={group[\"weight\"]}')
    else:
        print('未找到 A/B 测试')
"
```


## 测试服务
```bash
bentoml serve datamind.serving.scoring_service:ScoringService --reload --port 8700

# 评分服务
DATAMIND_LOG_FILE=scoring.log bentoml serve datamind.serving.scoring_service:ScoringService --port 8700

# 反欺诈服务
DATAMIND_LOG_FILE=fraud.log bentoml serve datamind.serving.fraud_service:FraudService --port 3001
```

## 启动服务
```bash
python datamind/scripts/start_bentoml_service.py scoring --dev
```

## 测试服务
### 低风险请求
```bash
curl -X POST http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "application_id": "TEST_003",
      "customer_id": "CUST_003",
      "model_id": "MDL_20260416110014_C9A03CA7",
      "ab_test_id": "ABT_20260416110128_6464",
      "features": {
        "age": 55,
        "income": 150000,
        "debt_ratio": 0.15,
        "credit_history": 820,
        "employment_years": 20,
        "loan_amount": 30000
      },
      "return_details": true
    }
  }'
```

### 高风险请求
```bash
curl -X POST http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "application_id": "TEST_002",
      "customer_id": "CUST_003",
      "model_id": "MDL_20260416110014_C9A03CA7",
      "ab_test_id": "ABT_20260416110128_6464",
      "features": {
        "age": 20,
        "income": 20000,
        "debt_ratio": 0.8,
        "credit_history": 400,
        "employment_years": 1,
        "loan_amount": 500000
      },
      "return_details": true
    }
  }'
```

### 正常请求
```bash
curl -X POST http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "application_id": "TEST_001",
      "customer_id": "CUST_003",
      "model_id": "MDL_20260416110014_C9A03CA7",
      "ab_test_id": "ABT_20260416110128_6464",
      "features": {
        "age": 35,
        "income": 50000,
        "debt_ratio": 0.3,
        "credit_history": 720,
        "employment_years": 5,
        "loan_amount": 100000
      },
      "return_details": true
    }
  }'
```
### 健康检查
```bash
curl -X POST http://localhost:8700/health -H "Content-Type: application/json" -d '{}'
```

### 列出模型
```bash
curl -X POST http://localhost:8700/models -H "Content-Type: application/json" -d '{}'
```

### 列出模型
```bash
curl -X POST http://localhost:8700/models -H "Content-Type: application/json" -d '{}'
```



## 检查 API 调用记录
```bash
python -c "
from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models.monitoring import ApiCallLog
import json

db_manager.initialize()

with get_db() as session:
    logs = session.query(ApiCallLog).order_by(ApiCallLog.created_at.desc()).limit(5).all()
    print(f'共 {len(logs)} 条记录')
    print()
    
    for i, log in enumerate(logs, 1):
        print(f'--- 记录 {i} ---')
        print(f'  请求ID: {log.request_id}')
        print(f'  应用ID: {log.application_id}')
        print(f'  模型ID: {log.model_id}')
        print(f'  模型版本: {log.model_version}')
        print(f'  端点: {log.endpoint}')
        print(f'  状态码: {log.status_code}')
        print(f'  耗时: {log.processing_time_ms} ms')
        print(f'  任务类型: {log.task_type}')
        print(f'  创建时间: {log.created_at}')
        if log.business_metrics:
            print(f'  业务指标: {json.dumps(log.business_metrics, ensure_ascii=False)}')
        if log.error_message:
            print(f'  错误信息: {log.error_message}')
        print()
"
```
## 查看审计日志
```bash
python -c "
from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models import AuditLog

db_manager.initialize()

with get_db() as session:
    logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(10).all()
    print(f'共 {len(logs)} 条审计记录')
    print('=' * 80)
    for log in logs:
        print(f'时间: {log.created_at}')
        print(f'审计ID: {log.audit_id}')
        print(f'操作: {log.action}')
        print(f'操作人: {log.operator}')
        print(f'资源类型: {log.resource_type}')
        print(f'资源ID: {log.resource_id}')
        print(f'结果: {log.result}')
        if log.details:
            print(f'详情: {log.details}')
        print('-' * 40)
"
```

## 检查性能记录
```bash
python -c "
from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models.monitoring import ModelPerformanceMetrics

db_manager.initialize()

with get_db() as session:
    records = session.query(ModelPerformanceMetrics).order_by(ModelPerformanceMetrics.date.desc()).limit(10).all()
    print(f'共 {len(records)} 条性能记录')
    print('=' * 80)
    for r in records:
        print(f'日期: {r.date}')
        print(f'模型ID: {r.model_id}')
        print(f'模型版本: {r.model_version}')
        print(f'任务类型: {r.task_type}')
        print(f'总请求数: {r.total_requests}')
        print(f'成功数: {r.success_count}')
        print(f'失败数: {r.error_count}')
        print(f'超时数: {r.timeout_count}')
        print(f'平均响应时间: {r.avg_response_time_ms}ms')
        print(f'P95响应时间: {r.p95_response_time_ms}ms')
        print(f'最大响应时间: {r.max_response_time_ms}ms')
        print(f'最小响应时间: {r.min_response_time_ms}ms')
        print(f'平均评分: {r.avg_score}')
        print(f'平均概率: {r.fraud_rate}')
        if r.score_distribution:
            print(f'评分分布: {r.score_distribution}')
        print('-' * 40)
"
```

根据您的项目结构，有以下几种方式启动 BentoML 服务：

方式一：直接使用 BentoML 命令（推荐开发调试）
bash
# 进入 serving 目录
cd /home/zhongsheng/tmp/pycharm_project_888/datamind/serving

# 启动评分卡服务
 bentoml serve datamind.serving.scoring_service:ScoringService --reload

# 或启动反欺诈服务
bentoml serve datamind.serving.fraud_service:FraudService --reload

# 指定端口和主机
bentoml serve datamind.serving.scoring_service:ScoringService --host 0.0.0.0 --port 8000 --reload
方式二：使用项目启动脚本
您项目中有 scripts/start_bentoml_service.py，可以使用它：

bash
cd /home/zhongsheng/tmp/pycharm_project_888

# 启动评分卡服务
python scripts/start_bentoml_service.py --service scoring

# 启动反欺诈服务
python scripts/start_bentoml_service.py --service fraud

# 指定端口
python scripts/start_bentoml_service.py --service scoring --port 8000

# 生产模式（禁用热重载）
python scripts/start_bentoml_service.py --service scoring --no-reload
方式三：打包成 Bento 后部署
bash
cd /home/zhongsheng/tmp/pycharm_project_888

# 构建 Bento
bentoml build

# 查看构建的 Bento
bentoml list

# 本地运行
bentoml serve bento_name:latest --production

# 或打包成 Docker 镜像
bentoml containerize bento_name:latest -t datamind-scoring:latest

# 运行 Docker 容器
docker run -p 8000:8000 datamind-scoring:latest
方式四：使用项目 Makefile
bash
cd /home/zhongsheng/tmp/pycharm_project_888

# 查看可用的 make 命令
make help

# 启动评分卡服务
make serve-scoring

# 启动反欺诈服务
make serve-fraud
测试服务是否正常运行
bash
# 健康检查
curl http://localhost:8000/health

# 评分卡预测
curl -X POST http://localhost:8700/predict \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "TEST_001",
    "features": {"age": 35, "income": 50000, "debt_ratio": 0.35}
  }'

# 反欺诈预测
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "TEST_001",
    "features": {"amount": 10000, "ip_risk": 0.8}
  }'

# 查看已加载模型
curl http://localhost:8000/models


## 键导出代码（推荐）

在项目根目录运行：
```bash
tree -a -I "__pycache__|.git|*.pyc"
```
然后：
```bash
sudo apt-get install python3.12-tk
python3.12 -c "import tkinter; print('tkinter 安装成功')"
pip install code-merger
merge -e py -f merged_output.md
merge -e py -f merged_output.md -s .venv __pycache__ .git .idea .pytest_cache
```
或者一键：
```bash
tar -czf datamind.tar.gz .
```


# 仅 Datamind 核心
pip install -e .

# Datamind + sklearn
pip install -e ".[sklearn]"

# Datamind + XGBoost
pip install -e ".[xgboost]"

# 完整模型框架环境
pip install -e ".[full]"


参考：https://blog.51cto.com/u_16099215/9695963

datamind/models/
├── registry.py          # ⭐ 对外唯一入口（register / load / retire）
├── backend.py           # ⭐ BentoML 封装层
│
├── artifact/            # ⭐ 模型反序列化系统（核心）
│   ├── __init__.py
│   ├── loader.py       # dispatch：framework -> handler
│   ├── registry.py     # handler 注册表
│   ├── io.py           # bytes <-> temp file 工具
│   └── handlers/
│       ├── sklearn.py
│       ├── xgboost.py
│       ├── lightgbm.py
│       ├── torch.py
│       ├── tensorflow.py
│       ├── onnx.py
│       └── catboost.py
│
└── types.py            # （可选）模型元数据/枚举

datamind/models/builder.py


datamind/models/
├── __init__.py
├── register.py
├── loader.py
├── retire.py
├── builder.py
├── backend.py
└── artifact/
    ├── __init__.py
    ├── loader.py
    ├── register.py
    ├── io.py
    └── handlers/

datamind/models/
├── register.py     -> ModelRegister
├── loader.py       -> ModelLoader
├── retire.py       -> ModelRetirer
├── builder.py      -> ModelBuilder
├── backend.py      -> BentoBackend
└── artifact/

datamind/models/
├── __init__.py
│
├── register.py        # 模型注册
├── loader.py          # 模型加载
├── deploy.py          # 上线
├── undeploy.py        # 下线
├── lifecycle.py       # deprecate/disable/archive
│
├── builder.py         # 构建 artifact
├── backend.py         # backend 抽象
│
├── enums.py           # 状态枚举
├── exceptions.py
│
└── artifact/
    ├── __init__.py
    ├── loader.py
    ├── register.py
    ├── io.py
    └── handlers/

datamind/models/artifact/register.py

给出datamind/models/retire.py

给出datamind/models/loader.py

# 元数据表 status
## 1. active

正常模型。

**允许：**

- 注册新版本 ✅
- 上线 deployment ✅
- 创建实验 ✅
- 配路由 ✅

**比如：**

当前主力模型。

---

## 2. deprecated

已废弃（不推荐继续使用），但还没真正停用。

这是最有价值的过渡状态。

**允许：**

- 已有 deployment 继续运行 ✅
- 查询、推理 ✅

**禁止（建议）：**

- 新 deployment ❌
- 新实验 ❌
- 新流量切换 ❌

**可选（看业务）：**

- 注册新版本，一般也不建议 ❌

**典型场景：**

你有 `scorecard-v1`，准备迁移到 `scorecard-v2`，  
`v1` 还在线，但已经不建议继续使用。

这时候：

```python
metadata.status = "deprecated"
```

非常自然。

---

## 3. inactive

停用。

**表示：**

模型已经停止业务使用。

**要求：**

通常所有 deployment 都已经下线。

**禁止：**

- 上线 ❌
- 注册新版本 ❌
- 实验 ❌

**允许：**

- 查询历史记录 ✅
- 审计 ✅

---

## 4. archived

归档。

**表示：**

生命周期彻底结束。

**特点：**

只读。

# 元数据表 status
| 状态 | 是否可推理 | 是否允许新上线 | 语义 |
|------|------------|---------------|------|
| active | 是 | 是 | 正常使用 |
| deprecated | 是（可能还在线） | 否 | 已废弃，建议迁移 |
| inactive | 否 | 否 | 已停用 |
| archived | 否 | 否 | 已归档 |


# 模型状态设计

## 一、Metadata（模型资产状态）

表示：

模型在控制平面是否允许继续参与生命周期操作。

### 建议保留

- `active`
- `deprecated`
- `inactive`
- `archived`

### 语义

| 状态 | 含义 |
|------|------|
| `active` | 正常模型，可继续运营 |
| `deprecated` | 已废弃，不建议新增使用 |
| `inactive` | 已停用，禁止运营 |
| `archived` | 已归档，只读 |

---

## 二、Deployment（运行状态）

表示：

某个版本是否在线服务。

### 保持简单

- `active`
- `inactive`

---

# 三、核心状态约束（最重要）

不是所有组合都合法。

---

## 规则 1：模型注册（Register）

### 动作

```python
ModelRegister.register(...)
```

### 结果

```python
metadata.status = "active"
```

初始没有 deployment：

```python
deployment = None
```

即：

```text
register
↓
metadata = active
```

---

## 规则 2：模型上线（Deploy）

### 动作

```python
ModelDeploy.deploy(...)
```

### 前置条件

必须：

```python
metadata.status == "active"
```

否则禁止：

- `deprecated` → 禁止上线
- `inactive` → 禁止上线
- `archived` → 禁止上线

### 成功后

```python
deployment.status = "active"
```

### 状态约束

| metadata | 能否 deploy |
|------|------|
| `active` | ✅ |
| `deprecated` | ❌ |
| `inactive` | ❌ |
| `archived` | ❌ |

---

## 规则 3：模型下线（Undeploy）

### 动作

```python
ModelUndeploy.undeploy(...)
```

### 前置条件

```python
deployment.status == "active"
```

### 结果

```python
deployment.status = "inactive"
```

**不会影响 metadata。**

即：

```text
metadata = active
deployment = active

↓ undeploy

metadata = active
deployment = inactive
```

---

## 规则 4：模型废弃（Deprecate）

### 动作

```python
ModelDeprecate.deprecate(...)
```

### 状态迁移

```text
active → deprecated
```

### 结果

```python
metadata.status = "deprecated"
```

已有 deployment：

可以继续运行：

```python
deployment.status = "active"
```

但是：

禁止新增 deployment。

### 状态约束

| metadata | deployment |
|------|------|
| `deprecated` | `active`（允许已有） |
| `deprecated` | 新建 `active`（禁止） |

这是灰度迁移最常见场景。

---

## 规则 5：模型停用（Disable）

### 动作

```python
ModelDisable.disable(...)
```

### 前置条件

必须所有 deployment 都已下线：

```python
all(deployment.status == "inactive")
```

否则报错。

### 允许状态迁移

```text
active → inactive
deprecated → inactive
```

### 结果

```python
metadata.status = "inactive"
```

此后：

禁止上线。

---

## 规则 6：模型归档（Archive）

### 动作

```python
ModelArchive.archive(...)
```

### 前置条件

必须：

```python
metadata.status == "inactive"
```

### 结果

```python
metadata.status = "archived"
```

归档后完全只读。

---

# 四、完整状态图

## Metadata State

```text
active
  │
  ├── deploy → Deployment.active
  │
  ├── deprecate
  ▼
deprecated
  │
  ▼
inactive
  │
  ▼
archived
```

## Deployment State

```text
inactive ↔ active
```

但有全局约束：

只有：

```python
metadata.status == "active"
```

deployment 才允许：

```text
inactive → active
```

也就是：

> 模型上线，只有当 `metadata.status = active` 时，`deployment.status` 才能为 `active`

---

# 五、最终合法组合

## 允许

| metadata | deployment |
|------|------|
| `active` | `active` ✅ |
| `active` | `inactive` ✅ |
| `deprecated` | `active` ✅（历史部署） |
| `deprecated` | `inactive` ✅ |
| `inactive` | `inactive` ✅ |
| `archived` | `inactive` ✅ |

---

## 禁止

| metadata | deployment |
|------|------|
| `inactive` | `active` ❌ |
| `archived` | `active` ❌ |
| `deprecated` | 新建 `active` ❌ |


datamind register
datamind deploy
datamind rollback
datamind list
datamind inspect

datamind model register
datamind model list
datamind model delete

datamind model register ...
datamind model list
datamind model delete ...
datamind version list ...


## 能力矩阵

| 能力 | logistic_regression | decision_tree | random_forest | xgboost | lightgbm | catboost |
|------|---------------------|----------------|----------------|----------|-----------|-----------|
| PREDICT_PROBA | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PREDICT_CLASS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PREDICT_LOG_ODDS | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| SHAP | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SHAP_TREE | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SHAP_KERNEL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| FEATURE_IMPORTANCE | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| BATCH_PREDICT | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SCORECARD_WOE | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SCORECARD_LOGIT | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SCORECARD_FEATURE_LOGIT | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SCORECARD_FEATURE_SCORE | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SCORECARD_SCORE | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SCORECARD_EXPORT | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |



# 常用树模型预测接口对照表

| 框架 | 模型类 | 预测类别 | 预测概率 |
|--------|--------|----------|----------|
| Scikit-Learn | `DecisionTreeClassifier` | `predict()` | `predict_proba()` |
| Scikit-Learn | `RandomForestClassifier` | `predict()` | `predict_proba()` |
| XGBoost | `Booster` / `XGBClassifier` | `predict(output_margin=False)` | `predict()` |
| LightGBM | `Booster` | `predict(type="class")` | `predict(type="response")` |
| CatBoost | `CatBoostClassifier` | `predict()` | `predict_proba()` |




## 全量发布（Full）

100% 流量由单个模型处理。

| deployment_id | rollout_type | deployment_group | role     | traffic_ratio |
|---------------|-------------|------------------|----------|---------------|
| dep_v1 | full | prod | champion | 1.0 |

---

## 灰度发布（Canary）

老版本与新版本共同提供服务。

示例：

- v1：90%
- v2：10%

| deployment_id | rollout_type | deployment_group | role       | traffic_ratio |
|---------------|-------------|------------------|------------|---------------|
| dep_v1 | canary | prod | champion   | 0.9 |
| dep_v2 | canary | prod | challenger | 0.1 |

说明：

- 同一个 `deployment_group`
- `traffic_ratio` 之和应等于 `1.0`
- 路由器按流量比例分发请求

---

## 影子发布（Shadow）

线上流量复制给新模型。

用户只看到主模型结果，影子模型仅用于验证。

| deployment_id | rollout_type | deployment_group | role | traffic_ratio |
|---------------|-------------|------------------|------|---------------|
| dep_v1 | full | prod | champion | 1.0 |
| dep_v2 | shadow | shadow | shadow | 1.0 |

说明：

- `champion` 接收正式流量并返回结果
- `shadow` 异步接收镜像流量，但其结果不会进入主响应
- `shadow` 不参与主流量权重求和，`traffic_ratio` 表示独立镜像采样率
- 每个请求只创建一条最终决策；主模型和影子模型分别写入执行记录，
  并通过逻辑 `decision_id` 关联同一条决策
- 执行表不建立数据库外键，记录生命周期由应用事务和表内唯一约束保证
- 影子执行队列已满、超时或预测失败时，不影响主请求结果

---

## A/B Test（AB测试）

多个模型同时对外服务。

示例：

- A模型：50%
- B模型：50%

| deployment_id | rollout_type | deployment_group | role       | traffic_ratio |
|---------------|-------------|------------------|------------|---------------|
| dep_a | ab | exp_001 | champion   | 0.5 |
| dep_b | ab | exp_001 | challenger | 0.5 |

说明：

- 同一个 `deployment_group`
- `traffic_ratio` 之和应等于 `1.0`
- 通常基于用户 ID 哈希进行稳定分流

---

## 字段说明

### rollout_type

发布模式：

```text
full
canary
shadow
ab
```

### deployment_group

部署分组。

表示多个 Deployment 属于同一套流量策略。

示例：

```text
prod
exp_001
exp_002
```

### role

部署角色：

```text
champion
challenger
shadow
```

### traffic_ratio

流量占比：

- Full：固定为 `1.0`
- Canary：多个 Deployment 之和为 `1.0`
- AB：多个 Deployment 之和为 `1.0`
- Shadow：独立镜像采样率，`1.0` 表示镜像全部请求


{
  "task": {
    "classification": {
      "threshold": 0.5,
      "calibration": "isotonic"
    }
  }
}


{
  "classification": {
    "threshold": 0.5
  }
}


# 流量分配

## 设计
```text
一个 Deployment
可以被多个 Routing Rule 引用

一个 Routing Rule
只指向一个 Deployment

Model
 └── Deployment
      ├── dep_v1
      ├── dep_v2
      └── dep_v3

Routing Rule
      ├── rule_01 -> dep_v1
      ├── rule_02 -> dep_v2
      ├── rule_03 -> dep_v3
      └── rule_04 -> dep_v1
```

分组规则：<model_id>_<environment>_<type>_<timestamp>
或者：
full     -> rollout_group = NULL
canary   -> rollout_group = generate_id("rgp")
shadow   -> rollout_group = generate_id("rgp")

if not 0 <= traffic_ratio <= 1:
    raise ValueError(
        f"流量占比必须在 0~1 之间，当前值: {traffic_ratio}"
    )

if rollout_type in {"canary", "shadow"} and not rollout_group:
    raise InvalidRoutingConfigError(
        f"发布类型 '{rollout_type}' 必须指定发布分组"
    )


## 创建部署

python -m datamind.cli.main deploy create scorecard `
  --version 1.0.0 `
  --environment production `
  --rollout full `
  --description "创建部署" `
  --owner admin


## 分流
Deploy（已完成）
   ↓
AB Experiment System（必须先做）
   ↓
Router（依赖 AB 结果）
   ↓
Traffic Split / Shadow / Canary



核心模块：

✔ experiment.py
✔ assignment.py
✔ policy.py


deploy：只负责“部署记录（metadata）”
runtime：只负责“真实模型服务（BentoML / serving）”
service CLI：负责“把模型真正发布成可访问 endpoint 的服务”
router/ab test：负责流量调度



routing/
├── router.py
├── strategies/
│   ├── full.py
│   ├── canary.py
│   ├── shadow.py
│   └── abtest.py

datamind/runtime/

├── backend.py
├── loader.py

├── gateway.py
├── router.py

├── registry.py

├── serving/
│   ├── scoring_service.py
│   └── classifier_service.py


                    Datamind Gateway
                           │
                           ▼
                     RuntimeRouter
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
      Full Route      Canary Route     Shadow Route
          │                │                │
          ▼                ▼                ▼
      Deployment      Deployment      Deployment
          │
          ▼
      ModelLoader
          │
          ▼
       Scorer

datamind/ab_test/      负责实验管理、分桶、记录、统计分析
datamind/runtime/      负责在线服务、模型加载、路由调用



## 实验配置

```json
{
  "assignment_key": "customer_id",
  "traffic_ratio": 0.2,
  "strategy": "stable_hash",
  "variants": [
    {
      "name": "control",
      "deployment_id": "dep_champion",
      "weight": 0.5,
      "is_control": true
    },
    {
      "name": "treatment",
      "deployment_id": "dep_challenger",
      "weight": 0.5,
      "is_control": false
    }
  ]
}
```


| 表名            | 含义                                     | 是否建议                     |
| ------------- | -------------------------------------- | ------------------------ |
| `requests`    | 原始请求表，记录输入 payload、来源、耗时、用户、IP         | 保留                       |
| `assignments` | 实验固定进组表，记录某个主体固定进入哪个实验组                | 改成这个用途                   |
| `decisions`   | 请求级路由/决策结果表，记录每次请求实际命中了哪个部署、版本、实验组     | 用它替换现在的请求级 `assignments` |
| `variants`    | 实验分组表，control / treatment / challenger | 新增                       |
| `outcomes`    | 结果回流表，通过、转化、逾期、坏账                      | 新增                       |

experiments
  实验主表：定义实验、状态、配置、生效时间

variants
  实验分组表：control / treatment / challenger，每组对应一个 deployment_id 和 weight

enrollments
  固定进组表：同一个 experiment_id + subject_key 固定命中同一个 variant

assignments
  请求分配记录表：每次请求实际命中了哪个部署、哪个实验、哪个分组

outcomes
  结果回流表：通过、转化、逾期、坏账等后验结果





现在的实验 bucket_key 是 customer_id，但当前 /predict 请求模型里已经有 subject_key、subject_type，
并且 A/B 引擎优先使用显式传入的 subject_key，只有没传 subject_key 时才从 payload 里按 bucket_key 提取。


请求决策时，系统首先判断请求是否显式指定 deployment_id。若已指定，则直接校验并返回对应部署。
若未指定，则优先尝试匹配 running 状态的实验，实验内部根据 strategy 执行 manual 或 hash 分配， 并返回实验分组绑定的部署。
若实验未命中，则继续匹配启用状态的路由规则。
若实验和路由均未命中，则进入默认部署兜底逻辑：优先选择当前环境下的活跃主部署；
若不存在主部署，则选择第一个可用的活跃部署作为兜底部署。
同一模型、同一环境，只允许一个 running 实验。

部署解析优先级：

1. 显式指定 deployment_id
2. 实验分流 experiment
   - 实验内部根据 strategy 执行 manual 或 hash
3. 路由规则 routing
4. 默认活跃部署 fallback
   - 优先选择 active champion 部署
   - 如果没有 champion，则选择第一个 active 部署

    
Datamind 当前路由优先级是：

1. 如果请求指定 deployment_id
   → manual

2. 如果有 running 实验，并且 subject 命中实验流量
   → experiment

3. 如果 routing 表有启用路由规则
   → routing

4. 如果以上都没有命中
   → fallback 到 active champion deployment


什么时候会走 routing？

你的路由顺序是：

1. 请求传了 deployment_id
   → manual
   → 不走 experiment，也不走 routing

2. 没传 deployment_id，且命中 running experiment
   → experiment
   → 不走 routing

3. 没传 deployment_id，且没有命中实验
   → routing

4. routing 表没有可用规则
   → fallback 到 active champion deployment


这个命令创建的是 routing 表记录，但用户侧命令叫：

datamind route create

例如你现在要给两个部署配置 routing 阶段 80% / 20%，后面可以这样用：

datamind route create dep_f1ac4e6e3318 `
  --environment development `
  --traffic 0.8 `
  --rollout canary `
  --group champion `
  --operator admin
datamind route create dep_b9f267054202 `
  --environment development `
  --traffic 0.2 `
  --rollout canary `
  --group challenger `
  --operator admin

## 实验或分组更新条件：

| 实验状态        | 分组状态       | 是否允许 update | 允许修改字段                                                            |
| ----------- | ---------- | ----------: | ----------------------------------------------------------------- |
| `draft`     | `active`   |          允许 | `name`、`deployment_id`、`weight`、`control/treatment`、`description` |
| `draft`     | `inactive` |          允许 | `name`、`deployment_id`、`weight`、`control/treatment`、`description` |
| `draft`     | `archived` |         不允许 | 不允许修改                                                             |
| `paused`    | `active`   |        部分允许 | 只允许 `description`                                                 |
| `paused`    | `inactive` |        部分允许 | 只允许 `description`                                                 |
| `paused`    | `archived` |         不允许 | 不允许修改                                                             |
| `running`   | 任意状态       |         不允许 | 不允许修改                                                             |
| `stopped`   | 任意状态       |         不允许 | 不允许修改                                                             |
| `completed` | 任意状态       |         不允许 | 不允许修改                                                             |
| `archived`  | 任意状态       |         不允许 | 不允许修改                                                             |


## 决策来源与路由策略对应关系
| source       | strategy   | 说明                     |
| ------------ | ---------- | ---------------------- |
| `manual`     | `manual`   | 请求显式指定 `deployment_id` |
| `experiment` | `manual`   | 命中 manual 实验分配         |
| `experiment` | `hash`     | 命中 hash 实验分配           |
| `routing`    | `weighted` | 命中 routing 表加权路由       |
| `deployment` | `fallback` | 实验和路由都未命中，使用默认活跃部署兜底   |


## 实验启动校验

- 至少有一个活跃分组
- 必须且只能有一个活跃对照组
- 至少有一个活跃实验组
- hash 策略下活跃分组权重之和必须等于 1

## 报文示例

#### 1. 显式指定部署：`source=manual`，`strategy=manual`

```http
POST /predict
Content-Type: application/json
```

```json
{
    "request": {
        "model_id": "mdl_0efc148c",
        "deployment_id": "dep_18f009682bc5",
        "environment": "development",
        "features": {
            "age": 0.35,
            "income": 0.72,
            "gender": 0.10,
            "province": 0.65,
            "education": 0.80
        }
    }
}
```

说明：请求报文中显式指定 `deployment_id` 时，系统会优先使用该部署进行推理，不再进入实验分流和路由规则匹配流程。

---

#### 2. 命中 manual 实验：`source=experiment`，`strategy=manual`

```http
POST /predict
Content-Type: application/json
```

```json
{
    "request": {
        "model_id": "mdl_0efc148c",
        "environment": "development",
        "subject_key": "customer_10001",
        "subject_type": "customer",
        "features": {
            "age": 0.35,
            "income": 0.72,
            "gender": 0.10,
            "province": 0.65,
            "education": 0.80
        }
    }
}
```

说明：请求报文本身不直接指定 `deployment_id`。系统会根据 `subject_key` 查找 manual 实验中的人工分配记录，命中对应实验分组后，再找到该分组绑定的 `deployment_id`。

---

#### 3. 命中 hash 实验：`source=experiment`，`strategy=hash`

```http
POST /predict
Content-Type: application/json
```

```json
{
    "request": {
        "model_id": "mdl_0efc148c",
        "environment": "development",
        "customer_id": "customer_10002",
        "subject_key": "customer_10002",
        "subject_type": "customer",
        "features": {
            "age": 0.42,
            "income": 0.83,
            "gender": 0.20,
            "province": 0.58,
            "education": 0.91
        }
    }
}
```

说明：请求报文本身不直接指定 `deployment_id`。系统会使用实验配置中的 `bucket_key` 做 hash 分桶。例如创建实验时指定 `--bucket-key customer_id`，则请求报文中需要提供 `customer_id`。系统根据实验 `traffic_ratio` 和实验分组 `weight` 命中对应实验分组，再找到该分组绑定的 `deployment_id`。

---

#### 4. 命中路由规则：`source=routing`，`strategy=weighted`

```http
POST /predict
Content-Type: application/json
```

```json
{
    "request": {
        "model_id": "mdl_0efc148c",
        "environment": "development",
        "subject_key": "customer_10003",
        "subject_type": "customer",
        "features": {
            "age": 0.28,
            "income": 0.49,
            "gender": 0.30,
            "province": 0.76,
            "education": 0.63
        }
    }
}
```

说明：当请求未显式指定 `deployment_id`，且没有命中 running 实验时，系统会继续匹配启用状态的路由规则。若 `features` 满足 `rules` 条件，则按路由表中的 `traffic_ratio` 做加权分流。

---

#### 5. 默认活跃部署兜底：`source=deployment`，`strategy=fallback`

```http
POST /predict
Content-Type: application/json
```

```json
{
    "request": {
        "model_id": "mdl_0efc148c",
        "environment": "development",
        "subject_key": "customer_10004",
        "subject_type": "customer",
        "features": {
            "age": 0.51,
            "income": 0.68,
            "gender": 0.40,
            "province": 0.33,
            "education": 0.74
        }
    }
}
```

当请求未显式指定 deployment_id，且未命中 running 实验和启用状态路由规则时，系统会优先查找当前环境下的活跃主部署；
如果不存在活跃主部署，则使用当前环境下第一个可用的活跃部署作为兜底部署进行推理。

python -c "import secrets; print(secrets.token_urlsafe(64))"


启动实验需要：
- 恰好一个启用的对照组
- 至少一个启用的实验分组
- 启用分组的权重合计为 1
- 每个分组绑定不同且可用的部署
