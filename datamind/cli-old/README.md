# Datamind 命令行工具

Datamind 模型部署平台的命令行接口（CLI），提供完整的模型管理、审计日志、配置管理和健康检查功能。

## 安装

### 通过 pip 安装

```bash
# 从源码安装
cd datamind
pip install -e .

# 或者直接安装
pip install datamind-cli
```

## 通过 Docker 使用
```bash
docker run --rm datamind-cli --help
```

## 命令补全

### Bash
```bash
source cli/completions/bash.sh
# 或添加到 ~/.bashrc
echo "source $(pwd)/cli/completions/bash.sh" >> ~/.bashrc
```

### Zsh
```bash
source cli/completions/zsh.sh
# 或添加到 ~/.zshrc
echo "source $(pwd)/cli/completions/zsh.sh" >> ~/.zshrc
```

### Fish
```bash
source cli/completions/fish.sh
# 或复制到补全目录
cp cli/completions/fish.sh ~/.config/fish/completions/datamind.fish
```

## 快速开始
```bash
# 查看帮助
datamind --help

# 查看版本
datamind version show

# 列出所有模型
datamind model list

# 查看模型详情
datamind model show MDL_20240315_ABCD1234

# 检查服务健康状态
datamind health check

# 查看最近审计日志
datamind audit list --days 7
```

## 全局选项
选项	说明
--config, -c	指定配置文件路径
--env, -e	指定环境 (development/testing/production)
--debug	启用调试模式
--help	显示帮助信息
--version	显示版本信息

## 命令详解

### 1. 模型管理命令 (model)
#### 列出模型
```bash
# 列出所有模型
datamind model list

# 按任务类型筛选
datamind model list --task-type scoring
datamind model list --task-type fraud_detection

# 按状态筛选
datamind model list --status active
datamind model list --status inactive

# 按框架筛选
datamind model list --framework sklearn

# 只显示生产模型
datamind model list --production

# JSON格式输出
datamind model list --format json
```

#### 查看模型详情
```bash
datamind model show MDL_20240315_ABCD1234
datamind model show MDL_20240315_ABCD1234 --format json
```

#### 注册新模型
```bash
# 基本注册
datamind model register \
  --name credit_score_v2 \
  --version 1.0.0 \
  --task-type scoring \
  --model-type xgboost \
  --framework xgboost \
  --features '["age", "income", "credit_history"]' \
  --output '{"score": "float"}' \
  --file model.json

# 使用JSON文件定义特征
datamind model register \
  --name fraud_detector_v3 \
  --version 1.0.0 \
  --task-type fraud_detection \
  --model-type lightgbm \
  --framework lightgbm \
  --features features.json \
  --output schema.json \
  --file model.txt \
  --description "反欺诈模型v3"

# 注册评分卡模型并配置参数
datamind model register \
  --name credit_score_v2 \
  --version 1.0.0 \
  --task-type scoring \
  --model-type xgboost \
  --framework xgboost \
  --features features.json \
  --output output.json \
  --file model.json \
  --scorecard '{
    "base_score": 600,
    "pdo": 50,
    "min_score": 320,
    "max_score": 960,
    "direction": "lower_better"
  }'

# 注册反欺诈模型并配置风险等级
datamind model register \
  --name fraud_detector_v3 \
  --version 1.0.0 \
  --task-type fraud_detection \
  --model-type lightgbm \
  --framework lightgbm \
  --features features.json \
  --output output.json \
  --file model.txt \
  --risk-config '{
    "levels": {
      "low": {"max": 0.3},
      "medium": {"min": 0.3, "max": 0.6},
      "high": {"min": 0.6, "max": 0.8},
      "very_high": {"min": 0.8}
    }
  }'
```

#### 激活/停用模型
```bash
# 激活模型
datamind model activate MDL_20240315_ABCD1234 --reason "准备上线"

# 停用模型
datamind model deactivate MDL_20240315_ABCD1234 --reason "模型废弃"

# 提升为生产模型
datamind model promote MDL_20240315_ABCD1234 --reason "通过测试"
```

#### 模型内存管理
```bash
# 加载模型到内存
datamind model load MDL_20240315_ABCD1234

# 从内存卸载模型
datamind model unload MDL_20240315_ABCD1234
```

#### 查看模型历史
```bash
datamind model history MDL_20240315_ABCD1234
```

#### 管理模型参数
```bash
# 查看模型参数
datamind model params MDL_20240315_ABCD1234

# 更新评分卡配置
datamind model update-params MDL_20240315_ABCD1234 \
  --scorecard '{"base_score": 650, "pdo": 60}' \
  --reason "调整评分卡参数"

# 更新风险配置
datamind model update-params MDL_20240315_ABCD1234 \
  --risk-config '{"levels": {"low": {"max": 0.2}, "high": {"min": 0.8}}}' \
  --reason "收紧风险阈值"
```

### 2. 审计日志命令 (audit)
```bash
# 查看最近审计日志
datamind audit list --days 7

# 按操作类型筛选
datamind audit list --action MODEL_REGISTER

# 按操作人筛选
datamind audit list --user admin

# 查看日志详情
datamind audit show AUD_20240315_ABCD1234

# 导出审计日志
datamind audit export --days 30 --output audit_export.json
```

### 3. 日志管理命令 (log)

#### 实时查看日志
```bash
# 跟踪访问日志
datamind log tail access -f

# 查看错误日志最后100行
datamind log tail error -n 100

# 过滤关键词
datamind log tail access -f -g "ERROR"
```

#### 搜索日志
```bash
# 搜索关键词
datamind log search access -k "ERROR" --since "7d"

# 按时间范围搜索
datamind log search audit -k "MODEL_REGISTER" \
  --since "2024-03-01" --until "2024-03-15"

# JSON格式输出
datamind log search performance -k "duration" --format json
```

#### 导出日志
```bash
# 导出访问日志
datamind log export access -o logs/access_export.log --since "30d"

# 导出所有日志并压缩
datamind log export all -o logs/all_logs.gz --compress

# 按时间范围导出
datamind log export error -o logs/error_export.log \
  --since "2024-03-01" --until "2024-03-31"
```

#### 日志统计
```bash
# 统计最近30天日志
datamind log stats access --days 30

# 统计错误日志
datamind log stats error --days 7

# 统计所有日志
datamind log stats all --days 90
```

#### 日志维护
```bash
# 手动轮转日志
datamind log rotate access --keep 20

# 轮转所有日志
datamind log rotate all --keep 90

# 试运行清理（只显示要删除的文件）
datamind log clean --days 90 --dry-run

# 实际清理
datamind log clean --days 180
```

#### 查看日志配置
```bash
datamind log config
```

### 4. 配置管理命令 (config)
```bash
# 查看当前配置
datamind config show
datamind config show --format json
datamind config show --format yaml

# 获取单个配置项
datamind config get api.host
datamind config get database.pool_size

# 验证配置
datamind config validate

# 查看环境变量
datamind config env

# 重载配置
datamind config reload
```

### 5. 健康检查命令 (health)
```bash
# 检查API服务
datamind health check
datamind health check --host api.example.com --port 8080

# 检查数据库
datamind health db
datamind health db --host db.example.com --port 5432

# 检查Redis
datamind health redis
datamind health redis --host redis.example.com --port 6379

# 检查所有服务
datamind health all
```

### 6. 版本命令 (version)
```bash
# 显示版本信息
datamind version show

# 检查更新
datamind version check
```

## 配置文件
CLI工具支持配置文件，默认查找顺序：
```text
./.datamind-cli.json (当前目录)

~/.config/datamind/cli.json (用户配置)

~/.datamind-cli.json (用户目录)
```

## 配置示例
```json
{
  "api": {
    "host": "localhost",
    "port": 8000,
    "timeout": 30
  },
  "format": "table",
  "color": true,
  "history_size": 100
}
```

## 环境变量
变量	说明
DATAMIND_API_HOST	API主机地址
DATAMIND_API_PORT	API端口
DATAMIND_API_TIMEOUT	请求超时时间(秒)
DATAMIND_LOG_LEVEL	日志级别

## 返回值

命令执行后会返回相应的退出码：
- 0: 成功
- 1: 一般错误
- 2: 参数错误
- 3: 未找到资源

## 常见问题

### 1. 连接失败
```bash
# 检查服务是否运行
datamind health check

# 检查配置
datamind config get api.host
datamind config get api.port
```
### 2. 权限不足
```bash

# 使用管理员身份运行
sudo datamind model list

# 检查API密钥配置
export DATAMIND_API_KEY=your-api-key
```

### 3. 输出格式问题
```bash
# 使用JSON格式便于解析
datamind model list --format json | jq '.[] | .model_name'

# 使用表格格式便于阅读
datamind model list --format table
```

### 4. 调试模式
```bash
# 启用调试模式查看详细错误
datamind --debug model show unknown-model
```

## 最佳实践

### 脚本中使用
```bash
#!/bin/bash
# 获取所有生产模型ID
model_ids=$(datamind model list --production --format json | jq -r '.[].model_id')

for model_id in $model_ids; do
  echo "加载模型: $model_id"
  datamind model load "$model_id"
done
```

### 定时任务
```bash
# 每天凌晨3点清理旧日志
0 3 * * * /usr/local/bin/datamind log clean --days 90

# 每周一导出审计日志
0 0 * * 1 /usr/local/bin/datamind audit export --days 7 -o /backup/audit_$(date +\%Y\%m\%d).json
```

### 别名设置
```bash
# 添加到 ~/.bashrc
alias dml='datamind model list'
alias dms='datamind model show'
alias dhc='datamind health check'
alias dla='datamind log tail access -f'
alias dle='datamind log tail error -f'
```