# Datamind 模型服务模块

基于BentoML的模型服务部署，提供高性能的模型推理服务。

## 目录结构
```
serving/
├── init.py # 模块初始化
├── base.py # 基础服务类
├── scoring_service.py # 评分卡服务
├── fraud_service.py # 反欺诈服务
├── bentofile.yaml # BentoML配置文件
├── docker/ # Docker相关文件
│ ├── Dockerfile
│ └── entrypoint.sh
├── requirements.txt # 服务依赖
└── README.md # 本文档
```

## 服务类型

### 1. 评分卡服务 (Scoring Service)
- **端口**: 3000
- **服务文件**: `scoring_service.py`
- **功能**: 信用评分、风险评级
- **输出**: 总分、特征分

### 2. 反欺诈服务 (Fraud Service)
- **端口**: 3000
- **服务文件**: `fraud_service.py`
- **功能**: 欺诈检测、风险分析
- **输出**: 欺诈概率、风险等级、风险因素


## 服务类型

### 1. 评分卡服务 (Scoring Service)
- 端口: 3001
- 端点: `/predict`, `/batch_predict`, `/health`

### 2. 反欺诈服务 (Fraud Service)
- 端口: 3002
- 端点: `/predict`, `/batch_predict`, `/explain`, `/health`

## 快速开始

### 本地运行

```bash
# 评分卡服务
cd serving
bentoml serve scoring_service:service --reload

# 反欺诈服务
bentoml serve fraud_service:service --reload
```

## 快速开始

### 本地开发

```bash
# 安装依赖
cd serving
pip install -r requirements.txt

# 运行评分卡服务
bentoml serve scoring_service:service --reload

# 运行反欺诈服务
bentoml serve fraud_service:service --reload
```

## 使用Docker
```bash
# 构建镜像
cd serving
docker build -f docker/Dockerfile -t datamind-serving .

# 运行评分卡服务
docker run -p 3000:3000 \
  -e SERVICE_TYPE=scoring \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e REDIS_URL=redis://host:6379 \
  -v /path/to/models:/app/models_storage \
  datamind-serving

# 运行反欺诈服务
docker run -p 3000:3000 \
  -e SERVICE_TYPE=fraud \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e REDIS_URL=redis://host:6379 \
  -v /path/to/models:/app/models_storage \
  datamind-serving
```

## 使用Docker Compose
```text
version: '3.8'
services:
  scoring:
    build:
      context: ./serving
      dockerfile: docker/Dockerfile
    ports:
      - "3001:3000"
    environment:
      SERVICE_TYPE: scoring
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/datamind
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./models_storage:/app/models_storage
    depends_on:
      - postgres
      - redis

  fraud:
    build:
      context: ./serving
      dockerfile: docker/Dockerfile
    ports:
      - "3002:3000"
    environment:
      SERVICE_TYPE: fraud
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/datamind
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./models_storage:/app/models_storage
    depends_on:
      - postgres
      - redis
```

## API使用示例

### 评分卡预测
```python
import requests
import json

# 请求数据
data = {
    "model_id": "MDL_20240315_ABCD1234",
    "application_id": "APP202403150001",
    "features": {
        "age": 35,
        "income": 50000,
        "credit_history": 720,
        "loan_amount": 100000,
        "employment_years": 5
    }
}

# 发送请求
response = requests.post(
    "http://localhost:3000/predict",
    json=data,
    headers={"Content-Type": "application/json"}
)

# 处理响应
result = response.json()
if result["success"]:
    print(f"总分: {result['data']['total_score']}")
    print(f"特征分: {result['data']['feature_scores']}")
else:
    print(f"错误: {result['error']}")
```

### 反欺诈预测
```python
import requests

data = {
    "model_id": "MDL_20240315_EFGH5678",
    "application_id": "APP202403150001",
    "features": {
        "ip_address": "192.168.1.1",
        "device_id": "device_123456",
        "user_agent": "Mozilla/5.0...",
        "amount": 10000,
        "transaction_hour": 14
    }
}

response = requests.post(
    "http://localhost:3000/predict",
    json=data
)

result = response.json()
if result["success"]:
    print(f"欺诈概率: {result['data']['fraud_probability']}")
    print(f"风险等级: {result['data']['risk_level']}")
    print(f"风险因素: {result['data']['risk_factors']}")
```

### 批量预测
```python
import requests

batch_data = [
    {
        "model_id": "MDL_20240315_ABCD1234",
        "application_id": "APP001",
        "features": {"age": 35, "income": 50000}
    },
    {
        "model_id": "MDL_20240315_ABCD1234",
        "application_id": "APP002",
        "features": {"age": 42, "income": 80000}
    }
]

response = requests.post(
    "http://localhost:3000/batch_predict",
    json=batch_data
)

results = response.json()
for i, result in enumerate(results):
    if result["success"]:
        print(f"请求 {i+1}: 分数 {result['data']['total_score']}")
```

## 预测解释（仅反欺诈）
```python
response = requests.post(
    "http://localhost:3002/explain",
    json=data
)

result = response.json()
if result["success"]:
    for contrib in result["explanation"]["contributions"]:
        print(f"{contrib['feature']}: 重要性={contrib['importance']}, 影响={contrib['impact']}")
```
## 监控指标

服务提供Prometheus监控指标：

- request_total: 总请求数

- request_duration_seconds: 请求耗时

- model_inference_duration_seconds: 模型推理耗时

- model_loaded_count: 已加载模型数量

- error_total: 错误总数

访问 http://localhost:3000/metrics 查看指标。

## 健康检查

- 端点: GET /health

- 频率: 每30秒

- 超时: 3秒

```json
{
    "status": "healthy",
    "service": "scoring-service",
    "timestamp": "2024-03-15T10:30:00",
    "models_loaded": 5,
    "request_id": "abc123"
}
```

## 配置说明
### 环境变量
变量名	说明	默认值	必填
SERVICE_TYPE	服务类型 (scoring/fraud)	scoring	是
ENVIRONMENT	运行环境	production	否
DATABASE_URL	数据库连接	-	是
REDIS_URL	Redis连接	-	是
LOG_LEVEL	日志级别	INFO	否
MODEL_CACHE_SIZE	模型缓存大小	10	否
MODEL_INFERENCE_TIMEOUT	推理超时(秒)	30	否

### 日志配置
日志格式为JSON，包含：

    @timestamp: 时间戳

    level: 日志级别

    service: 服务名称

    request_id: 请求ID

    message: 日志消息

### 并发配置
```yaml
traffic:
  timeout: 30          # 超时时间
  concurrency: 10       # 并发数
  max_batch_size: 100   # 最大批处理大小
```

### 资源限制
```yaml
resources:
  cpu: 2000m    # 2核
  memory: 4Gi   # 4GB内存
```