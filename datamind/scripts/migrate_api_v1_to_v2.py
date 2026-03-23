# Datamind/datamind/scripts/migrate_api_v1_to_v2.py

"""API 版本迁移指南

从 v1 迁移到 v2 的注意事项和代码示例
"""

import json

# v1 响应格式
V1_RESPONSE = {
    "total_score": 685.42,
    "default_probability": 0.023,
    "feature_scores": {"age": 85.2, "income": 120.5},
    "model_id": "MDL_xxx",
    "model_version": "1.0.0",
    "application_id": "APP_001",
    "processing_time_ms": 12.5,
    "timestamp": "2024-01-01T00:00:00",
    "request_id": "req-123",
    "trace_id": "trace-456",
    "span_id": "span-789",
    "ab_test_info": None
}

# v2 响应格式
V2_RESPONSE = {
    "score": 685.42,
    "probability": 0.023,
    "feature_contributions": {"age": 85.2, "income": 120.5},
    "model": {
        "id": "MDL_xxx",
        "version": "1.0.0",
        "task_type": "scoring"
    },
    "request": {
        "id": "req-123",
        "trace_id": "trace-456",
        "application_id": "APP_001"
    },
    "performance": {
        "processing_time_ms": 12.5,
        "inference_time_ms": 10.2
    },
    "experiment": None
}


def migrate_v1_to_v2(v1_data: dict) -> dict:
    """将 v1 响应转换为 v2 格式"""
    return {
        "score": v1_data["total_score"],
        "probability": v1_data["default_probability"],
        "feature_contributions": v1_data["feature_scores"],
        "model": {
            "id": v1_data["model_id"],
            "version": v1_data["model_version"],
            "task_type": "scoring"
        },
        "request": {
            "id": v1_data["request_id"],
            "trace_id": v1_data["trace_id"],
            "application_id": v1_data["application_id"]
        },
        "performance": {
            "processing_time_ms": v1_data["processing_time_ms"],
            "inference_time_ms": v1_data["processing_time_ms"]
        },
        "experiment": v1_data.get("ab_test_info")
    }


# 客户端迁移示例
print("=== API 版本迁移指南 ===\n")
print("v1 端点: POST /api/v1/scoring/predict")
print("v2 端点: POST /api/v2/scoring/predict\n")

print("v1 请求格式:")
print(json.dumps({
    "application_id": "APP_001",
    "features": {"age": 35, "income": 50000},
    "model_id": "MDL_123"
}, indent=2))

print("\nv2 请求格式（新增 options 参数）:")
print(json.dumps({
    "application_id": "APP_001",
    "features": {"age": 35, "income": 50000},
    "model_id": "MDL_123",
    "options": {
        "return_feature_importance": True,
        "timeout_ms": 5000
    }
}, indent=2))