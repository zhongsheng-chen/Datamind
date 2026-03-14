#!/bin/bash
# datamind/serving/docker/entrypoint.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印横幅
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Datamind Model Serving Container                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 获取服务类型
SERVICE_TYPE=${SERVICE_TYPE:-scoring}
ENVIRONMENT=${ENVIRONMENT:-production}
LOG_LEVEL=${LOG_LEVEL:-INFO}

echo -e "${GREEN}服务配置:${NC}"
echo "  • 服务类型: ${SERVICE_TYPE}"
echo "  • 环境: ${ENVIRONMENT}"
echo "  • 日志级别: ${LOG_LEVEL}"
echo "  • 工作目录: $(pwd)"
echo ""

# 检查必要的环境变量
echo -e "${YELLOW}检查环境变量...${NC}"

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}警告: DATABASE_URL 未设置，将使用默认值${NC}"
    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/datamind"
fi

if [ -z "$REDIS_URL" ]; then
    echo -e "${RED}警告: REDIS_URL 未设置，将使用默认值${NC}"
    export REDIS_URL="redis://localhost:6379/0"
fi

echo -e "${GREEN}✓ 环境变量检查完成${NC}\n"

# 等待依赖服务
echo -e "${YELLOW}等待依赖服务就绪...${NC}"

# 等待数据库
if [ -n "$DATABASE_URL" ]; then
    echo -n "等待数据库..."
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\).*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT=${DB_PORT:-5432}

    until pg_isready -h $DB_HOST -p $DB_PORT -U postgres; do
        echo -n "."
        sleep 2
    done
    echo -e " ${GREEN}就绪${NC}"
fi

# 等待Redis
if [ -n "$REDIS_URL" ]; then
    echo -n "等待Redis..."
    REDIS_HOST=$(echo $REDIS_URL | sed -n 's/.*@\([^:]*\).*/\1/p')
    REDIS_PORT=$(echo $REDIS_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    REDIS_PORT=${REDIS_PORT:-6379}

    until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping; do
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}就绪${NC}"
fi

echo -e "${GREEN}✓ 所有依赖服务已就绪${NC}\n"

# 加载生产模型
echo -e "${YELLOW}加载生产模型...${NC}"
python << END
import sys
import os
sys.path.insert(0, '/app')

from core.logging import log_manager, debug_print
from core.ml import model_registry, model_loader
from config.logging_config import LoggingConfig

# 初始化日志
log_config = LoggingConfig.load()
log_manager.initialize(log_config)

debug_print("Entrypoint", "开始加载生产模型")

try:
    # 获取生产模型
    models = model_registry.list_models(is_production=True)
    debug_print("Entrypoint", f"找到 {len(models)} 个生产模型")

    loaded_count = 0
    for model in models:
        try:
            debug_print("Entrypoint", f"加载模型: {model['model_name']} v{model['model_version']}")
            success = model_loader.load_model(
                model_id=model['model_id'],
                operator="serving",
                ip_address="internal"
            )
            if success:
                loaded_count += 1
                print(f"  ✓ {model['model_name']} v{model['model_version']}")
            else:
                print(f"  ✗ {model['model_name']} v{model['model_version']} - 加载失败")
        except Exception as e:
            print(f"  ✗ {model['model_name']} v{model['model_version']} - {str(e)}")

    print(f"\n成功加载 {loaded_count}/{len(models)} 个模型")

except Exception as e:
    print(f"加载模型失败: {e}")
    sys.exit(1)
END

echo -e "${GREEN}✓ 模型加载完成${NC}\n"

# 选择服务文件
if [ "$SERVICE_TYPE" = "fraud" ]; then
    SERVICE_FILE="fraud_service.py"
    echo -e "${GREEN}启动反欺诈服务...${NC}"
else
    SERVICE_FILE="scoring_service.py"
    echo -e "${GREEN}启动评分卡服务...${NC}"
fi

# 打印服务信息
echo -e "${BLUE}"
echo "══════════════════════════════════════════════════════════"
echo "  服务信息"
echo "══════════════════════════════════════════════════════════"
echo "  类型: ${SERVICE_TYPE}"
echo "  端口: 3000"
echo "  健康检查: http://localhost:3000/health"
echo "  指标: http://localhost:3000/metrics"
echo "  预测接口: http://localhost:3000/predict"
echo "══════════════════════════════════════════════════════════"
echo -e "${NC}"

# 启动BentoML服务
exec bentoml serve "${SERVICE_FILE}:service" \
    --production \
    --host 0.0.0.0 \
    --port 3000 \
    --reload \
    --enable-swagger-ui