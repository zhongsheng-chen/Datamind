# datamind/core/scoring/adapters/torch.py

"""PyTorch 模型适配器

支持 PyTorch 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集

特性：
  - 自动模式切换：推理时自动设置为 eval 模式
  - 梯度禁用：使用 torch.no_grad() 禁用梯度计算
  - 设备自动检测：自动将输入数据移动到模型所在设备
  - 多输出支持：支持二分类（softmax）和回归（sigmoid/直接输出）
  - 批量预测优化：重写 predict_proba_batch 支持批量张量计算
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class TorchAdapter(BaseModelAdapter):
    """PyTorch 模型适配器"""

    SUPPORTED_CAPABILITIES: ScorecardCapability = (
        ScorecardCapability.PREDICT_CLASS |
        ScorecardCapability.BATCH_PREDICT |
        ScorecardCapability.SHAP_KERNEL
    )

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        transformer: Optional[Any] = None
    ):
        """
        初始化适配器

        参数:
            model: PyTorch 模型（nn.Module 实例）
            feature_names: 特征名称列表（可选）
            transformer: WOE转换器（评分卡模型使用）
        """
        super().__init__(model, feature_names, transformer=transformer)

        self.device = next(model.parameters()).device
        self.model.eval()

        self._capabilities = self.SUPPORTED_CAPABILITIES

        logger.debug("PyTorch 适配器初始化完成，模型设备: %s", self.device)

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        返回:
            ScorecardCapability 位掩码
        """
        return self._capabilities

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            X_tensor = torch.from_numpy(X).float().to(self.device)

            with torch.no_grad():
                output = self.model(X_tensor)

                if output.shape[-1] == 2:
                    proba = torch.softmax(output, dim=1)[0, 1].item()
                else:
                    proba = torch.sigmoid(output).item() if output.numel() == 1 else output.item()

            return float(proba)

        except Exception as e:
            logger.error("PyTorch 单条预测失败: %s", e)
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        try:
            X_tensor = torch.from_numpy(X).float().to(self.device)

            with torch.no_grad():
                output = self.model(X_tensor)

                if output.shape[-1] == 2:
                    probs = torch.softmax(output, dim=1)[:, 1].cpu().numpy()
                else:
                    probs = torch.sigmoid(output).cpu().numpy().flatten()

            return probs.tolist()

        except Exception as e:
            logger.error("PyTorch 批量预测失败: %s", e)
            raise

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        PyTorch 模型通常不直接提供特征重要性。

        返回:
            空字典
        """
        return {}