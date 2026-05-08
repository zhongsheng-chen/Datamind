"""模型产物加载示例"""

import numpy as np
from pathlib import Path

from datamind.models.artifact import ModelArtifactLoader


def main():
    # 模型文件
    model_path = "datamind/demo/scorecard.pkl"

    # 读取模型文件
    data = Path(model_path).read_bytes()

    # 反序列化
    model = ModelArtifactLoader.load(
        framework="sklearn",
        data=data,
    )

    print("加载成功")
    print("模型类型:", type(model))

    # 构造测试样本
    samples = np.array([
        [0.1, 0.3, 0.8, 0.2, 0.5],
        [0.9, 0.7, 0.1, 0.4, 0.2],
    ])

    # 预测
    result = model.predict(samples)

    print("预测结果:", result)

    # 概率（更适合评分卡）
    proba = model.predict_proba(samples)

    print("预测概率:")
    print(proba)


if __name__ == "__main__":
    main()