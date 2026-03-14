# Datamind API 组件

提供完整的RESTful API接口，支持模型管理、评分卡预测、反欺诈预测、A/B测试和管理功能。

## 特性

- **RESTful设计** - 符合REST架构风格的API设计
- **多种认证** - 支持JWT、API Key、Basic Auth
- **自动文档** - 集成Swagger UI和ReDoc
- **请求验证** - Pydantic模型自动验证
- **错误处理** - 统一的错误响应格式
- **速率限制** - 防止滥用和DDoS攻击
- **CORS支持** - 跨域资源共享
- **审计日志** - 所有操作记录审计日志
- **性能监控** - 请求耗时、并发数等指标

## 目录结构
```text
├── init.py # 模块初始化
├── dependencies.py # API依赖（认证、用户等）
├── middlewares/ # 中间件
│       ├── init.py
│       ├── auth.py # 认证中间件
│       ├── cors.py # CORS中间件
│       ├── logging_middleware.py # 日志中间件
│       ├── rate_limit.py # 限流中间件
│       ├── security.py # 安全中间件
│       └── performance.py # 性能监控中间件
└── routes/ # 路由模块
├── init.py
├── model_api.py # 模型管理API
├── scoring_api.py # 评分卡API
├── fraud_api.py # 反欺诈API
└── management_api.py # 管理API
```


## 快速开始

### 1. 启动API服务

```bash
# 使用uvicorn启动
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 使用gunicorn（生产环境）
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 2. 访问API文档

- Swagger UI: http://localhost:8000/api/docs

- ReDoc: http://localhost:8000/api/redoc

- OpenAPI JSON: http://localhost:8000/openapi.json

### 3. 认证方式

#### JWT Token
```bash

# 获取token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# 使用token访问
curl http://localhost:8000/api/v1/models \
  -H "Authorization: Bearer <your_token>"
```

#### API Key

```bash

curl http://localhost:8000/api/v1/models \
  -H "X-API-Key: your-api-key"
```


## API端点

### 1. 模型管理API (/api/v1/models)

#### 列出所有模型

```bash
GET /api/v1/models

# 带筛选参数
GET /api/v1/models?task_type=scoring&status=active&framework=sklearn
```

#### 响应示例

```json
{
  "total": 10,
  "models": [
    {
      "model_id": "MDL_20240315_ABCD1234",
      "model_name": "credit_score_v2",
      "model_version": "1.0.0",
      "task_type": "scoring",
      "model_type": "xgboost",
      "framework": "xgboost",
      "status": "active",
      "is_production": true,
      "is_loaded": true,
      "created_by": "admin",
      "created_at": "2024-03-15T10:30:00"
    }
  ]
}
```

#### 获取模型详情

```bash
GET /api/v1/models/{model_id}
```

#### 响应示例

```json
{
  "model_id": "MDL_20240315_ABCD1234",
  "model_name": "credit_score_v2",
  "model_version": "1.0.0",
  "task_type": "scoring",
  "model_type": "xgboost",
  "framework": "xgboost",
  "file_path": "/app/models_storage/MDL_.../model_1.0.0.json",
  "file_size": 1048576,
  "input_features": ["age", "income", "credit_history"],
  "output_schema": {"score": "float"},
  "status": "active",
  "is_production": true,
  "is_loaded": true,
  "created_by": "admin",
  "created_at": "2024-03-15T10:30:00",
  "description": "信用评分模型v2",
  "tags": {"department": "risk", "project": "credit_card"}
}
```

#### 注册新模型

```bash
POST /api/v1/models/register
Content-Type: multipart/form-data

# 表单字段
model_name: credit_score_v2
model_version: 1.0.0
task_type: scoring
model_type: xgboost
framework: xgboost
input_features: ["age", "income", "credit_history"]
output_schema: {"score": "float"}
description: 信用评分模型v2
model_file: @model.json
```

#### 响应示例

```json
{
  "success": true,
  "model_id": "MDL_20240315_ABCD1234",
  "message": "模型 credit_score_v2 v1.0.0 注册成功",
  "request_id": "req_abc123"
}
```

#### 激活模型

```bash
POST /api/v1/models/{model_id}/activate
```

#### 停用模型

```bash
POST /api/v1/models/{model_id}/deactivate
```

#### 设为生产模型

```bash
POST /api/v1/models/{model_id}/promote
```

#### 加载模型到内存

```bash
POST /api/v1/models/{model_id}/load
```

#### 从内存卸载模型

```bash
POST /api/v1/models/{model_id}/unload
```

#### 获取模型历史

```bash
GET /api/v1/models/{model_id}/history
```

#### 响应示例

```json
{
  "model_id": "MDL_20240315_ABCD1234",
  "history": [
    {
      "operation": "CREATE",
      "operator": "admin",
      "operation_time": "2024-03-15T10:30:00",
      "details": {"input_features_count": 3}
    },
    {
      "operation": "ACTIVATE",
      "operator": "admin",
      "operation_time": "2024-03-16T09:00:00",
      "reason": "准备上线"
    }
  ]
}
```

#### 获取模型类型列表

```bash
GET /api/v1/models/types/task
GET /api/v1/models/types/model?framework=sklearn
GET /api/v1/models/types/framework?model_type=xgboost
```

### 2. 评分卡API (/api/v1/scoring)

#### 单笔预测

```bash
POST /api/v1/scoring/predict
Content-Type: application/json

{
  "model_id": "MDL_20240315_ABCD1234",
  "application_id": "APP202403150001",
  "features": {
    "age": 35,
    "income": 50000,
    "credit_history": 720,
    "loan_amount": 100000,
    "employment_years": 5
  },
  "scoring": {  # 可选，评分卡参数
    "base_score": 600,
    "pdo": 50,
    "min_score": 320,
    "max_score": 960,
    "direction": "lower_better"
  }
}
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "total_score": 725,
    "feature_scores": {
      "age": 145.2,
      "income": 280.5,
      "credit_history": 195.3,
      "loan_amount": 104.0
    },
    "model_version": "1.0.0",
    "scoring_params": {
      "base_score": 600,
      "pdo": 50,
      "min_score": 320,
      "max_score": 960,
      "direction": "lower_better"
    }
  },
  "request_id": "req_abc123",
  "model_id": "MDL_20240315_ABCD1234"
}
```

#### 批量预测

```bash
POST /api/v1/scoring/batch
Content-Type: application/json

[
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
```

#### 响应示例

```json
{
  "total": 2,
  "success": 2,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "success": true,
      "data": {"total_score": 725, "feature_scores": {...}}
    },
    {
      "index": 1,
      "success": true,
      "data": {"total_score": 680, "feature_scores": {...}}
    }
  ],
  "errors": []
}
```

### 3. 反欺诈API (/api/v1/fraud)

#### 单笔预测

```bash
POST /api/v1/fraud/predict
Content-Type: application/json

{
  "model_id": "MDL_20240315_EFGH5678",
  "application_id": "APP202403150001",
  "features": {
    "ip_address": "192.168.1.1",
    "device_id": "device_123456",
    "user_agent": "Mozilla/5.0...",
    "amount": 10000,
    "transaction_hour": 14
  },
  "risk_config": {  # 可选，风险等级阈值配置
    "levels": {
      "low": {"max": 0.2},
      "medium": {"min": 0.2, "max": 0.5},
      "high": {"min": 0.5, "max": 0.8},
      "very_high": {"min": 0.8}
    }
  }
}
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "fraud_probability": 0.1234,
    "risk_factors": [
      {
        "factor": "device_id",
        "value": "device_123456",
        "weight": 0.5,
        "description": "设备指纹异常"
      }
    ],
    "risk_level": "low",
    "model_version": "1.0.0",
    "risk_config": {
      "levels": {
        "low": {"max": 0.2},
        "medium": {"min": 0.2, "max": 0.5},
        "high": {"min": 0.5, "max": 0.8},
        "very_high": {"min": 0.8}
      }
    }
  },
  "request_id": "req_abc123"
}
```

#### 预测解释

```bash
POST /api/v1/fraud/explain
Content-Type: application/json

{
  "model_id": "MDL_20240315_EFGH5678",
  "application_id": "APP202403150001",
  "features": {
    "ip_address": "192.168.1.1",
    "device_id": "device_123456",
    "amount": 10000
  }
}
```

#### 响应示例

```json
{
  "success": true,
  "data": {
    "fraud_probability": 0.1234,
    "risk_level": "low"
  },
  "explanation": {
    "contributions": [
      {
        "feature": "device_id",
        "value": "device_123456",
        "importance": 0.5,
        "impact": 0.3
      },
      {
        "feature": "ip_address",
        "value": "192.168.1.1",
        "importance": 0.3,
        "impact": 0.15
      }
    ],
    "feature_importance": {
      "device_id": 0.5,
      "ip_address": 0.3,
      "amount": 0.2
    }
  }
}
```

#### 批量预测

```bash
POST /api/v1/fraud/batch
```

### 4. 管理API (/api/v1/management)

#### 获取推理统计

```bash
GET /api/v1/management/stats/inference?days=7
```

#### 响应示例

```json
{
  "days": 7,
  "stats": [
    {
      "task_type": "scoring",
      "date": "2024-03-15",
      "total_requests": 15234,
      "avg_processing_time_ms": 87.5,
      "p95_processing_time_ms": 145.2
    }
  ]
}
```

#### 获取引擎统计

```bash
GET /api/v1/management/stats/engine
```

#### 响应示例

```json
{
  "inference_engine": {
    "total_inferences": 100000,
    "success_inferences": 99800,
    "failed_inferences": 200,
    "avg_duration_ms": 85.3,
    "success_rate": 0.998
  },
  "model_loader": {
    "loaded_models": 5,
    "models": [
      {
        "model_id": "MDL_...",
        "model_name": "credit_score_v2",
        "loaded_at": "2024-03-15T10:30:00"
      }
    ]
  }
}
```

#### 获取审计日志

```bash
GET /api/v1/management/audit/logs?limit=100&offset=0
```

#### 详细健康检查

```bash
GET /api/v1/management/health/detailed
```

#### 响应示例

```json
{
  "status": "healthy",
  "timestamp": "2024-03-15T10:30:00",
  "components": {
    "database": {
      "status": "healthy",
      "engines": {"default": "healthy"}
    },
    "model_loader": {
      "status": "healthy",
      "loaded_models": 5
    },
    "inference_engine": {
      "status": "healthy",
      "stats": {...}
    }
  },
  "version": "1.0.0",
  "environment": "production"
}
```

#### 清除缓存

```bash
POST /api/v1/management/cache/clear?cache_type=all
```

#### 获取配置信息

```bash
GET /api/v1/management/config
```

## 错误响应格式
```json
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "模型未找到: MDL_20240315_ABCD1234",
    "details": {
      "model_id": "MDL_20240315_ABCD1234"
    }
  },
  "request_id": "req_abc123"
}
```

## HTTP状态码
| 状态码 | 说明 | 示例 |
| :---: | :--- | :--- |
| 200 | 成功 | 请求成功处理 |
| 400 | 请求错误 | 参数验证失败 |
| 401 | 未认证 | 缺少API密钥 |
| 403 | 禁止访问 | 权限不足 |
| 404 | 资源不存在 | 模型未找到 |
| 409 | 资源冲突 | 模型已存在 |
| 422 | 无法处理 | 输入数据无效 |
| 429 | 请求过多 | 超过速率限制 |
| 500 | 服务器错误 | 内部错误 |


## 调试模式
```bash
# 启动调试模式
uvicorn main:app --reload --log-level debug

# 查看日志
tail -f logs/datamind.log
```











