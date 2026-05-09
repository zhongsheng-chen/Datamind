# 使用方式

## 安装依赖

```bash
pip install typer
```

## CLI 运行

### 注册模型
```bash
python -m datamind.cli.main model register \
  --name scorecard \
  --version 4.1.10 \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --model-path datamind/demo/scorecard.pkl \
  --description "信用评分卡模型" \
  --created-by admin \
  --force
```

### 列出模型
```bash
python -m datamind.cli.main model list \
  --framework sklearn \
  --model-type logistic_regression
```


## 下一步你可以自然扩展成

```bash
datamind model register
datamind model list
datamind model delete

datamind version list
datamind version rollback

datamind deploy create
datamind deploy stop
```

这时候 `Datamind` 就开始像：

- `MLflow`
- `Docker`
- `kubectl`

这种“平台入口”了。

而且你现在的分层，其实已经很接近这个方向。