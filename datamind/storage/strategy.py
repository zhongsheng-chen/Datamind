# datamind/storage/strategy.py

"""存储键策略

统一 key 规则定义层，是唯一 key 规则来源。

核心功能：
  - model_key: 构造模型文件的完整 key
  - model_prefix: 构造模型目录的 key 前缀
  - extract_filename: 从 key 中提取文件名
  - validate_model_dir: 校验模型目录名合法性
  - validate_model_id: 校验模型 ID 合法性
  - validate_version: 校验模型版本号合法性
  - validate_filename: 校验文件名合法性

使用示例：
  from datamind.storage.strategy import StorageKeyStrategy

  strategy = StorageKeyStrategy(
      model_dir="models"
  )

  key = strategy.model_key(
      model_id="mdl_0123456789abcdef",
      version="1.0.0",
      artifact_id="art_0123456789abcdef",
      filename="model.pkl",
  )

  prefix = strategy.model_prefix(
      model_id="mdl_0123456789abcdef"
  )

  filename = strategy.extract_filename(
      key
  )
"""

import re


class StorageKeyStrategy:
    """统一 key 规则定义层（唯一 key 规则来源）"""

    # 合法的模型目录名和模型 ID：字母、数字、下划线、连字符
    _VALID_IDENTIFIER_PATTERN = re.compile(
        r"^[a-zA-Z0-9_-]+$"
    )

    # 合法的版本号：
    # 必须以字母或数字开头，可包含字母、数字、点、下划线、加号和连字符
    _VALID_VERSION_PATTERN = re.compile(
        r"^[a-zA-Z0-9][a-zA-Z0-9._+-]*$"
    )

    def __init__(
            self,
            model_dir: str,
    ) -> None:
        """初始化 key 策略

        参数：
            model_dir: 模型目录名
        """
        self.validate_model_dir(model_dir)
        self.model_dir = model_dir

    @classmethod
    def validate_model_dir(
            cls,
            model_dir: str,
    ) -> None:
        """校验模型目录名合法性

        参数：
            model_dir: 模型目录名

        异常：
            ValueError: 模型目录名不合法
        """
        if (
                not isinstance(model_dir, str)
                or cls._VALID_IDENTIFIER_PATTERN.fullmatch(model_dir) is None
        ):
            raise ValueError(
                f"非法的模型目录名: {model_dir}，"
                "只能包含字母、数字、下划线和连字符"
            )

    @classmethod
    def validate_model_id(
            cls,
            model_id: str,
    ) -> None:
        """校验模型 ID 合法性

        参数：
            model_id: 模型 ID

        异常：
            ValueError: 模型 ID 不合法
        """
        if (
                not isinstance(model_id, str)
                or cls._VALID_IDENTIFIER_PATTERN.fullmatch(model_id) is None
        ):
            raise ValueError(
                f"非法的模型 ID: {model_id}，"
                "只能包含字母、数字、下划线和连字符"
            )

    @classmethod
    def validate_version(
            cls,
            version: str,
    ) -> None:
        """校验模型版本号合法性

        参数：
            version: 模型版本号

        异常：
            ValueError: 模型版本号不合法
        """
        if (
                not isinstance(version, str)
                or cls._VALID_VERSION_PATTERN.fullmatch(version) is None
        ):
            raise ValueError(
                f"非法的模型版本号: {version}，"
                "必须以字母或数字开头，且只能包含字母、数字、"
                "点、下划线、加号和连字符"
            )

    @staticmethod
    def validate_filename(
            filename: str,
    ) -> None:
        """校验文件名合法性

        参数：
            filename: 文件名

        异常：
            ValueError: 文件名不合法
        """
        if (
                not isinstance(filename, str)
                or not filename
                or filename in {".", ".."}
                or "/" in filename
                or "\\" in filename
                or "\x00" in filename
        ):
            raise ValueError(
                f"非法的文件名: {filename}，"
                "文件名不能为空，且不能包含路径分隔符、"
                "空字符或使用 . / .."
            )

    def model_key(
            self,
            model_id: str,
            version: str,
            artifact_id: str,
            filename: str,
    ) -> str:
        """构造模型文件的完整 key

        参数：
            model_id: 模型 ID
            version: 模型版本号
            artifact_id: 模型制品 ID
            filename: 文件名

        返回：
            完整 key，格式为：
            {model_dir}/{model_id}/{version}/
            artifacts/{artifact_id}/{filename}

        异常：
            ValueError: 参数不合法
        """
        self.validate_model_id(model_id)
        self.validate_version(version)
        self.validate_model_id(artifact_id)
        self.validate_filename(filename)

        return (
            f"{self.model_dir}/"
            f"{model_id}/"
            f"{version}/artifacts/"
            f"{artifact_id}/"
            f"{filename}"
        )

    def model_prefix(
            self,
            model_id: str,
    ) -> str:
        """构造模型目录的 key 前缀

        参数：
            model_id: 模型 ID

        返回：
            key 前缀，格式为：
            {model_dir}/{model_id}/
        """
        self.validate_model_id(model_id)

        return f"{self.model_dir}/{model_id}/"

    @classmethod
    def extract_filename(
            cls,
            key: str,
    ) -> str:
        """从 key 中提取文件名

        参数：
            key: 完整存储键

        返回：
            文件名

        异常：
            ValueError: 存储键为空或未包含有效文件名
        """
        if (
                not isinstance(key, str)
                or not key
                or "\x00" in key
        ):
            raise ValueError(
                f"非法的存储键: {key}"
            )

        normalized_key = key.replace(
            "\\",
            "/",
        )

        filename = normalized_key.rsplit(
            "/",
            maxsplit=1,
        )[-1]

        cls.validate_filename(filename)

        return filename
