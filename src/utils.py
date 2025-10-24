from pathlib import Path
from src.config_parser import config
from src.setup import setup_logger

logger = setup_logger()

def get_model_info(business_name: str) -> dict:
    """
    根据业务名称返回模型名称、路径、模型类型、版本、uuid以及特征信息。

    参数:
        business_name (str): 业务名称

    返回:
        dict: 包含模型信息的字典
            {
                "model_type": str,
                "model_name": str,
                "model_path": str,
                "version": str,
                "uuid": str,
                "features": list
            }

    异常:
        ValueError: 如果配置中没有找到该业务名称
        KeyError: 如果配置中缺少必要字段
    """

    model_registry = config.get("model_registry", {})

    if business_name not in model_registry:
        logger.error(f"未找到业务名称 {business_name} 在 model_registry 配置中")
        raise ValueError(f"{business_name} 不存在于 model_registry 配置中")

    try:
        info = model_registry[business_name]

        # 提取模型信息
        model_type = info.get("model_type", "")
        model_name = info.get("model_name", "")
        model_path = Path(info.get("model_path", ""))

        root = Path(__file__).resolve().parent.parent

        # 如果 model_path 不是绝对路径，则拼接根目录路径
        if not model_path.is_absolute():
            model_path = root / model_path

        model_path = model_path.resolve().as_posix()

        # 确保路径的父目录存在
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        version = info.get("version", "")
        uuid = info.get("uuid", "")
        features = info.get("features", [])

        # 检查必需的字段是否存在
        if not model_name or not model_type:
            raise KeyError(f"模型配置缺少必要字段：model_name 或 model_type")

        logger.info(f"成功获取 {business_name} 模型信息 - {model_name} 路径: {model_path}")
        return {
            "model_type": model_type,
            "model_name": model_name,
            "model_path": model_path,
            "version": version,
            "uuid": uuid,
            "features": features
        }

    except KeyError as e:
        logger.error(f"配置文件缺少字段: {e}")
        raise

    except Exception as e:
        logger.exception(f"获取模型信息时发生错误: {e}")
        raise


