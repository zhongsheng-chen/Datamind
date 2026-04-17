# datamind/storage/strategy.py

"""存储键策略

统一 key 规则定义层，是唯一 key 规则来源。

核心功能：
  - model_key: 构造模型文件的完整 key
  - model_prefix: 构造模型目录的 key 前缀
  - extract_filename: 从 key 中提取文件名
  - validate_model_id: 校验模型ID合法性
  - validate_filename: 校验文件名合法性

特性：
  - 唯一来源：所有 key 规则在此定义
  - 单一职责：只负责 key 规则
  - 易于扩展：支持未来添加版本、租户等维度
  - 解析统一：key 的解析规则也集中管理
  - 输入校验：防止非法输入
"""

import re


class StorageKeyStrategy:
    """统一 key 规则定义层（唯一 key 规则来源）"""

    # 合法的模型ID：字母、数字、下划线、连字符
    _VALID_MODEL_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    # 合法的文件名：不能包含路径分隔符
    _VALID_FILENAME_PATTERN = re.compile(r'^[^/\\]+$')

    def __init__(self, model_dir: str):
        """初始化 key 策略

        参数：
            model_dir: 模型目录名
        """
        self.model_dir = model_dir

    def validate_model_id(self, model_id: str) -> None:
        """校验模型ID合法性

        参数：
            model_id: 模型ID

        异常：
            ValueError: 模型ID不合法
        """
        if not self._VALID_MODEL_ID_PATTERN.match(model_id):
            raise ValueError(f"非法的模型ID: {model_id}，只能包含字母、数字、下划线、连字符")

    def validate_filename(self, filename: str) -> None:
        """校验文件名合法性

        参数：
            filename: 文件名

        异常：
            ValueError: 文件名不合法
        """
        if not self._VALID_FILENAME_PATTERN.match(filename):
            raise ValueError(f"非法的文件名: {filename}，不能包含路径分隔符")
        if not filename or filename in ('.', '..'):
            raise ValueError(f"非法的文件名: {filename}")

    def model_key(self, model_id: str, filename: str) -> str:
        """构造模型文件的完整 key

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            完整 key，格式: {model_dir}/{model_id}/{filename}

        异常：
            ValueError: 参数不合法
        """
        self.validate_model_id(model_id)
        self.validate_filename(filename)
        return f"{self.model_dir}/{model_id}/{filename}"

    def model_prefix(self, model_id: str) -> str:
        """构造模型目录的 key 前缀

        参数：
            model_id: 模型ID

        返回：
            key 前缀，格式: {model_dir}/{model_id}/
        """
        self.validate_model_id(model_id)
        return f"{self.model_dir}/{model_id}/"

    @staticmethod
    def extract_filename(key: str) -> str:
        """从 key 中提取文件名

        参数：
            key: 完整存储键

        返回：
            文件名
        """
        return key.split("/")[-1]