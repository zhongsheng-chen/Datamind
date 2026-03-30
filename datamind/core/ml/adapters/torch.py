# datamind/core/ml/common/adapters/torch.py

"""PyTorch 模型适配器

支持 PyTorch 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性

特性：
  - 自动模式切换：推理时自动设置为 eval 模式
  - 梯度禁用：使用 torch.no_grad() 禁用梯度计算，提升性能
  - 设备自动检测：自动将输入数据移动到模型所在设备（CPU/GPU）
  - 多输出支持：支持二分类（softmax）和回归（sigmoid/直接输出）
  - 批量预测优化：重写 predict_proba_batch 支持批量张量计算
  - 错误处理：完善的异常捕获和调试信息

继承的方法（由基类提供）：
  - predict: 统一的预测接口，支持多种输入格式
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
"""

import numpy as np
import torch
from typing import Dict, List, Optional

from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.logging.debug import debug_print


class TorchAdapter(BaseModelAdapter):
    """PyTorch 模型适配器"""

    def __init__(self, model, feature_names: Optional[List[str]] = None):
        """
        初始化适配器

        参数:
            model: PyTorch 模型（nn.Module 实例）
            feature_names: 特征名称列表（可选）
        """
        super().__init__(model, feature_names)

        # 获取模型设备
        self.device = next(model.parameters()).device

        # 设置为推理模式
        self.model.eval()

        debug_print("TorchAdapter", f"模型设备: {self.device}")

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            # 转换为张量并移动到模型设备
            X_tensor = torch.from_numpy(X).float().to(self.device)

            # 禁用梯度计算
            with torch.no_grad():
                output = self.model(X_tensor)

                # 处理输出
                if output.shape[-1] == 2:
                    # 二分类，使用 softmax
                    proba = torch.softmax(output, dim=1)[0, 1].item()
                else:
                    # 回归或单输出，使用 sigmoid
                    proba = torch.sigmoid(output).item() if output.numel() == 1 else output.item()

            return float(proba)

        except Exception as e:
            debug_print("TorchAdapter", f"预测失败: {e}")
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（重写基类方法以优化性能）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        try:
            # 转换为张量并移动到模型设备
            X_tensor = torch.from_numpy(X).float().to(self.device)

            # 禁用梯度计算
            with torch.no_grad():
                output = self.model(X_tensor)

                # 处理输出
                if output.shape[-1] == 2:
                    # 二分类，使用 softmax
                    probs = torch.softmax(output, dim=1)[:, 1].cpu().numpy()
                else:
                    # 回归或单输出，使用 sigmoid
                    probs = torch.sigmoid(output).cpu().numpy().flatten()

            return probs.tolist()

        except Exception as e:
            debug_print("TorchAdapter", f"批量预测失败: {e}")
            raise

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        PyTorch 模型通常不直接提供特征重要性，
        子类可重写此方法实现自定义的重要性提取逻辑。

        返回:
            空字典（PyTorch 模型不直接支持特征重要性）
        """
        return {}