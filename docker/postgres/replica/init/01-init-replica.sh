#!/bin/bash
set -e

echo "========================================="
echo "Datamind PostgreSQL 备库初始化脚本"
echo "========================================="

# 注意：备库的数据目录将由 pg_basebackup 填充
# 这个脚本只在容器首次启动时运行，但备库的数据目录会被覆盖
# 所以这个脚本主要用于显示信息

echo "备库将由主库自动初始化"
echo "等待主库数据同步..."

# 等待备库成为只读模式
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; then
        IS_RECOVERY=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT pg_is_in_recovery();" 2>/dev/null | xargs)
        if [ "$IS_RECOVERY" = "t" ]; then
            echo "备库已就绪并处于恢复模式"
            break
        fi
    fi
    echo "等待备库就绪... (尝试 $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

echo "备库初始化完成"