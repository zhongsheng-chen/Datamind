# 使用方式

## 当前能力

### ✔ 注册模型

```bash
python -m datamind.cli.main model register
```

---

## ✔ 扩展后（未来理想）

你可以演进成：

```bash
datamind model register \
  --name scorecard \
  --version 4.1.10 \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --model-path datamind/demo/scorecard.pkl
```

> 👉 这个下一步可以升级参数系统（`Click` / `Typer`）

---

# 🚀 下一步升级建议（很关键）

你现在这个 CLI 是：

✅ **MVP 版 CLI（结构正确）**

下一步建议按下面方向升级：

---

## 🔥 1. 改用 `Typer`（强烈推荐）

```python
import typer
```

### 优点

- 自动生成 `help`
- 自动类型校验
- 命令定义更干净
- 更接近 :contentReference[oaicite:0]{index=0} 风格

---

## 🔥 2. 参数绑定成 `dataclass`

```python
@dataclass
class RegisterModelRequest:
    ...
```

### 好处

- CLI 参数对象化
- 参数传递更清晰
- 更容易做参数校验
- 后续 API / CLI 可以复用同一套 DTO

---

## 🔥 3. CLI → Service 解耦

推荐架构：

```text
CLI
 ↓
ModelService
 ↓
ModelRegister
```

而不是：

```text
CLI
 ↓
直接调用 register()
```

### 好处

- CLI 只负责参数解析
- Service 负责业务编排
- Register 负责模型注册实现
- 后续接入 API、Web UI、Workflow 更自然

---

这样 `Datamind` 后面就会越来越像：

- :contentReference[oaicite:1]{index=1}
- :contentReference[oaicite:2]{index=2}
- :contentReference[oaicite:3]{index=3}

从“工具脚本”逐步演进成“平台入口”。