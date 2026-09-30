# Console 操作手册

从申请评分模型开始，依次完成注册、发布、预测和版本比较。最后下线一个分类模型，查看回收站与历史记录。下表列出手册使用的演示模型。

| 模型标识 | 显示名称 | 任务 | 框架 |
| --- | --- | --- | --- |
| `application-scorecard` | 申请评分模型 | scoring | sklearn / optbinning |
| `behavior-scorecard` | 行为评分模型 | scoring | sklearn / optbinning |
| `collection-scorecard` | 催收评分模型 | scoring | sklearn / optbinning |
| `fraud-risk` | 欺诈风险模型 | classification | CatBoost |
| `multi-borrowing-risk` | 多头借贷风险模型 | classification | XGBoost |
| `default-probability` | 违约概率模型 | classification | sklearn / RandomForest |

业务名称用于演示资源管理，模型仍使用 `examples/` 中的合成数据与标签。训练入口、制品名称和输入区别见[评分卡与分类模型](models.md)。

## 1. 准备环境与制品

按[本地演示环境](../deployment/local-demo.md)启动 PostgreSQL、Redis、MinIO、Runtime、Console 和任务 Worker，再运行[银行场景训练命令](../examples/index.md)。本次 Console 使用 `http://127.0.0.1:18701`。默认安装使用 8701 端口。

申请评分制品为 `application_scorecard.pkl`，候选版为 `application_scorecard_candidate.pkl`。行为和催收评分分别使用 `behavior_scorecard.pkl` 与 `collection_scorecard.pkl`。

## 2. 登录

打开控制台，填写初始化时创建的账号，点击“登录”。

![控制台登录](../assets/login.png)

左侧导航用于资源、运行状态、任务和调用查询。右上角账号菜单用于用户与角色管理。

## 3. 注册模型

进入“模型”，点击列表右上角的“+”，打开注册向导。

| 字段 | 申请评分模型 | 欺诈风险模型 |
| --- | --- | --- |
| 模型名称 | `application-scorecard` | `fraud-risk` |
| 显示名称 | 申请评分模型 | 欺诈风险模型 |
| 版本 | `1.0.0` | `1.0.0` |
| 框架 | `sklearn` | `catboost` |
| 类型 | 逻辑回归 | CatBoost |
| 任务类型 | 评分 | 分类 |

![申请评分模型基本信息](../assets/register-basic.png)

点击“下一步”上传对应制品，填写模型和版本说明，最后点击“确认注册”。评分卡类型选逻辑回归，对应 `optbinning.Scorecard` 中使用的估计器。

![上传申请评分制品](../assets/register-file.png)

![注册说明与选项](../assets/register-options.png)

按模型清单分别注册其他制品。为申请评分新增 1.1.0 时，通过“版本”的“添加版本”入口上传候选文件。同一业务版本的制品修订与新增版本的区别见[模型与版本](../models/index.md)。

## 4. 激活与检查版本

在模型行点击“更多操作”，选择“激活”。进入“版本”核对目标版本已启用。未启用时通过版本行操作激活。

![首次激活申请评分模型](../assets/activate-model.png)

删除演示开始前，模型列表包含六个业务模型：

![六个模型的注册结果](../assets/models-before-delete.png)

点击欺诈风险模型可查看 CatBoost 框架、分类任务和关联资源：

![欺诈风险分类模型详情](../assets/classification-model.png)

申请评分版本详情显示评分刻度、变量与分箱。点击“查看评分表”，检查 WoE、系数与特征分，并使用 CSV 或 JSON 导出。

![申请评分版本详情](../assets/version-detail.png)

![申请评分表](../assets/scorecard.png)

## 5. 创建并启用部署

申请评分模型需要三个部署：

| 用途 | 版本 | 发布类型 | 角色 |
| --- | --- | --- | --- |
| 主部署 | 1.0.0 | canary | Champion |
| 候选部署 | 1.1.0 | canary | Challenger |
| 影子部署 | 1.1.0 | shadow | Shadow |

进入“部署”，点击“+”，选择已启用版本。主、副路由要按比例分配，因此本演示的主部署选择“金丝雀发布”并明确选择 Champion。单一版本全量服务的简化步骤见[快速上手](../getting-started/quickstart.md)。

![创建申请评分主部署](../assets/create-deployment.png)

创建后，通过行操作选择“启用”。其余五个业务模型各创建一个 full 主部署，角色自动为 Champion。评分默认阈值为 600，分类默认概率阈值为 0.5。

![部署列表](../assets/deployments.png)

模型激活、Deployment 启用和 Runtime 加载是不同状态，还需核对运行实例。

## 6. 创建主、副与影子路由

进入“路由”，点击“+”，为申请评分配置：

| 路由名称 | 绑定部署 | 比例 |
| --- | --- | --- |
| `application-scorecard-main` | 1.0.0 Champion | 80% |
| `application-scorecard-secondary` | 1.1.0 Challenger | 20% |
| `application-scorecard-shadow` | 1.1.0 Shadow | 100% |

![创建 80% 主路由](../assets/create-routing.png)

创建后通过行操作“启用”。其余模型的 full 主路由使用 100%。Console 显示百分数，CLI/API 使用 0～1，80% 对应 `traffic_ratio=0.8`。

![主、副与影子路由](../assets/routings.png)

这里“主路由”和“副路由”表示 Champion 与 Challenger 的两条普通流量路由，不是故障转移的主备关系。两者共享 100% 主流量预算，影子路由独立采样，不占用该预算。一个部署只维护一条未删除路由。完整命令见[流量管理](../routing/index.md)。

## 7. 检查运行状态

核对模型、版本、部署角色、节点、状态和健康情况。一个 Deployment 可以对应多个运行节点，列表行数不是部署数。

![运行实例状态](../assets/runtimes.png)

首次请求见[快速上手](../getting-started/quickstart.md)，评分与分类的请求区别见[模型指南](models.md)。

## 8. 查看预测结果

进入“API 调用”，查看模型、任务、版本、耗时与状态。使用请求 ID 查询并点击对应行，可查看输入、响应及关联决策。

![真实调用记录](../assets/requests.png)

评分结果包含违约概率、总分及逐特征分。请求明细保留完整响应，并提供决策和部署的查看入口。

![申请评分请求与响应](../assets/request-detail.png)

## 9. 查看批量与影子执行

按照[批量预测](batch-prediction.md)提交异步任务。本次六个模型各完成基础批量任务，并分别提交 50、100、200 条实例。申请评分另有十二条实验批量实例。合计 25 个批次、2,124 条批量实例，均查询至成功完成。

点击批次查看总数、完成数、失败数、命中部署和结果：

![申请评分批量任务](../assets/batch-detail.png)

影子部署使用相同输入旁路执行，客户端仍获得主预测结果。进入“执行记录”，区分 primary 与 shadow 并核对状态。

![包含影子预测的执行记录](../assets/executions.png)

配置与 Worker 步骤见[影子发布](../deployment/shadow.md)。

## 10. 查看实验与分组

实验 `application-scorecard-comparison` 使用 1.0.0 主部署作为 Control，1.1.0 候选部署作为 Treatment，两个分组均启用。

![申请评分实验](../assets/experiment-detail.png)

曝光比例为 50%，Control 与 Treatment 在实验内部各占 50%。未进入实验的请求继续按 80%/20% 普通路由分配。影子执行同时旁路运行。

![实验分组与绑定版本](../assets/variants.png)

本次先用 24 次请求验证普通路由，19 次命中主部署、5 次命中候选部署。再为不同借款人提交 64 次在线请求，回流 64 条模拟 T+30 Outcome，并执行实验分析。随后继续追加大量在线与批量调用，实验保持运行。配置、请求与回流步骤见[A/B 测试](../experiments/index.md)。

## 11. 删除多头借贷风险模型

完成该模型的在线与批量预测后，先禁用并删除它的主路由，停用对应部署，待运行节点卸载后删除部署，再停用模型。CLI 操作顺序如下，ID 来自此前创建结果：

```bash
datamind route disable <multi_borrowing_routing_id>
datamind route delete <multi_borrowing_routing_id> --yes --reason "演示模型退役"
datamind deployment disable <multi_borrowing_deployment_id>
# 先在运行状态确认节点已卸载，再执行删除。
datamind deployment delete <multi_borrowing_deployment_id> --yes --reason "演示模型退役"
datamind model deactivate multi-borrowing-risk
```

回到“模型”，在多头借贷风险模型的行操作中选择“删除”，填写原因并确认：

![删除多头借贷风险模型](../assets/delete-model.png)

删除后普通模型列表保留五个模型：

![删除后的模型列表](../assets/models.png)

点击“回收站”，可查看已删除模型与删除原因。本次执行逻辑删除，未执行永久清理。

![模型回收站](../assets/models-trash.png)

## 12. 查看最终概览与审计

完成路由、实验、批量、影子和删除操作后，返回“概览”，选择“1 小时”。

![删除模型后的最终概览](../assets/overview.png)

本次从空数据库生成 32,230 次成功预测：30,106 次在线调用、2,124 条批量实例。各模型统计如下：

| 模型 | 调用数 | 最终状态 |
| --- | --- | --- |
| 申请评分模型 | 18,455 | 已启用 |
| 行为评分模型 | 4,855 | 已启用 |
| 催收评分模型 | 3,355 | 已启用 |
| 欺诈风险模型 | 2,455 | 已启用 |
| 违约概率模型 | 1,855 | 已启用 |
| 多头借贷风险模型 | 1,255 | 已删除 |

评分任务合计 26,665 次，分类任务合计 5,565 次。已删除模型的历史调用仍计入累计统计。

申请评分的 18,455 次主预测均生成成功的异步影子执行。影子执行不是另一次客户端调用，因此 32,230 次 API 调用对应 50,685 条执行记录。实验的有限样本命中数见[A/B 验证结果](../experiments/index.md)。

界面中的模型调用表和累计排行可滚动查看。为完整展示，本页概览截图展开了这两个列表，显示全部六个模型。当前可用模型数量与历史调用统计分别表示不同范围：模型删除后，其已有请求、结果和审计记录仍可查询。以概览与回收站共同核对当前资源和历史行为。

![包含模型删除的审计记录](../assets/audits.png)

## 13. 用户与角色

点击右上角账号菜单，进入“用户管理”或“角色管理”。操作按钮受当前权限和资源状态约束。

![用户管理](../assets/users.png)

![角色与权限](../assets/roles.png)

具体授权操作见[访问控制](access-control.md)。

## 验证范围

截图拍摄于 2026-09-30，来自真实运行的 Datamind v0.1.0。环境为 Python 3.12.13、Node.js 24、PostgreSQL 17.10、Redis 8.8.2、MinIO `RELEASE.2025-09-07T16-13-09Z`。

权限与状态转换见[状态与权限](../reference/states-permissions.md)，运行故障的排查见[生产部署](../deployment/production.md)。
