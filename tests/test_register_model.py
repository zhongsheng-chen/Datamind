# tests/test_register_model_unittest.py
import unittest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path
from src.register_model import ModelRegistry

class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        # 创建一个临时模型文件
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.tmp_dir.name) / "dummy_model.pkl"
        with open(self.model_path, "wb") as f:
            f.write(b"dummy model content")

        self.registry = ModelRegistry(
            model_name="test_model",
            model_type="dummy_type",
            model_path=str(self.model_path),
            framework="sklearn",
            task="test_task",
            force=True
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_create_hash_and_uuid(self):
        # 测试 hash
        model_hash = self.registry.create_hash()
        self.assertEqual(len(model_hash), 64)

        # 测试 UUID
        uuid_str = self.registry.create_identifier(model_hash)
        self.assertEqual(len(uuid_str), 36)

    def test_detect_framework(self):
        detected_framework = ModelRegistry.detect_framework(str(self.model_path))
        self.assertEqual(detected_framework, "sklearn")

    @patch("register_model.bentoml.sklearn.save_model")
    @patch("register_model.ModelRegistry.write_model_registry")
    def test_register_model(self, mock_write_registry, mock_save_model):
        # Mock 返回一个对象，含 tag 和 version
        mock_artifact = MagicMock()
        mock_artifact.tag = "v1.0"
        mock_artifact.info.version = "1.0.0"
        mock_save_model.return_value = mock_artifact

        # 执行注册
        self.registry.register_model()

        # 验证 save_model 被调用
        mock_save_model.assert_called_once_with(
            self.registry.model_name, unittest.mock.ANY, signatures=unittest.mock.ANY
        )

        # 验证写入注册表
        mock_write_registry.assert_called_once()
        args, kwargs = mock_write_registry.call_args
        self.assertEqual(args[0], "1.0.0")  # version
        self.assertEqual(args[2], "v1.0")   # tag

if __name__ == "__main__":
    unittest.main()
