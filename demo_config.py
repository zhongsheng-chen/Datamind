#!/usr/bin/env python
# config_demo.py

"""配置组件使用示例

演示 datamind.config 模块的各种使用方式。

运行方式：
  python config_demo.py

环境变量示例（.env 文件）：
  DATAMIND_ENVIRONMENT=production
  DATAMIND_SERVICE_PORT=9090
  DATAMIND_STORAGE_TYPE=minio
  DATAMIND_STORAGE_MINIO_ENDPOINT=minio.example.com:9000
  DATAMIND_STORAGE_MINIO_BUCKET=datamind-models
  DATAMIND_LOG_LEVEL=DEBUG
  DATAMIND_DB_HOST=192.168.1.100
"""

from datamind.config import get_settings
from datamind.constants import (
    StorageType,
    Environment,
    LogLevel,
    LogFormat,
    ModelStage,
)


def demo_basic_usage():
    """基础使用示例"""
    print("=" * 50)
    print("1. 基础使用示例")
    print("=" * 50)

    settings = get_settings()

    # 服务配置
    print(f"服务名称: {settings.service.name}")
    print(f"服务版本: {settings.service.version}")
    print(f"运行环境: {settings.service.environment}")
    print(f"监听地址: {settings.service.host}:{settings.service.port}")
    print(f"工作进程数: {settings.service.workers}")
    print(f"请求超时: {settings.service.timeout}秒")
    print(f"启用文档: {settings.service.enable_docs}")
    print(f"启用健康检查: {settings.service.enable_health_check}")


def demo_storage_config():
    """存储配置示例"""
    print("\n" + "=" * 50)
    print("2. 存储配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"存储类型: {settings.storage.type}")
    print(f"模型目录: {settings.storage.model_dir}")
    print(f"最大文件大小: {settings.storage.max_file_size / 1024 / 1024} MB")

    if settings.storage.type == StorageType.local:
        print(f"本地存储目录: {settings.storage.local.base_dir}")
    elif settings.storage.type == StorageType.minio:
        print(f"MinIO端点: {settings.storage.minio.endpoint}")
        print(f"MinIO存储桶: {settings.storage.minio.bucket}")
        print(f"MinIO安全连接: {settings.storage.minio.secure}")
        print(f"MinIO区域: {settings.storage.minio.region}")


def demo_database_config():
    """数据库配置示例"""
    print("\n" + "=" * 50)
    print("3. 数据库配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"数据库主机: {settings.database.host}:{settings.database.port}")
    print(f"数据库用户: {settings.database.user}")
    print(f"数据库名称: {settings.database.database}")
    print(f"密码已设置: {'是' if settings.database.password else '否'}")


def demo_logging_config():
    """日志配置示例"""
    print("\n" + "=" * 50)
    print("4. 日志配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"日志级别: {settings.logging.level}")
    print(f"日志格式: {settings.logging.format}")
    print(f"日志目录: {settings.logging.dir}")
    print(f"日志文件名: {settings.logging.filename}")
    print(f"控制台输出: {settings.logging.enable_console}")
    print(f"文件输出: {settings.logging.enable_file}")


def demo_audit_config():
    """审计配置示例"""
    print("\n" + "=" * 50)
    print("5. 审计配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"记录请求日志: {settings.audit.enable_request_log}")
    print(f"记录响应日志: {settings.audit.enable_response_log}")
    print(f"记录请求体: {settings.audit.log_request_body}")
    print(f"记录响应体: {settings.audit.log_response_body}")
    print(f"追踪ID头: {settings.audit.trace_id_header}")
    print(f"日志保留天数: {settings.audit.retention_days}")


def demo_model_config():
    """模型配置示例"""
    print("\n" + "=" * 50)
    print("6. 模型配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"启用热加载: {settings.model.enable_hot_reload}")


def demo_ab_test_config():
    """AB测试配置示例"""
    print("\n" + "=" * 50)
    print("7. AB测试配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"AB测试启用: {settings.ab_test.enabled}")
    if settings.ab_test.enabled:
        print(f"A组权重: {settings.ab_test.group_a_weight}")
        print(f"B组权重: {settings.ab_test.group_b_weight}")
        print(f"分流策略: {settings.ab_test.strategy}")


def demo_scorecard_config():
    """评分卡配置示例"""
    print("\n" + "=" * 50)
    print("8. 评分卡配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"基准分: {settings.scorecard.base_score}")
    print(f"基准好坏比: {settings.scorecard.base_odds}")
    print(f"PDO: {settings.scorecard.pdo}")
    print(f"评分范围: [{settings.scorecard.min_score}, {settings.scorecard.max_score}]")


def demo_classification_config():
    """分类模型配置示例"""
    print("\n" + "=" * 50)
    print("9. 分类模型配置示例")
    print("=" * 50)

    settings = get_settings()

    print(f"分类阈值: {settings.classification.threshold}")


def demo_conditional_logic():
    """条件逻辑示例"""
    print("\n" + "=" * 50)
    print("10. 条件逻辑示例")
    print("=" * 50)

    settings = get_settings()

    # 根据运行环境执行不同逻辑
    if settings.service.environment == Environment.PRODUCTION:
        print("🟢 生产环境：启用完整监控")
    elif settings.service.environment == Environment.STAGING:
        print("🟡 预发布环境：启用灰度验证")
    elif settings.service.environment == Environment.TESTING:
        print("🔵 测试环境：启用测试模式")
    else:
        print("⚪ 开发环境：启用调试模式")

    # 根据存储类型执行不同逻辑
    if settings.storage.type == StorageType.minio:
        print(f"📦 使用 MinIO 对象存储，端点: {settings.storage.minio.endpoint}")
    else:
        print(f"💾 使用本地文件存储，目录: {settings.storage.local.base_dir}")

    # 根据日志级别执行不同逻辑
    if settings.logging.level == LogLevel.DEBUG:
        print("🐛 调试模式已启用，将输出详细日志")
    elif settings.logging.level == LogLevel.INFO:
        print("ℹ️ 信息模式，输出常规日志")
    elif settings.logging.level == LogLevel.WARNING:
        print("⚠️ 警告模式，仅输出警告和错误")
    else:
        print("❌ 错误模式，仅输出错误")

    # 根据日志格式执行不同逻辑
    if settings.logging.format == LogFormat.JSON:
        print("📋 使用 JSON 格式日志，便于日志采集")
    else:
        print("📝 使用文本格式日志，便于人工阅读")


def demo_config_modification_prevention():
    """配置不可变演示"""
    print("\n" + "=" * 50)
    print("11. 配置不可变演示")
    print("=" * 50)

    settings = get_settings()

    print(f"原始端口: {settings.service.port}")

    try:
        # 尝试修改配置（frozen=True 会阻止修改）
        settings.service.port = 9999
        print("❌ 配置被修改了（不应该发生）")
    except Exception as e:
        print(f"✅ 配置不可变，修改被阻止: {type(e).__name__}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Datamind 配置组件演示")
    print("=" * 60)

    try:
        demo_basic_usage()
        demo_storage_config()
        demo_database_config()
        demo_logging_config()
        demo_audit_config()
        demo_model_config()
        demo_ab_test_config()
        demo_scorecard_config()
        demo_classification_config()
        demo_conditional_logic()
        demo_config_modification_prevention()

        print("\n" + "=" * 60)
        print("✅ 配置组件演示完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        raise


if __name__ == "__main__":
    main()