#!/bin/bash
set -e

echo "========================================="
echo "初始化 Datamind PostgreSQL 主库"
echo "========================================="

# 等待 PostgreSQL 启动
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
    echo "等待 PostgreSQL 启动..."
    sleep 2
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 创建复制用户
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'replicator') THEN
            CREATE USER replicator WITH REPLICATION LOGIN ENCRYPTED PASSWORD '${REPLICA_PASSWORD:-replica123}';
        END IF;
    END
    \$\$;

    -- 创建复制槽（如果不存在）
    SELECT pg_create_physical_replication_slot('replica_slot')
    WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replica_slot');

    -- 创建只读用户
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'readonly') THEN
            CREATE USER readonly WITH LOGIN ENCRYPTED PASSWORD '${READONLY_PASSWORD:-readonly123}';
        END IF;
    END
    \$\$;
    GRANT CONNECT ON DATABASE datamind TO readonly;
    GRANT USAGE ON SCHEMA public TO readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly;

    -- 创建监控用户
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'monitor') THEN
            CREATE USER monitor WITH LOGIN ENCRYPTED PASSWORD '${MONITOR_PASSWORD:-monitor123}';
        END IF;
    END
    \$\$;
    GRANT CONNECT ON DATABASE datamind TO monitor;
    GRANT pg_read_all_settings TO monitor;
    GRANT pg_read_all_stats TO monitor;
    GRANT pg_stat_scan_tables TO monitor;

    -- 创建扩展
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

    -- 显示配置
    \x
    SELECT * FROM pg_replication_slots;
EOSQL

echo "主库初始化完成"