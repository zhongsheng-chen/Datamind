# 安装

Datamind 支持 Python `>=3.12,<3.15`，建议使用 Python 3.12。

## 使用 pip 安装

根据所用模型框架，安装相应的可选依赖：

### scikit-learn

```bash
python -m pip install "pydatamind[sklearn]"
```

### XGBoost

```bash
python -m pip install "pydatamind[xgboost]"
```

### LightGBM

```bash
python -m pip install "pydatamind[lightgbm]"
```

### CatBoost

```bash
python -m pip install "pydatamind[catboost]"
```

### 完整安装

安装所有支持的模型框架及相关依赖。

```bash
python -m pip install "pydatamind[full]"
```

## 验证安装

```bash
datamind --version
```

## 从源码安装

克隆仓库并进入项目目录：

```bash
git clone https://github.com/zhongsheng-chen/Datamind.git
cd Datamind
```

以可编辑模式安装，同时安装 scikit-learn 所需依赖：

```bash
python -m pip install -e ".[sklearn]"
```

如需从源码运行管理控制台，请先安装 [Node.js 24](https://nodejs.org/)，再构建前端资源：

```bash
npm ci
npm run build:console
```

安装完成后，继续阅读[配置与初始化](configuration.md)。
