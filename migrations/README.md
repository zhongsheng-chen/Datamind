# Datamind 数据库迁移

基于 Alembic 的数据库迁移管理，提供版本控制、自动迁移、回滚等功能。

## 特性

* **版本控制** - 每个迁移都有唯一版本号
* **自动生成** - 自动检测模型变化生成迁移脚本
* **双向迁移** - 支持升级和降级
* **多环境支持** - 开发、测试、生产环境独立管理
* **数据完整性** - 确保迁移过程数据安全
* **枚举类型** - 支持 PostgreSQL 枚举类型的创建和管理
* **并发索引** - 支持 `CREATE INDEX CONCURRENTLY` 避免锁表
* **扩展管理** - 自动安装和管理 PostgreSQL 扩展（如 `pg_trgm`）
* **幂等操作** - 所有操作都支持 `IF NOT EXISTS` / `IF EXISTS`，可安全重复执行
* **审计跟踪** - 记录所有迁移操作

## 目录结构
```text
Datamind/
├── alembic.ini             # Alembic 配置文件（项目根目录）
├── migrations/             # 迁移目录
│   ├── **init**.py         # 模块初始化
│   ├── env.py              # Alembic 环境配置
│   ├── script.py.mako      # 迁移脚本模板
│   ├── README.md           # 迁移说明文档
│   └── versions/           # 迁移版本目录
│       ├── **init**.py
│       ├── 20240315_initial.py        # 初始迁移（创建所有基础表）
│       ├── 20240316_add_status.py     # 添加状态字段
│       └── 20240317_add_indexes.py    # 添加性能优化索引
```

## 迁移文件说明

### 1. 初始迁移 (20240315_initial.py)

创建所有 PostgreSQL 枚举类型（使用 DO $$ + IF NOT EXISTS）

创建 9 张核心表：

* model_metadata - 模型元数据
* model_version_history - 模型版本历史
* model_deployments - 模型部署
* api_call_logs - API调用日志
* model_performance_metrics - 模型性能监控
* audit_logs - 审计日志
* ab_test_configs - A/B测试配置
* ab_test_assignments - A/B测试分配
* system_configs - 系统配置

创建所有基础索引

JSONB 字段设置默认值（'[]'::jsonb 或 '{}'::jsonb）

Boolean 字段使用 sa.text('false') 确保正确性

### 2. 添加状态字段 (20240316_add_status.py)

* 为 model_version_history 添加 status_snapshot 字段
* 为 model_deployments 添加 deployment_status 字段
* 创建相关索引并添加注释

### 3. 添加性能优化索引 (20240317_add_indexes.py)

* 安装 pg_trgm 扩展（支持 trigram 索引）
* 创建 GIN 索引用于 JSONB 字段查询
* 创建复合索引优化常用查询
* 使用 autocommit_block() 支持 CREATE INDEX CONCURRENTLY
* 所有索引都添加了详细的注释说明

## 快速开始

### 1. 配置数据库连接

编辑项目根目录的 alembic.ini 文件，修改数据库连接字符串：

sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/datamind

或者在 env.py 中从环境变量读取（已配置）：

```python
# env.py 中会自动从 settings 获取数据库 URL
db_url = settings.database.url
if db_url.startswith("postgresql+asyncpg"):
    db_url = db_url.replace("postgresql+asyncpg", "postgresql")
config.set_main_option("sqlalchemy.url", db_url)
```

### 2. 执行完整迁移

```bash
# 升级到最新版本
python -m alembic upgrade head

# 或者分步执行
python -m alembic upgrade 20240315_initial
python -m alembic upgrade 20240316_add_status
python -m alembic upgrade 20240317_add_indexes
```

### 3. 创建新迁移

```bash
# 自动生成迁移（基于模型变化）
alembic revision --autogenerate -m "添加新功能"

# 手动创建空迁移
alembic revision -m "手动迁移描述"
```

### 4. 查看迁移状态

```bash
# 查看当前版本
python -m alembic current

# 查看历史版本
python -m alembic history

# 查看迁移生成的 SQL（不执行）
python -m alembic upgrade head --sql
```

### 5. 回滚迁移

```bash
# 回滚一个版本
python -m alembic downgrade -1

# 回滚到指定版本
python -m alembic downgrade 20240316_add_status

# 回滚到基础版本
python -m alembic downgrade base
```

## 最佳实践

### 1. 枚举类型处理

```python
# 安全创建枚举（避免重复）
op.execute("""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'my_enum') THEN
        CREATE TYPE my_enum AS ENUM ('value1', 'value2');
    END IF;
END$$;
""")

# 在表中使用枚举（禁止自动创建）
sa.Column('my_column', PgEnum('value1', 'value2', name='my_enum', create_type=False))
```

### 2. 并发索引创建

```python
# 需要在事务外执行的索引
with op.get_context().autocommit_block():
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name
        ON table_name USING gin (jsonb_column)
    """)
    op.execute("COMMENT ON INDEX idx_name IS '索引说明'")
```

### 3. JSONB 字段默认值

```python
sa.Column(
    'jsonb_column',
    postgresql.JSONB(),
    nullable=False,
    server_default=sa.text("'{}'::jsonb"),
    comment='说明'
)
```

### 4. Boolean 字段默认值

```python
sa.Column(
    'bool_column',
    sa.Boolean(),
    nullable=False,
    server_default=sa.text('false'),
    comment='说明'
)
```

### 5. 安全降级

```python
# 删除枚举类型时使用 CASCADE
op.execute('DROP TYPE IF EXISTS public.my_enum CASCADE')
```

## 注意事项

* 迁移顺序：严格按照版本号顺序执行
* 事务处理：CREATE INDEX CONCURRENTLY 必须在事务外执行，使用 autocommit_block()
* 幂等性：所有操作都应支持重复执行（使用 IF NOT EXISTS / IF EXISTS）
* 枚举删除：删除枚举类型时必须使用 CASCADE，否则可能因依赖而失败
* 扩展安装：使用 pg_trgm 等扩展的索引，需要先安装扩展

## 故障排查

### 常见错误及解决方案

| 错误                                                              | 原因         | 解决方案                                         |
| --------------------------------------------------------------- | ---------- | -------------------------------------------- |
| type "xxx" already exists                                       | 枚举类型重复创建   | 使用 DO $$ + IF NOT EXISTS                     |
| CREATE INDEX CONCURRENTLY cannot run inside a transaction block | 并发索引在事务内执行 | 使用 with op.get_context().autocommit_block(): |
| column "xxx" of relation "yyy" already exists                   | 重复添加字段     | 检查迁移历史，避免重复操作                                |
| relation "alembic_version" does not exist                       | 数据库未初始化    | 执行 alembic upgrade head                      |
