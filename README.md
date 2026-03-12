```text
datamind/
├── api/                            # API接口层
│   ├── __init__.py
│   ├── register_api.py             # 模型注册API
│   ├── model_api.py                 # 模型查询API
│   ├── audit_api.py                 # 审计日志API
│   ├── inference_api.py             # 推理日志API
│   └── version_api.py               # 版本管理API
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
│   ├── audit_logger.py               # 审计日志系统
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
├── scripts/                          # 脚本工具（保留，用于自动化任务）
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
│   ├── conftest.py                    # pytest配置
│   ├── unit/                          # 单元测试
│   │   ├── test_models.py
│   │   ├── test_audit_logger.py
│   │   └── test_model_loader.py
│   ├── integration/                   # 集成测试
│   │   ├── test_api.py
│   │   └── test_database.py
│   └── fixtures/                      # 测试数据
│       ├── sample_model.pkl
│       └── test_config.yaml
│
├── logs/                             # 日志目录（运行时创建）
│   ├── Datamind.log
│   ├── Datamind.error.log
│   ├── access.log
│   ├── audit.log
│   └── performance.log
│
├── data/                             # 数据目录
│   └── models/                       # 模型文件存储
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
├── kubernetes/                       # Kubernetes部署
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml                       # 自动扩缩容
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