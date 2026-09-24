"""存储键策略测试.

验证模型目录、模型 ID、版本号、文件名和存储键格式。

核心功能：
  - test_strategy_preserves_valid_model_dir:
    验证保留合法模型目录
  - test_validate_model_dir_accepts_valid_identifiers:
    验证模型目录接受合法标识
  - test_validate_model_dir_rejects_invalid_values:
    验证模型目录拒绝非法值
  - test_validate_model_name_accepts_valid_identifiers:
    验证模型名称接受合法标识
  - test_validate_model_name_rejects_invalid_values:
    验证模型名称拒绝非法值
  - test_validate_version_accepts_valid_values:
    验证版本号接受合法值
  - test_validate_version_rejects_invalid_values:
    验证版本号拒绝非法值
  - test_validate_filename_accepts_valid_values:
    验证文件名接受合法值
  - test_validate_filename_rejects_invalid_values:
    验证文件名拒绝非法值
  - test_model_key_builds_expected_key:
    验证构造预期模型键
  - test_model_key_validates_components:
    验证模型键校验所有组成部分
  - test_model_prefix_builds_expected_prefix:
    验证构造预期模型前缀
  - test_model_prefix_validates_model_id:
    验证模型前缀校验模型 ID
  - test_extract_filename_returns_last_component:
    验证提取存储键末尾文件名
  - test_extract_filename_rejects_invalid_key:
    验证文件名提取拒绝非法键
"""

from typing import Any

import pytest

from datamind.storage.strategy import StorageKeyStrategy


def test_strategy_preserves_valid_model_dir() -> None:
    """测试保存合法模型目录."""
    strategy = StorageKeyStrategy(
        model_dir="model_registry"
    )

    assert strategy.model_dir == "model_registry"


@pytest.mark.parametrize(
    "model_dir",
    [
        "models",
        "model_registry",
        "model-registry",
        "Models2026",
    ],
)
def test_validate_model_dir_accepts_valid_identifiers(
    model_dir: str,
) -> None:
    """测试接受合法模型目录名."""
    strategy = StorageKeyStrategy(
        model_dir=model_dir
    )

    assert strategy.model_dir == model_dir


@pytest.mark.parametrize(
    "model_dir",
    [
        "",
        " ",
        "model registry",
        "models/data",
        r"models\data",
        "models.data",
        "模型",
        None,
        123,
    ],
)
def test_validate_model_dir_rejects_invalid_values(
    model_dir: Any,
) -> None:
    """测试拒绝非法模型目录名."""
    with pytest.raises(
        ValueError,
        match="非法的模型目录名",
    ):
        StorageKeyStrategy(
            model_dir=model_dir
        )


@pytest.mark.parametrize(
    "model_name",
    [
        "scorecard",
        "model-2026",
        "model_001",
        "risk.score",
    ],
)
def test_validate_model_name_accepts_valid_identifiers(
    model_name: str,
) -> None:
    """测试接受合法模型名称."""
    StorageKeyStrategy.validate_model_name(
        model_name
    )


@pytest.mark.parametrize(
    "model_name",
    [
        "",
        " ",
        "model id",
        "model/id",
        r"model\id",
        "MODEL_001",
        "模型",
        None,
        123,
    ],
)
def test_validate_model_name_rejects_invalid_values(
    model_name: Any,
) -> None:
    """测试拒绝非法模型名称."""
    with pytest.raises(
        ValueError,
        match="非法的模型名称",
    ):
        StorageKeyStrategy.validate_model_name(
            model_name
        )


@pytest.mark.parametrize(
    "version",
    [
        "1",
        "1.0.0",
        "v1.0.0",
        "1.0.0-rc1",
        "1.0.0+build",
        "version_1",
    ],
)
def test_validate_version_accepts_valid_values(
    version: str,
) -> None:
    """测试接受合法模型版本号."""
    StorageKeyStrategy.validate_version(
        version
    )


@pytest.mark.parametrize(
    "version",
    [
        "",
        " ",
        ".1.0.0",
        "-1.0.0",
        "_1.0.0",
        "+1.0.0",
        "1/0/0",
        r"1\0\0",
        "版本1",
        None,
        123,
    ],
)
def test_validate_version_rejects_invalid_values(
    version: Any,
) -> None:
    """测试拒绝非法模型版本号."""
    with pytest.raises(
        ValueError,
        match="非法的模型版本号",
    ):
        StorageKeyStrategy.validate_version(
            version
        )


@pytest.mark.parametrize(
    "filename",
    [
        "model.pkl",
        "scorecard.joblib",
        "模型说明.txt",
        "model 2026.pkl",
        ".hidden",
    ],
)
def test_validate_filename_accepts_valid_values(
    filename: str,
) -> None:
    """测试接受合法文件名."""
    StorageKeyStrategy.validate_filename(
        filename
    )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        ".",
        "..",
        "models/model.pkl",
        r"models\model.pkl",
        "model\x00.pkl",
        None,
        123,
    ],
)
def test_validate_filename_rejects_invalid_values(
    filename: Any,
) -> None:
    """测试拒绝非法文件名."""
    with pytest.raises(
        ValueError,
        match="非法的文件名",
    ):
        StorageKeyStrategy.validate_filename(
            filename
        )


def test_model_key_builds_expected_key() -> None:
    """测试构造完整模型存储键."""
    strategy = StorageKeyStrategy(
        model_dir="models"
    )

    key = strategy.model_key(
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_0123456789abcdef",
        filename="scorecard.pkl",
    )

    assert key == (
        "models/scorecard/"
        "1.0.0/"
        "artifacts/art_0123456789abcdef/scorecard.pkl"
    )


@pytest.mark.parametrize(
    (
        "model_id",
        "version",
        "artifact_id",
        "filename",
        "error_message",
    ),
    [
        (
            "model/id",
            "1.0.0",
            "art_0123456789abcdef",
            "model.pkl",
            "非法的模型名称",
        ),
        (
            "mdl_0123456789abcdef",
            ".1.0.0",
            "art_0123456789abcdef",
            "model.pkl",
            "非法的模型版本号",
        ),
        (
            "mdl_0123456789abcdef",
            "1.0.0",
            "artifact/id",
            "model.pkl",
            "非法的模型制品 ID",
        ),
        (
            "mdl_0123456789abcdef",
            "1.0.0",
            "art_0123456789abcdef",
            "models/model.pkl",
            "非法的文件名",
        ),
    ],
)
def test_model_key_validates_components(
    model_id: str,
    version: str,
    artifact_id: str,
    filename: str,
    error_message: str,
) -> None:
    """测试构造存储键前校验各组成部分."""
    strategy = StorageKeyStrategy(
        model_dir="models"
    )

    with pytest.raises(
        ValueError,
        match=error_message,
    ):
        strategy.model_key(
            model_name=model_id,
            version=version,
            artifact_id=artifact_id,
            filename=filename,
        )


def test_model_prefix_builds_expected_prefix() -> None:
    """测试构造模型目录前缀."""
    strategy = StorageKeyStrategy(
        model_dir="models"
    )

    prefix = strategy.model_prefix(
        model_name="scorecard"
    )

    assert prefix == "models/scorecard/"


def test_model_prefix_validates_model_id() -> None:
    """测试构造模型前缀前校验模型 ID."""
    strategy = StorageKeyStrategy(
        model_dir="models"
    )

    with pytest.raises(
        ValueError,
        match="非法的模型名称",
    ):
        strategy.model_prefix(
            model_name="model/id"
        )


@pytest.mark.parametrize(
    (
        "key",
        "expected_filename",
    ),
    [
        (
            "models/mdl_0123456789abcdef/1.0.0/model.pkl",
            "model.pkl",
        ),
        (
            r"models\mdl_0123456789abcdef\1.0.0\model.pkl",
            "model.pkl",
        ),
        (
            "model.pkl",
            "model.pkl",
        ),
    ],
)
def test_extract_filename_returns_last_component(
    key: str,
    expected_filename: str,
) -> None:
    """测试从不同格式存储键提取文件名."""
    filename = StorageKeyStrategy.extract_filename(
        key
    )

    assert filename == expected_filename


@pytest.mark.parametrize(
    "key",
    [
        "",
        "models/",
        r"models\\",
        "models/model\x00.pkl",
        None,
        123,
    ],
)
def test_extract_filename_rejects_invalid_key(
    key: Any,
) -> None:
    """测试拒绝无法提取有效文件名的存储键."""
    with pytest.raises(
        ValueError,
    ):
        StorageKeyStrategy.extract_filename(
            key
        )
