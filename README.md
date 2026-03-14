#
我想设计一个银行贷款模型部署平台Datamind, 用于部署模型开发人员用Python跑出来的评分卡模型，反欺诈等模型。
不用考虑批量预测，零售信贷贷款都是单笔处理的。
模型部署工具考虑用bentoml实现，支持模型注册、注销，支持模型文件热更换，支持模型框架：sklearn|xgboost|lightgbm|torch|tensorflow|onnx|catboost。
支持模型类型：模型类型：decision_tree|random_forest|xgboost|lightgbm|logistic_regression。
能支持AB test.能跑评分卡模型任务也能跑反欺诈模型任务，并提供API服务。对于评分卡模型，应该返回模型总评分和模型的特征分.不要直接输出决策结果。决策交给下游的内评系统
只跑模型，不管模型规则。
模型ID应该是Datamind后台维护的识别模型的唯一主键。不应该作为模型注册参数。
模型元数据不保存在数据库吗？金融场景要能审计，要有完善的日志系统。
```text
datamind/
├── api/                            # API接口层
│   ├── __init__.py
│   ├── register_api.py             # 模型注册API
│   ├── model_api.py                # 模型查询API
│   ├── management_api.py             
│   ├── scoring_api.py             
│   └── fraud_detection_api.py  
│
├── bento_services/                  # BentoML服务（独立部署）
│   ├── __init__.py
│   ├── scoring_service.py           # 评分卡服务
│   │   ├── service.py               # BentoML服务定义
│   │   ├── bentofile.yaml           # BentoML配置文件
│   │   └── requirements.txt         # 服务依赖
│   │
│   └── fraud_service.py             # 反欺诈服务
│       ├── service.py
│       ├── bentofile.yaml
│       └── requirements.txt
│
├── cli/                             # 命令行工具（新增）
│   ├── __init__.py
│   ├── main.py                      # CLI入口
│   ├── commands/                    # 命令模块
│   │   ├── __init__.py
│   │   ├── model.py                  # 模型管理命令
│   │   ├── audit.py                   # 审计日志命令
│   │   ├── log.py                     # 日志管理命令
│   │   ├── config.py                  # 配置管理命令
│   │   ├── health.py                  # 健康检查命令
│   │   └── version.py                 # 版本管理命令
│   ├── utils/                        # CLI工具函数
│   │   ├── __init__.py
│   │   ├── printer.py                 # 格式化输出
│   │   ├── progress.py                # 进度条显示
│   │   └── config.py                  # CLI配置管理
│   ├── completions/                  # 命令行补全
│   │   ├── bash.sh                    # Bash补全
│   │   ├── zsh.sh                     # Zsh补全
│   │   └── fish.sh                    # Fish补全
│   ├── templates/                    # 命令模板
│   │   ├── model_registration.json    # 模型注册模板
│   │   └── audit_query.json           # 审计查询模板
│   └── README.md                      # CLI使用说明
│
├── core/                            # 核心业务逻辑
│   ├── __init__.py
│   ├── models.py                    # SQLAlchemy数据库模型
│   ├── database.py                   # 数据库连接管理
│   ├── log_manager.py                # 日志管理器
│   ├── model_registry.py             # 模型注册核心逻辑
│   ├── model_loader.py               # 模型热加载器
│   ├── inference.py                  # 统一推理引擎
│   ├── ab_test.py                    # AB测试管理器
│   └── exceptions.py                 # 自定义异常
│
├── config/                           # 配置文件
│   ├── __init__.py
│   ├── settings.py                   # 应用配置
│   ├── logging_config.py              # 日志配置模型
│   ├── development.yaml               # 开发环境配置
│   ├── testing.yaml                   # 测试环境配置
│   ├── staging.yaml                   # 预发布环境配置
│   └── production.yaml                # 生产环境配置
│
├── migrations/                       # 数据库迁移
│   ├── __init__.py
│   ├── env.py                         # Alembic环境配置
│   ├── alembic.ini                    # Alembic配置文件
│   └── versions/                      # 迁移版本
│       ├── 20240115_initial.py        # 初始迁移
│       └── 20240120_add_indexes.py    # 添加索引
│
├── scripts/                          # 脚本工具
│   ├── __init__.py
│   ├── backup_db.py                   # 数据库备份
│   ├── migrate_data.py                # 数据迁移
│   ├── init_db.py                     # 数据库初始化
│   └── cron_jobs/                     # 定时任务脚本
│       ├── cleanup_logs.py
│       ├── archive_models.py
│       └── send_daily_report.py
│
├── storage/                          # 文件存储
│   ├── __init__.py
│   └── file_store.py                  # 模型文件存储管理
│
├── utils/                            # 工具函数
│   ├── __init__.py
│   ├── time_converter.py              # 时间格式转换
│   ├── log_converter.py               # 日志格式转换
│   ├── validators.py                  # 数据验证器
│   └── helpers.py                     # 通用辅助函数
│
├── tests/                            # 测试目录
│   ├── __init__.py
│
├── logs/                             # 日志目录（运行时创建）
│   ├── Datamind.log
│   ├── Datamind.error.log
│   ├── access.log
│   ├── audit.log
│   └── performance.log
│
── models/                       # 模型文件存储
│       ├── scoring/                   # 评分卡模型
│       │   └── mod_202401151030_abc12345/
│       │       ├── metadata.json
│       │       ├── model_1.0.0.pkl
│       │       ├── latest -> model_1.0.0.pkl
│       │       └── versions/
│       │           └── 1.0.0.json
│       └── fraud_detection/           # 反欺诈模型
│           └── mod_202401151231_def45678/
│               ├── metadata.json
│               ├── model_1.0.0.pkl
│               ├── latest -> model_1.0.0.pkl
│               └── versions/
│                   └── 1.0.0.json
│
├── docker/                           # Docker相关
│   ├── Dockerfile                     # 主服务Dockerfile
│   ├── Dockerfile.bento               # BentoML服务Dockerfile
│   ├── docker-compose.yml             # 本地开发用
│   ├── docker-compose.prod.yml        # 生产环境用
│   └── entrypoint.sh                  # 容器入口脚本
│
│
├── docs/                             # 文档
│   ├── api.md                         # API文档
│   ├── deployment.md                  # 部署文档
│   ├── configuration.md               # 配置说明
│   ├── logging.md                     # 日志系统说明
│   ├── ab_testing.md                  # AB测试说明
│   └── cli.md                         # CLI使用说明
│
├── .env.example                       # 环境变量示例
├── .gitignore                         # Git忽略文件
├── requirements.txt                   # Python依赖
├── requirements-dev.txt               # 开发依赖
├── Makefile                           # 常用命令
├── pyproject.toml                     # 项目配置
├── setup.py                           # 安装脚本（安装后可使用datamind命令）
└── README.md                          # 项目说明
```


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


最新的项目结构
```text
datamind/
├── README.md
├── requirements.txt
├── .env.example
├── .env.dev
├── .env.test
├── .env.prod
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

# 测试
python -m unittest tests/test_logging_config.py
python -m unittest tests/test_logging_config.py -v

# 测试确保project.toml:
[tool.pytest.ini_options]
pythonpath = ["."]


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
# 注册评分卡模型并配置评分卡参数
model_id = model_registry.register_model(
    model_name="credit_score_v2",
    model_version="1.0.0",
    task_type="scoring",
    model_type="xgboost",
    framework="xgboost",
    input_features=["age", "income", "credit_history"],
    output_schema={"score": "float"},
    created_by="admin",
    model_file=open("model.json", "rb"),
    scorecard_params={
        "base_score": 600,
        "pdo": 50,
        "min_score": 320,
        "max_score": 960,
        "direction": "lower_better"
    }
)

# 注册反欺诈模型并配置风险等级
model_id = model_registry.register_model(
    model_name="fraud_detector_v3",
    model_version="1.0.0",
    task_type="fraud_detection",
    model_type="lightgbm",
    framework="lightgbm",
    input_features=["ip_address", "device_id", "amount"],
    output_schema={"fraud_probability": "float"},
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

# 获取模型参数
params = model_registry.get_model_params(model_id)
print(params['scorecard'])  # 获取评分卡配置

# 更新模型配置
model_registry.update_model_params(
    model_id=model_id,
    operator="admin",
    scorecard_params={
        "base_score": 650,
        "pdo": 60,
        "direction": "higher_better"
    },
    reason="根据业务需求调整评分卡参数"
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

## 启动依赖服务

```bash
# 使用 Docker Compose 启动 PostgreSQL 和 Redis
docker-compose up -d postgres redis

# 或手动启动 PostgreSQL 和 Redis
```

## 初始化数据库

```bash
# 创建数据库表
python scripts/init_db.py

# 执行数据库迁移
alembic upgrade head
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
      context: ./serving
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
      context: ./serving
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