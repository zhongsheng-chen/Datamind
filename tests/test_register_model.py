import unittest
from unittest.mock import patch, MagicMock
from src.register_model import ModelRegistry

class TestRegisterModel(unittest.TestCase):

    @patch("src.register_model.update_config_yaml")  # 不修改 config.yaml
    @patch("src.register_model.ModelRegistry.write_model_registry")  # 不写入数据库
    @patch("src.register_model.bentoml.sklearn.save_model")  # mock bentoml 保存
    @patch("joblib.load")  # mock joblib.load
    @patch("builtins.open")  # mock 文件打开
    def test_register_sklearn_lightweight(self, mock_open, mock_joblib_load, mock_save_model, mock_write_registry, mock_update_yaml):
        """
        测试 sklearn 模型注册逻辑，轻量化，不依赖真实文件或数据库
        """
        # Mock 返回一个 dummy 模型对象
        mock_model = MagicMock()
        mock_joblib_load.return_value = mock_model

        # Mock bentoml save_model 返回 dummy artifact
        dummy_artifact = MagicMock()
        dummy_artifact.tag = "test_tag"
        dummy_artifact.info.version = "0.1.0"
        mock_save_model.return_value = dummy_artifact

        # 创建 ModelRegistry 实例
        registry = ModelRegistry(
            model_name="test_model",
            model_type="sklearn",
            model_path="/tmp/dummy_model.pkl",
            framework="sklearn",
            task="classification",
            force=True
        )

        # 调用注册方法
        registry.register_model()

        # 断言 bentoml.sklearn.save_model 被调用一次
        mock_save_model.assert_called_once_with(
            "test_model",
            mock_model,
            signatures={"predict": {"batchable": False}, "predict_proba": {"batchable": False}}
        )

        # 断言 write_model_registry 被调用一次
        mock_write_registry.assert_called_once()
        # 断言 update_config_yaml 被调用一次
        mock_update_yaml.assert_called_once()

if __name__ == "__main__":
    unittest.main()
