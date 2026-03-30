# datamind/config/scorecard_config.py
"""评分卡配置模块

定义评分卡模型的所有配置项，支持动态分箱调整和配置版本管理。

核心功能：
  - 评分卡参数配置（基准分/翻倍比/基准odds）
  - 特征分箱配置（等频/等宽/自定义/单调/决策树）
  - WOE值配置和验证
  - IV值计算和验证
  - 配置版本管理
  - 配置热加载支持
  - 配置生效时间控制
  - 多环境隔离（开发/测试/生产）

配置来源：
  支持从环境变量读取配置，例如：
    - `SCORECARD_BASE_SCORE=600`
    - `SCORECARD_PDO=50`
    - `SCORECARD_ODDS=20`
    - `SCORECARD_MIN_SCORE=0`
    - `SCORECARD_MAX_SCORE=1000`
    - `SCORECARD_DEFAULT_N_BINS=10`
    - `SCORECARD_DEFAULT_MIN_SAMPLES=5`

配置验证：
  提供完善的配置验证，包括：
    - 类型验证（枚举、整数、浮点数、字符串）
    - 范围验证（评分 `0-1000`、`pdo>0`、`odds>0`）
    - 一致性验证（分箱边界递增、WOE数量匹配）
    - 完整性验证（特征系数与分箱配置对应）
    - 依赖验证（有效时间区间、生产配置标识）

枚举类型：
  - `BinningStrategy`: 分箱策略（quantile/uniform/custom/monotonic/tree）
  - `ScoreDirection`: 评分方向（higher_better/lower_better）
  - `ConfigState`: 配置状态（draft/active/deprecated/archived）

使用示例：
  >>> from datamind.config import get_scorecard_default_config
  >>> config = get_scorecard_default_config()
  >>> print(config.base_score)
  600
"""

import json
import hashlib
import threading
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScorecardConstants:
    """评分卡常量定义"""
    # 评分参数默认值
    DEFAULT_BASE_SCORE: float = 600
    DEFAULT_PDO: float = 50
    DEFAULT_ODDS: float = 20
    DEFAULT_MIN_SCORE: float = 0
    DEFAULT_MAX_SCORE: float = 1000

    # 分箱参数默认值
    DEFAULT_N_BINS: int = 10
    DEFAULT_MIN_SAMPLES_PER_BIN: int = 5
    DEFAULT_STRATEGY: str = "quantile"

    # 配置参数默认值
    DEFAULT_VERSION: str = "1.0.0"
    DEFAULT_DIRECTION: str = "higher_better"

    # 缓存参数默认值
    DEFAULT_ENABLE_CACHE: bool = True
    DEFAULT_CACHE_TTL: int = 300

    # 评分范围
    MIN_SCORE_LIMIT: float = 0
    MAX_SCORE_LIMIT: float = 1000

    # 分箱范围
    MIN_N_BINS: int = 2
    MAX_N_BINS: int = 50
    MIN_SAMPLES_PER_BIN: int = 1


class BinningStrategy(str, Enum):
    """分箱策略枚举

    定义特征分箱的算法类型。

    属性:
        QUANTILE: 等频分箱 - 基于分位数，每箱样本量大致相等
        UNIFORM: 等宽分箱 - 基于值域，每箱区间宽度相等
        CUSTOM: 自定义分箱 - 用户手动指定分箱边界
        MONOTONIC: 单调分箱 - 确保WOE值单调递增或递减
        TREE: 决策树分箱 - 基于决策树最优分割点
    """
    QUANTILE = "quantile"
    UNIFORM = "uniform"
    CUSTOM = "custom"
    MONOTONIC = "monotonic"
    TREE = "tree"


class ScoreDirection(str, Enum):
    """评分方向枚举

    定义评分与风险的关系方向。

    属性:
        HIGHER_BETTER: 分数越高越好（风险越低）
        LOWER_BETTER: 分数越低越好（风险越低）
    """
    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"


class ConfigState(str, Enum):
    """配置状态枚举

    定义评分卡配置的生命周期状态。

    状态流转：
        DRAFT → ACTIVE → DEPRECATED → ARCHIVED

    属性:
        DRAFT: 草稿状态 - 配置正在编辑中，不可用于生产
        ACTIVE: 活跃状态 - 配置已生效，可用于生产推理
        DEPRECATED: 已弃用状态 - 配置不再推荐使用，但保留兼容
        ARCHIVED: 已归档状态 - 配置已废弃，仅用于历史查询
    """
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ScorecardDefaultConfig(BaseSettings):
    """评分卡默认配置

    从环境变量读取评分卡的默认参数配置。

    配置示例：
        SCORECARD_BASE_SCORE=600
        SCORECARD_PDO=50
        SCORECARD_ODDS=20
        SCORECARD_MIN_SCORE=0
        SCORECARD_MAX_SCORE=1000
        SCORECARD_DIRECTION=higher_better
        SCORECARD_DEFAULT_N_BINS=10
        SCORECARD_DEFAULT_MIN_SAMPLES=5
        SCORECARD_DEFAULT_STRATEGY=quantile
        SCORECARD_ENABLE_CACHE=true
        SCORECARD_CACHE_TTL=300

    属性:
        base_score: 基准分，默认 `600`
        pdo: 点数翻倍比（Points to Double the Odds），默认 `50`
        odds: 基准 odds，默认 `20`
        min_score: 最低分，默认 `0`
        max_score: 最高分，默认 `1000`
        direction: 评分方向，默认 `higher_better`
        default_n_bins: 默认分箱数量，默认 `10`
        default_min_samples_per_bin: 每箱默认最小样本数，默认 `5`
        default_strategy: 默认分箱策略，默认 `quantile`
        enable_cache: 是否启用配置缓存，默认 `True`
        cache_ttl: 缓存过期时间（秒），默认 `300`
        default_version: 默认版本，默认 `1.0.0`
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="SCORECARD_"
    )

    base_score: float = Field(
        default=ScorecardConstants.DEFAULT_BASE_SCORE,
        ge=ScorecardConstants.MIN_SCORE_LIMIT,
        le=ScorecardConstants.MAX_SCORE_LIMIT,
        validation_alias="SCORECARD_BASE_SCORE",
        description="基准分"
    )

    pdo: float = Field(
        default=ScorecardConstants.DEFAULT_PDO,
        gt=0,
        validation_alias="SCORECARD_PDO",
        description="点数翻倍比（Points to Double the Odds）"
    )

    odds: float = Field(
        default=ScorecardConstants.DEFAULT_ODDS,
        gt=0,
        validation_alias="SCORECARD_ODDS",
        description="基准 odds"
    )

    min_score: float = Field(
        default=ScorecardConstants.DEFAULT_MIN_SCORE,
        ge=0,
        validation_alias="SCORECARD_MIN_SCORE",
        description="最低分"
    )

    max_score: float = Field(
        default=ScorecardConstants.DEFAULT_MAX_SCORE,
        le=ScorecardConstants.MAX_SCORE_LIMIT,
        validation_alias="SCORECARD_MAX_SCORE",
        description="最高分"
    )

    direction: str = Field(
        default=ScorecardConstants.DEFAULT_DIRECTION,
        validation_alias="SCORECARD_DIRECTION",
        description="评分方向：`higher_better` 或 `lower_better`"
    )

    default_n_bins: int = Field(
        default=ScorecardConstants.DEFAULT_N_BINS,
        ge=ScorecardConstants.MIN_N_BINS,
        le=ScorecardConstants.MAX_N_BINS,
        validation_alias="SCORECARD_DEFAULT_N_BINS",
        description="默认分箱数量"
    )

    default_min_samples_per_bin: int = Field(
        default=ScorecardConstants.DEFAULT_MIN_SAMPLES_PER_BIN,
        ge=ScorecardConstants.MIN_SAMPLES_PER_BIN,
        validation_alias="SCORECARD_DEFAULT_MIN_SAMPLES",
        description="每箱默认最小样本数"
    )

    default_strategy: str = Field(
        default=ScorecardConstants.DEFAULT_STRATEGY,
        validation_alias="SCORECARD_DEFAULT_STRATEGY",
        description="默认分箱策略：`quantile`/`uniform`/`custom`/`monotonic`/`tree`"
    )

    enable_cache: bool = Field(
        default=ScorecardConstants.DEFAULT_ENABLE_CACHE,
        validation_alias="SCORECARD_ENABLE_CACHE",
        description="是否启用配置缓存"
    )

    cache_ttl: int = Field(
        default=ScorecardConstants.DEFAULT_CACHE_TTL,
        ge=60,
        validation_alias="SCORECARD_CACHE_TTL",
        description="缓存过期时间（秒）"
    )

    default_version: str = Field(
        default=ScorecardConstants.DEFAULT_VERSION,
        pattern=r"^\d+\.\d+\.\d+$",
        validation_alias="SCORECARD_DEFAULT_VERSION",
        description="默认配置版本，格式：`major.minor.patch`"
    )

    @field_validator('direction', mode='before')
    @classmethod
    def _validate_direction(cls, v: str) -> str:
        """验证评分方向"""
        if isinstance(v, str):
            if v not in ['higher_better', 'lower_better']:
                return ScorecardConstants.DEFAULT_DIRECTION
        return v

    @field_validator('default_strategy', mode='before')
    @classmethod
    def _validate_strategy(cls, v: str) -> str:
        """验证分箱策略"""
        valid_strategies = ['quantile', 'uniform', 'custom', 'monotonic', 'tree']
        if v not in valid_strategies:
            return ScorecardConstants.DEFAULT_STRATEGY
        return v


class FeatureBinConfig(BaseModel):
    """特征分箱配置模型

    定义单个特征的分箱规则和WOE值。

    核心功能：
      - 定义分箱边界（`bin_edges`）
      - 定义WOE值（`woe_values`）
      - 计算信息值（`iv`）
      - 处理缺失值（`missing_bin`）
      - 支持多种分箱策略（`strategy`）

    验证规则：
      - 分箱边界必须严格递增
      - WOE值数量必须比分箱数量少1
      - IV值必须大于等于0
      - 缺失值分箱必须在 `bin_edges` 中存在

    属性:
        name: 特征名称，唯一标识
        strategy: 分箱策略，决定分箱算法
        bin_edges: 分箱边界列表，长度为 `n_bins + 1`
        woe_values: WOE值列表，长度为 `n_bins`
        iv: 信息值，衡量特征预测能力
        missing_bin: 缺失值分箱标识，`None` 表示缺失值单独处理
        n_bins: 分箱数量，默认 `10`，范围 `2-50`
        min_samples_per_bin: 每箱最小样本数，默认 `5`
        monotonic_cst: 单调约束（`None`/`1`/`-1`），`1` 为递增，`-1` 为递减
        custom_breaks: 自定义分箱边界（`strategy=CUSTOM` 时使用）
    """

    name: str = Field(
        default="",
        min_length=1,
        max_length=100,
        description="特征名称"
    )

    strategy: BinningStrategy = Field(
        default=BinningStrategy.QUANTILE,
        description="分箱策略"
    )

    bin_edges: List[Union[float, int, str]] = Field(
        default_factory=list,
        description="分箱边界列表，长度为 `n_bins + 1`"
    )

    woe_values: List[float] = Field(
        default_factory=list,
        description="WOE值列表，长度为 `n_bins`"
    )

    iv: float = Field(
        default=0.0,
        ge=0.0,
        description="信息值（Information Value）"
    )

    missing_bin: Optional[str] = Field(
        default=None,
        description="缺失值分箱标识，`None` 表示缺失值单独处理"
    )

    n_bins: int = Field(
        default=ScorecardConstants.DEFAULT_N_BINS,
        ge=ScorecardConstants.MIN_N_BINS,
        le=ScorecardConstants.MAX_N_BINS,
        description="分箱数量"
    )

    min_samples_per_bin: int = Field(
        default=ScorecardConstants.DEFAULT_MIN_SAMPLES_PER_BIN,
        ge=ScorecardConstants.MIN_SAMPLES_PER_BIN,
        description="每箱最小样本数"
    )

    monotonic_cst: Optional[int] = Field(
        default=None,
        ge=-1,
        le=1,
        description="单调约束：`1`=递增，`-1`=递减，`None`=无约束"
    )

    custom_breaks: Optional[List[float]] = Field(
        default=None,
        description="自定义分箱边界（`strategy=CUSTOM` 时使用）"
    )

    @field_validator('woe_values')
    @classmethod
    def _validate_woe_count(cls, woe_values: List[float], info) -> List[float]:
        """验证WOE值数量与分箱数量匹配"""
        bin_edges = info.data.get('bin_edges', [])
        if bin_edges and len(woe_values) != len(bin_edges) - 1:
            raise ValueError(
                f"WOE值数量({len(woe_values)})必须比分箱数({len(bin_edges) - 1})相等"
            )
        return woe_values

    @field_validator('bin_edges')
    @classmethod
    def _validate_bin_edges(cls, bin_edges: List[Union[float, int, str]]) -> List[Union[float, int, str]]:
        """验证分箱边界严格递增"""
        if not bin_edges:
            return bin_edges

        numeric_edges = [e for e in bin_edges if isinstance(e, (int, float))]
        if len(numeric_edges) > 1:
            for i in range(len(numeric_edges) - 1):
                if numeric_edges[i] >= numeric_edges[i + 1]:
                    raise ValueError(
                        f"分箱边界必须严格递增: {numeric_edges[i]} >= {numeric_edges[i + 1]}"
                    )
        return bin_edges

    @field_validator('monotonic_cst')
    @classmethod
    def _validate_monotonic_constraint(cls, monotonic_cst: Optional[int]) -> Optional[int]:
        """验证单调约束值"""
        if monotonic_cst is not None and monotonic_cst not in (-1, 1):
            raise ValueError(f"单调约束必须为 `-1`（递减）、`1`（递增）或 `None`")
        return monotonic_cst

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        返回:
            字典格式的配置，用于序列化存储
        """
        result = {
            'name': self.name,
            'strategy': self.strategy.value,
            'bin_edges': self.bin_edges,
            'woe_values': self.woe_values,
            'iv': self.iv,
            'missing_bin': self.missing_bin,
            'n_bins': self.n_bins,
            'min_samples_per_bin': self.min_samples_per_bin,
            'monotonic_cst': self.monotonic_cst,
            'custom_breaks': self.custom_breaks
        }
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any], feature_name: Optional[str] = None) -> 'FeatureBinConfig':
        """从字典创建实例

        参数:
            data: 字典格式的配置数据
            feature_name: 特征名称，如果提供则覆盖 `data` 中的 `name`

        返回:
            `FeatureBinConfig` 实例
        """
        name = feature_name or data.get('name', '')
        if not name:
            raise ValueError("特征名称不能为空")

        return cls(
            name=name,
            strategy=BinningStrategy(data.get('strategy', ScorecardConstants.DEFAULT_STRATEGY)),
            bin_edges=data.get('bin_edges', []),
            woe_values=data.get('woe_values', []),
            iv=data.get('iv', 0.0),
            missing_bin=data.get('missing_bin'),
            n_bins=data.get('n_bins', ScorecardConstants.DEFAULT_N_BINS),
            min_samples_per_bin=data.get('min_samples_per_bin', ScorecardConstants.DEFAULT_MIN_SAMPLES_PER_BIN),
            monotonic_cst=data.get('monotonic_cst'),
            custom_breaks=data.get('custom_breaks')
        )


class ScorecardConfig(BaseModel):
    """评分卡完整配置模型

    定义评分卡的所有配置参数，包括评分参数、特征分箱、模型系数等。

    核心功能：
      - 评分参数配置（`base_score`/`pdo`/`odds`）
      - 特征分箱配置管理
      - 模型系数管理
      - 配置版本控制
      - 配置状态管理
      - 生效时间控制

    验证规则：
      - `base_score` 必须在 `0-1000` 之间
      - `pdo` 必须大于 `0`
      - `odds` 必须大于 `0`
      - `min_score` 必须小于 `max_score`
      - 特征系数必须与分箱配置对应

    属性:
        base_score: 基准分，默认 `600`
        pdo: 点数翻倍比（Points to Double the Odds），默认 `50`
        odds: 基准 odds，默认 `20`
        min_score: 最低分，默认 `0`
        max_score: 最高分，默认 `1000`
        direction: 评分方向，默认 `higher_better`
        feature_bins: 特征分箱配置字典
        coefficients: 特征系数字典
        intercept: 截距项
        feature_importance: 特征重要性字典
        version: 配置版本
        config_id: 配置唯一标识
        state: 配置状态
        created_by: 创建人
        created_at: 创建时间
        updated_by: 更新人
        updated_at: 更新时间
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        description: 配置描述
        tags: 标签字典
    """

    base_score: float = Field(
        default=ScorecardConstants.DEFAULT_BASE_SCORE,
        ge=ScorecardConstants.MIN_SCORE_LIMIT,
        le=ScorecardConstants.MAX_SCORE_LIMIT,
        description="基准分"
    )

    pdo: float = Field(
        default=ScorecardConstants.DEFAULT_PDO,
        gt=0,
        description="点数翻倍比（Points to Double the Odds）"
    )

    odds: float = Field(
        default=ScorecardConstants.DEFAULT_ODDS,
        gt=0,
        description="基准 odds"
    )

    min_score: float = Field(
        default=ScorecardConstants.DEFAULT_MIN_SCORE,
        ge=ScorecardConstants.MIN_SCORE_LIMIT,
        description="最低分"
    )

    max_score: float = Field(
        default=ScorecardConstants.DEFAULT_MAX_SCORE,
        le=ScorecardConstants.MAX_SCORE_LIMIT,
        description="最高分"
    )

    direction: ScoreDirection = Field(
        default=ScoreDirection.HIGHER_BETTER,
        description="评分方向"
    )

    feature_bins: Dict[str, FeatureBinConfig] = Field(
        default_factory=dict,
        description="特征分箱配置字典"
    )

    coefficients: Dict[str, float] = Field(
        default_factory=dict,
        description="特征系数字典"
    )

    intercept: float = Field(
        default=0.0,
        description="截距项"
    )

    feature_importance: Dict[str, float] = Field(
        default_factory=dict,
        description="特征重要性字典"
    )

    version: str = Field(
        default=ScorecardConstants.DEFAULT_VERSION,
        pattern=r"^\d+\.\d+\.\d+$",
        description="配置版本，格式：`major.minor.patch`"
    )

    config_id: str = Field(
        default="",
        description="配置唯一标识"
    )

    state: ConfigState = Field(
        default=ConfigState.DRAFT,
        description="配置状态"
    )

    created_by: str = Field(
        default="system",
        max_length=50,
        description="创建人"
    )

    created_at: Optional[datetime] = Field(
        default=None,
        description="创建时间"
    )

    updated_by: str = Field(
        default="system",
        max_length=50,
        description="更新人"
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        description="更新时间"
    )

    effective_from: Optional[datetime] = Field(
        default=None,
        description="生效开始时间"
    )

    effective_to: Optional[datetime] = Field(
        default=None,
        description="生效结束时间"
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="配置描述"
    )

    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="标签字典"
    )

    @field_validator('min_score', 'max_score')
    @classmethod
    def _validate_score_range(cls, v: float, info) -> float:
        """验证评分范围"""
        if 'min_score' in info.data and 'max_score' in info.data:
            if info.data['min_score'] >= info.data['max_score']:
                raise ValueError(
                    f"`min_score`({info.data['min_score']})必须小于`max_score`({info.data['max_score']})"
                )
        return v

    @field_validator('coefficients')
    @classmethod
    def _validate_coefficients(cls, coefficients: Dict[str, float], info) -> Dict[str, float]:
        """验证系数与特征分箱匹配"""
        feature_bins = info.data.get('feature_bins', {})
        missing_features = set(coefficients.keys()) - set(feature_bins.keys())
        if missing_features:
            raise ValueError(
                f"系数中的特征在分箱配置中不存在: {missing_features}"
            )
        return coefficients

    @model_validator(mode='after')
    def _generate_config_id(self) -> 'ScorecardConfig':
        """生成配置唯一标识"""
        if not self.config_id:
            config_str = json.dumps(self.to_dict(), sort_keys=True, default=str)
            self.config_id = hashlib.sha256(config_str.encode()).hexdigest()[:16]
        return self

    def get_score_params(self) -> Dict[str, float]:
        """获取评分参数

        计算评分公式中的 `factor` 和 `offset`。

        评分公式：
            score = offset + factor * (intercept + Σ(coefficient_i * WOE_i))

        其中：
            factor = pdo / ln(2)
            offset = base_score - factor * ln(odds)

        返回:
            包含 `factor` 和 `offset` 的字典
        """
        import numpy as np

        factor = self.pdo / np.log(2)
        offset = self.base_score - factor * np.log(self.odds)

        return {
            'factor': factor,
            'offset': offset,
            'base_score': self.base_score,
            'pdo': self.pdo,
            'odds': self.odds
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        返回:
            字典格式的配置，用于序列化存储
        """
        result = {
            'base_score': self.base_score,
            'pdo': self.pdo,
            'odds': self.odds,
            'min_score': self.min_score,
            'max_score': self.max_score,
            'direction': self.direction.value,
            'feature_bins': {
                name: bin_config.to_dict()
                for name, bin_config in self.feature_bins.items()
            },
            'coefficients': self.coefficients,
            'intercept': self.intercept,
            'feature_importance': self.feature_importance,
            'version': self.version,
            'config_id': self.config_id,
            'state': self.state.value,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'description': self.description,
            'tags': self.tags
        }
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScorecardConfig':
        """从字典创建实例

        参数:
            data: 字典格式的配置数据

        返回:
            `ScorecardConfig` 实例
        """
        feature_bins = {}
        for name, bin_data in data.get('feature_bins', {}).items():
            feature_bins[name] = FeatureBinConfig.from_dict(bin_data, feature_name=name)

        created_at = data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get('updated_at')
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        effective_from = data.get('effective_from')
        if effective_from and isinstance(effective_from, str):
            effective_from = datetime.fromisoformat(effective_from)

        effective_to = data.get('effective_to')
        if effective_to and isinstance(effective_to, str):
            effective_to = datetime.fromisoformat(effective_to)

        return cls(
            base_score=data.get('base_score', ScorecardConstants.DEFAULT_BASE_SCORE),
            pdo=data.get('pdo', ScorecardConstants.DEFAULT_PDO),
            odds=data.get('odds', ScorecardConstants.DEFAULT_ODDS),
            min_score=data.get('min_score', ScorecardConstants.DEFAULT_MIN_SCORE),
            max_score=data.get('max_score', ScorecardConstants.DEFAULT_MAX_SCORE),
            direction=ScoreDirection(data.get('direction', ScorecardConstants.DEFAULT_DIRECTION)),
            feature_bins=feature_bins,
            coefficients=data.get('coefficients', {}),
            intercept=data.get('intercept', 0.0),
            feature_importance=data.get('feature_importance', {}),
            version=data.get('version', ScorecardConstants.DEFAULT_VERSION),
            config_id=data.get('config_id', ''),
            state=ConfigState(data.get('state', ConfigState.DRAFT.value)),
            created_by=data.get('created_by', 'system'),
            created_at=created_at,
            updated_by=data.get('updated_by', 'system'),
            updated_at=updated_at,
            effective_from=effective_from,
            effective_to=effective_to,
            description=data.get('description'),
            tags=data.get('tags', {})
        )

    def validate(self) -> List[str]:
        """验证配置有效性

        返回:
            错误列表，空列表表示验证通过
        """
        errors = []

        if self.base_score < ScorecardConstants.MIN_SCORE_LIMIT or self.base_score > ScorecardConstants.MAX_SCORE_LIMIT:
            errors.append(
                f"`base_score`({self.base_score})必须在{ScorecardConstants.MIN_SCORE_LIMIT}-{ScorecardConstants.MAX_SCORE_LIMIT}之间")

        if self.pdo <= 0:
            errors.append(f"`pdo`({self.pdo})必须大于0")

        if self.odds <= 0:
            errors.append(f"`odds`({self.odds})必须大于0")

        if self.min_score >= self.max_score:
            errors.append(
                f"`min_score`({self.min_score})必须小于`max_score`({self.max_score})"
            )

        for name, bin_config in self.feature_bins.items():
            if len(bin_config.bin_edges) != len(bin_config.woe_values) + 1:
                errors.append(
                    f"特征 `{name}`: 分箱数({len(bin_config.bin_edges) - 1})与WOE值数({len(bin_config.woe_values)})不匹配"
                )

        for feature_name in self.coefficients.keys():
            if feature_name not in self.feature_bins:
                errors.append(f"系数中的特征 `{feature_name}` 没有对应的分箱配置")

        return errors

    def is_effective(self, check_time: Optional[datetime] = None) -> bool:
        """检查配置是否在有效期内

        参数:
            check_time: 检查时间点，`None` 表示当前时间

        返回:
            `True` 表示在有效期内，`False` 表示已过期或尚未生效
        """
        if self.state != ConfigState.ACTIVE:
            return False

        now = check_time or datetime.now()

        if self.effective_from and now < self.effective_from:
            return False

        if self.effective_to and now > self.effective_to:
            return False

        return True

_scorecard_default_config: Optional[ScorecardDefaultConfig] = None
_config_lock = threading.Lock()


def get_scorecard_default_config() -> ScorecardDefaultConfig:
    """获取评分卡默认配置实例

    从 `.env` 文件和环境变量加载配置，支持热重载。

    返回:
        `ScorecardDefaultConfig` 单例实例

    示例:
        >>> config = get_scorecard_default_config()
        >>> print(config.base_score)
        600
    """
    global _scorecard_default_config
    if _scorecard_default_config is None:
        with _config_lock:
            if _scorecard_default_config is None:
                _scorecard_default_config = ScorecardDefaultConfig()
    return _scorecard_default_config


def reload_scorecard_default_config() -> ScorecardDefaultConfig:
    """重新加载评分卡默认配置

    用于配置文件热重载场景。

    返回:
        新加载的 `ScorecardDefaultConfig` 实例
    """
    global _scorecard_default_config
    with _config_lock:
        _scorecard_default_config = ScorecardDefaultConfig()
    return _scorecard_default_config


__all__ = [
    'ScorecardConstants',
    'BinningStrategy',
    'ScoreDirection',
    'ConfigState',
    'FeatureBinConfig',
    'ScorecardConfig',
    'ScorecardDefaultConfig',
    'get_scorecard_default_config',
    'reload_scorecard_default_config'
]