# scripts/list_models.py
"""列出已注册的模型"""

import sys
import logging

from datamind.config import get_settings, BASE_DIR
from datamind.core.db.database import db_manager
from datamind.core.ml.model import model_registry
from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs

# 安装启动日志
install_bootstrap_logger()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()

try:
    logger.info("=" * 50)
    logger.info("开始列出已注册模型")
    logger.info(f"项目根目录: {BASE_DIR}")
    logger.info(f"数据库URL: {settings.database.url.split('@')[-1]}")

    # 初始化数据库连接
    logger.info("初始化数据库连接...")
    db_manager.initialize()
    logger.info("数据库连接初始化成功")

    # 列出模型
    models = model_registry.list_models()
    logger.info(f"共找到 {len(models)} 个模型")

    for m in models:
        logger.info(f"模型: {m['model_name']} v{m['model_version']}")
        logger.info(f"  ID: {m['model_id']}")
        logger.info(f"  状态: {m['status']}")
        logger.info(f"  生产: {m['is_production']}")
        logger.info(f"  任务类型: {m['task_type']}")
        logger.info(f"  框架: {m['framework']}")

    logger.info("=" * 50)
    logger.info("列出完成")

except Exception as e:
    logger.error(f"列出模型失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    flush_bootstrap_logs()