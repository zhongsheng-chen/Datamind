# main.py
from config.logging_config import LoggingConfig, LogLevel, LogFormat, TimeZone, TimestampPrecision

# 直接从环境变量读取
config = LoggingConfig()
print("从环境变量读取的配置:")
print(f"name: {config.name}")
print(f"level: {config.level}")
print(f"format: {config.format}")
print(f"timezone: {config.timezone}")
print("-" * 50)

# 或者指定不同的 .env 文件
config = LoggingConfig(_env_file="../.env.production")
print("从 .env.production 读取的配置:")
print(f"name: {config.name}")
print(f"level: {config.level}")
print(f"format: {config.format}")
print("-" * 50)

# 或者混合使用（直接指定部分参数，其他从环境变量读取）
config = LoggingConfig(
    name="CustomLogger",  # 直接指定
    level=LogLevel.DEBUG,  # 直接指定（现在可以了，因为已经导入）
    format=LogFormat.JSON,  # 直接指定
    timezone=TimeZone.CST,  # 直接指定
    timestamp_precision=TimestampPrecision.MILLISECONDS,  # 直接指定
    max_bytes=52428800,  # 50MB
    _env_file="../.env"  # 其他配置从环境变量读取
)

print("混合配置结果:")
print(f"name: {config.name}")  # CustomLogger
print(f"level: {config.level}")  # LogLevel.DEBUG
print(f"format: {config.format}")  # LogFormat.JSON
print(f"timezone: {config.timezone}")  # TimeZone.CST
print(f"timestamp_precision: {config.timestamp_precision}")  # TimestampPrecision.MILLISECONDS
print(f"max_bytes: {config.max_bytes}")  # 52428800 (从直接指定)
print(f"backup_count: {config.backup_count}")  # 从环境变量读取
print(f"file: {config.file}")  # 从环境变量读取