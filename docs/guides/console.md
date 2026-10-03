# 管理控制台

Console 提供模型服务的管理与观测界面。左侧导航进入资源和运行记录，右上角账号菜单进入用户与角色管理。操作按钮按权限和资源状态显示。

截图用于定位界面功能，示例资产名称与数据不作为操作前提。CLI 操作与接口接入分别见 [参考手册](../cli/index.md)和[在线预测](online-prediction.md)。

## 概览与登录

先按[服务管理](../deployment/processes.md)启动 Console，默认访问地址为 `http://127.0.0.1:8701`。使用初始化时创建的账户登录，认证配置见[访问控制](access-control.md)。

![登录](../assets/login.png)

概览显示调用量、成功率、响应耗时与趋势。模型调用表和排行支持查看历史表现，删除模型后，已有调用仍保留在统计中。截图展开了可滚动列表，以便查看完整布局。

![概览](../assets/overview.png)

## 模型管理

### 列表与注册

进入“模型”查看状态、框架与任务类型，点击右上角“+”打开注册向导。

![模型列表](../assets/models-before-delete.png)

填写模型名称、版本、框架、类型和任务。评分卡选择 sklearn、逻辑回归与评分任务，分类模型按实际训练框架和算法填写。

![基本信息](../assets/register-basic.png)

上传制品，填写模型和版本说明后确认。任务类型与输入要求见[分类与评分](models.md)。

![上传制品](../assets/register-file.png)

![注册选项](../assets/register-options.png)

### 版本与评分卡

通过模型行的“更多操作”激活模型，在“版本”中检查目标版本状态。新增业务版本使用“添加版本”，同版本文件替换受[制品修订规则](../models/index.md)约束。

![激活模型](../assets/activate-model.png)

分类详情显示框架、任务和关联资源。评分卡版本详情还显示刻度、变量和分箱，点击“查看评分表”查看 WoE、系数与特征分，可导出 CSV 或 JSON。

![分类模型详情](../assets/classification-model.png)

![版本详情](../assets/version-detail.png)

![评分表](../assets/scorecard.png)

### 下线与回收站

下线前先结束关联实验并处理流量，停用部署，等待节点卸载后删除部署，再处理模型或版本。具体生命周期见[模型管理](../models/index.md)。

在模型行选择“删除”，填写原因并确认。逻辑删除的模型进入回收站，普通列表不再显示。

![删除确认](../assets/delete-model.png)

![普通模型列表](../assets/models.png)

回收站显示已删除资源与原因。恢复需要满足资源状态与制品条件，永久清理会删除物理制品。

![回收站](../assets/models-trash.png)

## 部署管理

在“部署”点击“+”，选择已激活版本、发布方式和环境。金丝雀发布还需选择 `champion` 或 `challenger` 角色，其他方式自动确定角色。

![创建部署](../assets/create-deployment.png)

通过行操作启用或停用部署。启用后检查运行实例的节点、状态和健康情况，一个部署可能对应多个节点。

![部署列表](../assets/deployments.png)

![运行实例](../assets/runtimes.png)

部署配置与节点实际加载分别检查，职责见[部署与运行](../deployment/index.md)。

## 流量管理

进入“路由”，创建指向目标部署的路由，设置比例、规则和时间，再启用。界面使用百分数，CLI/API 使用 0～1，例如 80% 对应 `traffic_ratio=0.8`。

![创建路由](../assets/create-routing.png)

普通路由共享主流量预算，影子路由独立采样。主、副路由用于分配到不同版本，这些名称表示分流用途。选择顺序与预算见[流量分配](../routing/index.md)，条件设置见[路由规则](../routing/rules.md)。

![路由列表](../assets/routings.png)

## 实验管理

在“实验”创建实验（`Experiment`），设置策略、曝光比例和主体字段。实验分组（`Variant`）分别绑定有效部署，指定对照组并设置权重。

![实验详情](../assets/experiment-detail.png)

![实验分组](../assets/variants.png)

启动前检查分组和部署。运行后查看主体分配与业务结果，结果成熟并回流后执行分析。曝光比例和权重的区别见[实验分流](../experiments/assignment.md)，完整操作见[A/B 教程](../experiments/index.md)。

## 运行观测

### API 调用与执行记录

“API 调用”显示模型、版本、耗时与状态。按请求 ID 筛选并打开明细，可查看输入、响应、关联决策及部署。

![调用列表](../assets/requests.png)

![请求明细](../assets/request-detail.png)

“执行记录”区分主执行 `primary` 与影子执行 `shadow`。影子结果不替代客户端收到的主结果，使用请求 ID 关联查看。

![执行记录](../assets/executions.png)

### 批量任务

按[批量指南](batch-prediction.md)提交任务后，在“批量任务”查看状态和进度。打开批次明细，检查完成、成功、失败计数及逐实例结果，部分成功需要继续排查失败实例。

![批次明细](../assets/batch-detail.png)

### 审计

“审计记录”用于查询操作者、目标资源、动作及结果。调查管理操作时按时间和资源定位，结合请求与执行记录查看。

![审计记录](../assets/audits.png)

## 系统管理

点击右上角账号菜单进入“用户管理”或“角色管理”。管理用户启停、密码与角色授权，角色决定可执行的资源操作。

![用户管理](../assets/users.png)

![角色管理](../assets/roles.png)

操作步骤见[访问控制](access-control.md)，权限全集见[状态与权限](../reference/states-permissions.md)。
