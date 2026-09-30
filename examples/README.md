# 示例开发

完整脚本索引、银行场景模型和制品命名见 [ReadTheDocs 示例](https://datamind.readthedocs.io/en/latest/examples/)，注册与预测见 [评分卡与分类模型](../docs/guides/models.md)。请克隆仓库后从项目根目录运行；PyPI 安装包不包含这些示例脚本。

本目录训练脚本使用可复现的合成数据，仅生成本地制品，注册、激活和部署由调用方显式执行。artifacts/ 不纳入版本管理。

scorecard/ 训练 optbinning.Scorecard；classification/ 包括 sklearn、XGBoost、LightGBM、CatBoost 与 credit_risk 信贷特征示例。按脚本选择对应 extra，全部框架可安装 `.[full]`。查看参数：

```bash
python examples/scorecard/train.py --help
python examples/classification/credit_risk/train.py --help
```

新增示例保留随机种子、数据生成、训练/验证、制品保存与命令行入口；检查保存后的特征名称和模型格式，并更新正式示例索引。业务显示名称仅作服务管理演示，不代表脚本训练了真实业务标签。
