## 功能目标

建立一个规则 + 模型的一体化零售贷款决策服务，以 BentoML + PostgreSQL 为核心，规则用 YAML 配置，模型支持 多算法、多版本、多格式。

- 服务逻辑：

    - 规则引擎（初筛规则） → 如果触发，直接拒绝并返回 拒绝码（写入数据库）

    - 模型预测 → 支持多种模型（违约概率模型、反欺诈模型…），给出结果

    - 结果存储 → 模型输入、输出、规则触发原因写入数据库，便于审计和效果评估

## 特性

- 多格式支持：pickle、joblib、ONNX、JSON 等常用格式。

- 自动依赖管理：BentoML 会记录模型依赖（如 sklearn 版本）。

- 多版本管理：同一个模型名称可保存多个版本，方便热更新。

- 统一接口：不同框架模型都可以通过 Runner 或 API 暴露服务。
- 特征对齐（Feature Mapping & Validation）

## 模型与规则

- 规则引擎：

  采用 YAML + Python 实现，规则可配置。规则触发要有码值（拒绝原因码），同时写库

- 模型支持：

    - 算法类型：LR、NNs、Decision Tree、XGBoost

    - 文件格式：支持 ONNX、PKL 
    - 多个模型版本：不同业务场景或版本号

- 特征管理：

    - 不同模型输入特征个数不一样

    - 需要一个 特征映射/适配层，保证调用时能选择正确的特征

## 技术选型

- 服务框架：

    - 使用 BentoML 部署模型（API 形式对外提供服务）

    - BentoML 自动处理模型版本管理、依赖封装、容器化

- 数据库：

  本地用 PostgreSQL 存储：

    - 规则触发日志

    - 模型调用输入/输出

    - 决策结果（通过/拒绝/分数）

- 日志：

  统一用 Python logging（RotatingFileHandler），支持控制台 + 文件输出

- 配置管理：

  用 config/config.yaml 统一管理数据库、日志、服务等参数



## 服务调用方式

- 同步 API 调用：

    - 内评系统每笔进件调用一次，得到即时结果

    - 无需 Kafka

- 异步扩展（可选）：

    - 如果未来需要：

        - 大规模实时数据分析

        - 指标监控（实时进件量、逾期率）

        - 模型效果追踪

- 可以把服务调用结果异步写入 Kafka，再做实时计算

## 测试

- 生成测试数据
  ```bash
  PYTHONPATH=. python mock/data_mocker.py

- 测试单个案例
  ```bash
  PYTHONPATH=. pytest tests/test_utils.py

- 测试所有案例
   ```bash
   PYTHONPATH=. pytest tests/test_register_model.py
  ```
  ```bash
   PYTHONPATH=. pytest tests/test_register_model.py
  ```

model_type ,‘LinerRegression’, 'DecisionTree', 'RandomForest', 'XGBoost', 'LightGBM ' 等等这些模型算法

步骤：
- 训练模型
  ```bash
  cd demo/
  python train.py
  ```
  - 模型注册
    - 注册全部模型
    ```bash
    PYTHONPATH=. python src/register_model.py --all
    ```
    - 注册指定模型
    ```bash
    PYTHONPATH=. python src/register_model.py --model_name demo_loan_scorecard_lr_20250930
    ```
    - 强制注册模型
    ```bash
    PYTHONPATH=. python src/register_model.py --model_name demo_loan_scorecard_lr_20250930 --force
    ```

- 发布服务（开发模式）
  ```bash
  export PYTHONPATH=/tmp/pycharm_project_888:$PATH 
  bentoml serve src.service:Datamind --reload --port 3000
  ```
  - 如果端口被占用
    ```bash
    lsof -i :3000
    sudo fuser -k 3000/tcp
    ```
- 模型注销
  - 注销全部模型
      ```bash
      PYTHONPATH=. python src/unregister_model.py --all
     ```
  - 按tag注销模型
      ```bash
      PYTHONPATH=. python src/unregister_model.py --tag demo_loan_scorecard_lr_20250930:bnx7y63fsn2uqxgq
      ```
  - 按tag注销模型，支持批量逗号分隔
      ```bash
      PYTHONPATH=. python src/unregister_model.py --tags demo_loan_scorecard_lr_20250930:bnx7y63fsn2uqxgq, demo_loan_scorecard_rf_20250930:rweugznuok7v2b3i
      ```
  - 按uuid注销模型
      ```bash
      PYTHONPATH=. python src/unregister_model.py --uuid b4005024-444c-51a0-b312-3d43ded9e529
      ```
  - 按uuid注销模型，支持批量逗号分隔
      ```bash
      PYTHONPATH=. python src/unregister_model.py --uuid b4005024-444c-51a0-b312-3d43ded9e529,123e4567-e89b-12d3-a456-426614174000
      ```
  - 彻底删除指定模型
      ```bash
      PYTHONPATH=. python src/unregister_model.py --uuid b4005024-444c-51a0-b312-3d43ded9e529 --delete
      ```
  - 彻底删除所有模型
      ```bash
      PYTHONPATH=. python src/unregister_model.py --all --delete
      ```    
- 镜像化
    ```bash
  bentoml containerize loan_service:latest
  docker run -p 3000:3000 loan_service:latest
    ```

## 模型服务
- 查看所有模型服务
    ```bash
    PYTHONPATH=. python bentoml_helper/list_model.py
    ```
- 保留最新版本，删除历史旧模型
    ```bash
    PYTHONPATH=. python bentoml_helper/delete_model.py --keep-latest
    ```
- 删除早于指定日期的模型
    ```bash
    PYTHONPATH=. python bentoml_helper/delete_model.py --before 2025-09-01
    ```
- 删除指定tag的模型
    ```bash
    PYTHONPATH=. python bentoml_helper/delete_model.py --tag name1:version2, name2:version2 --dry-run
    ```
- 删除多个tag指定模型中早于指定日期的模型：
    ```bash
    PYTHONPATH=. python bentoml_helper/delete_model.py --tag name1:version2, name2:version2 --before 2025-09-01
    ```
  
- dry-run 模式，只打印将要删除的模型
    ```bash
    PYTHONPATH=. python bentoml_helper/delete_model.py --dry-run
    PYTHONPATH=. python bentoml_helper/delete_model.py --before 2025-09-01 --dry-run
    ```
## 镜像
- 构建镜像
```bash
docker build -t dataminddev/datamind:latest .
```
- 删除悬空镜像
```bash
docker image prune -f
```

## 启动服务
```bash
docker compose up -d
```

## 删除服务
```bash
docker compose down -v
```

## 查看日志
```bash
docker logs -f datamind
```


**规则类型**

| 类型            | 描述                  | 适用场景                | 示例                                         |
|-----------------|---------------------|-----------------------|--------------------------------------------|
| boolean         | 条件为真/假           | 是否满足某个逻辑判断       | 18 <= age <= 65                            |
| enum            | 枚举值匹配            | 职业类型、贷款用途         | employment_status in ['full_time','part_time'] |
| threshold       | 数值阈值比较          | 收入、信用分、贷款金额       | income >= 3000                              |
| cross_rule      | 跨规则依赖            | 基于前置规则结果触发       | prev_rule_R001_result == True               |
| external        | 调用外部函数/接口       | 黑名单、三方数据接口        | not_in_internal_blacklist(id_number)        |
| regex           | 正则匹配              | 身份证号、手机号、邮箱格式   | ^\d{18}$                                    |
| date            | 日期比较              | 入职时间、注册时间、有效期   | employment_date <= today - timedelta(days=180) |
| aggregate       | 聚合计算              | 逾期次数、贷款总额统计      | sum(overdue_last12m) <= 2                   |
| probabilistic   | 概率或评分卡           | 模型预测概率、风控评分       | score_probability >= 0.7                    |
| combination     | 多条件组合             | 多指标组合风控           | income >= 5000 and credit_score >= 650     |
| range           | 数值区间              | 贷款期限、利率区间        | 12 <= loan_term_months <= 60               |
| list_inclusion  | 值列表包含             | 银行或城市限制           | branch_code in allowed_branches            |
| conditional     | 条件触发              | 特殊业务策略             | if loan_type == 'farm' then crop_area >= 100 |
| pattern         | 字符串模式             | 邮箱、手机号、地址        | "@gmail.com" in email                       |
| risk_score      | 风险评分阈值           | 风控评分等级判断          | risk_score < 50                             |
| custom          | 用户自定义逻辑          | 复杂业务逻辑或组合接口     | 可以通过 Python 函数实现                    |


**models 参数**
```yaml
models:
  scoring:
  - model_name: demo_loan_scorecard_lr_20250930                     # 模型名称，必填
    model_type: logistic_regression                                 # 模型类型，必填 可选 logistic_regression|decision_tree|random_forest|xgboost|lightgbm|catboost
    model_path: "models/demo_loan_scorecard_lr_20250930.pkl"        # 模型路径，必填
    version: "2vunfhf33o5tvglm"                                     # 版本编号，选填，模型注册成功后会自动生成版本编号
    uuid: "9b95a32d-a6ef-525e-afd4-027ba96e6f31"                    # 唯一标识，选填，模型注册成功后会自动生成唯一标识
    hash: "10e80124a0bd9d1a873cf1f47b1761ee368b1d0d34a89a580d3fb6708138bbf7"
    framework: sklearn                                              # 模型框架，必填，可选 sklearn|xgboost|lightgbm|torch|tensorflow|onnx|catboost
    features: demo_loan_features                                    # 模型采用的特征集索引
```

# 生成 logo
```bash
docker run --rm -it -v $(pwd)/print_logo.py:/app/print_logo.py python:3.10-slim bash -c "pip install pyfiglet && python /app/print_logo.py"
```

# git 拉取最新版本

- 生成 SSH Key：
```bash
ssh-keygen -t ed25519 -C "zhongsheng.chen@outlook.com"
```
- 查看公钥：
```bash
cat ~/.ssh/id_ed25519.pub
```
- 登录 GitHub → Settings → SSH and GPG keys → New SSH key → 粘贴公钥
- 修改仓库远程地址为 SSH：
```bash
git remote set-url origin git@github.com:zhongsheng-chen/Datamind.git
```
- 测试连接：
```bash
ssh -T git@github.com
```
- 拉取最新代码
```bash
git fetch origin
git reset --hard origin/master
```
或
```bash
git rebase --abort
git fetch origin
git reset --hard origin/master
```
# git 推送最新版本

- 查看远程地址
```bash
git remote -v
```
- 添加所有修改并提交
```bash
git add .
git commit -m "本地最新修改提交"
```
- 推送到远程仓库
```bash
git push -u origin master # 第一次
```
或
```bash
git push origin master
```
或
```bash
git push origin master --force
```
- 创建Tag
```bash
git tag -a v20251112 -m "版本 v20251112 发布"
```
- 查看Tag
```bash
git show v20251112
```
- 推送 tag 到远程
```bash
git push origin v20251112
```
- 删除本地 Tag
```bash
git tag -d v20251112
```
- 删除远程 Tag
```bash
git push origin --delete v20251112
```