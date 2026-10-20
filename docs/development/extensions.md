# 扩展开发

为 Datamind 增加功能时，通常需要同时修改请求入口、业务服务和相关基础模块。本页说明如何选择实现位置，以及如何将新能力接入现有的配置、数据库和模型执行流程。开发环境的安装见[开发环境](index.md)。

## 代码组织

代码按请求入口、业务服务、数据访问和模型执行等职责组织。扩展功能时，可通过下表查找相关模块；涉及多个入口的业务规则应统一放在服务层，由 CLI 和管理控制台共同调用。

| 修改内容                         | 实现位置                   |
|----------------------------------|----------------------------|
| 命令和终端输出                   | `datamind/cli/`            |
| 管理控制台请求与响应             | `datamind/console/`        |
| 模型、部署、路由和实验等业务操作 | `datamind/services/`       |
| 数据模型、数据访问和事务         | `datamind/db/`             |
| 模型文件加载和输入结构提取       | `datamind/models/`         |
| 框架推理适配                     | `datamind/core/inference/` |
| 运行实例、模型加载和任务执行     | `datamind/runtime/`        |

## 新增业务功能

新增功能时，在服务层统一实现输入校验、资源状态检查和业务变更，由命令行与管理控制台共用。数据访问和事务管理沿用 Repository 与 `UnitOfWork`，可参考[模型注册服务](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/services/registration.py)；涉及运行时变更时，还需明确生效条件和重试方式。

服务完成后，按需要接入操作入口：

- **命令行**使用 Typer 定义参数和注册命令，通过 `cli_context` 获取身份并检查权限，最后将服务结果转换为终端输出。
- **管理控制台**负责解析请求、检查权限和生成响应，直接调用服务方法处理业务。

完成接入后，验证两个入口的业务行为和错误信息是否一致，检查 CLI 失败退出码、JSON 输出结构及审计记录。测试应覆盖正常操作、非法输入、资源不存在、权限不足和状态冲突，并按需补充环境隔离与重复请求场景。

## 新增配置

配置定义集中在 `datamind/config/`。优先在已有配置类中添加字段，声明类型、默认值和校验规则，并通过 `Field(description=...)` 提供说明，供环境变量参考页使用。

如果需要新增独立配置域，还需完成以下接入：

- 设置环境变量前缀，在 `providers.py` 中添加读取函数。
- 按需接入 `settings.py` 的聚合配置，并更新 `__init__.py` 的导出。
- 在 `doc_support/metadata.json` 中添加配置标题，更新 `.env.example` 及相关部署配置。

完成后，测试默认值、环境变量覆盖和非法输入，并[重新生成环境变量参考](documentation.md#更新参考文档)。配置读取函数每次加载当前值，`get_settings()` 则缓存聚合配置；使用后者的测试如果修改了环境变量，应在测试前后调用 `get_settings.cache_clear()`。

## 数据库迁移

修改数据库结构时，需要同时提供迁移脚本。使用独立开发数据库，通过 `DATAMIND_DATABASE_URL` 配置连接，以下命令均在项目根目录执行。

### 准备数据库

将开发数据库升级到当前版本，再修改 `datamind/db/models/` 中的模型定义。

```bash
datamind db upgrade
```

### 生成迁移

生成迁移脚本，将示例描述替换为本次变更内容。

```bash
python -m alembic revision --autogenerate -m "describe schema change"
```

新脚本位于 `datamind/db/migrations/versions/`。检查字段、约束和索引的变更，补充数据转换或回填逻辑；审阅完成后，再次运行 `datamind db upgrade` 应用迁移。

### 验证迁移

分别验证空数据库的完整升级和已有旧版数据的升级。需要验证回退时，先备份测试数据，再在隔离数据库中执行：

```bash
datamind db downgrade --revision -1
```

降级可能删除表或数据，命令默认要求确认。回退后重新升级，核对结构和数据是否符合预期。

## 接入模型框架

接入新框架需要完成能力声明、模型加载和推理适配，并验证注册、部署到预测的完整流程。

### 声明支持范围

先确定支持的模型类型、文件格式和任务能力，再更新对应定义：

- 在 `datamind/constants/framework.py` 和同目录的 `model_type.py` 中添加框架、模型类型及二者的支持关系。
- 在 `datamind/models/artifact/formats.py` 中声明允许的文件扩展名。

支持范围确定后，在 `pyproject.toml` 中声明所需的可选依赖，供用户按需安装。

### 模型加载

- **加载文件**：实现将字节流还原为模型对象的加载函数，通过 [ModelArtifactRegister](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/models/artifact/register.py) 的 `register` 方法注册，并在 `handlers/__init__.py` 中导入对应模块。
- **提取输入结构**：扩展[SchemaExtractor](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/models/schema.py)，获取特征名称、顺序和类型，并更新框架与提取函数的映射。

### 适配推理

模型加载后，由适配器将统一的预测请求转换为框架调用：

- 在 `datamind/core/inference/adapters/` 中继承 `BaseModelAdapter`，实现推理接口。
- 更新该目录的 `factory.py`，补充框架识别和适配器映射。

加载函数和适配器均应延迟导入框架依赖，确保未安装该框架时，其他功能仍可正常使用。

### 验证集成

先使用真实训练并保存的模型补充模块测试，覆盖以下行为：

- **加载与输入**：模型文件能够重新加载，特征名称、类型和顺序符合预期。
- **推理结果**：输入正确对齐，类别顺序、概率和预测结果正确；支持评分任务时，单独验证评分行为与注册约束。
- **异常处理**：缺少依赖、文件损坏和模型类型不受支持时，返回明确的错误信息。

模块测试通过后，将新框架加入 `scripts/verify_framework.py` 的参数和验证逻辑，执行框架检查。以下以已有的 sklearn 为例：

```bash
python -m scripts.verify_framework sklearn
```

最后，验证模型注册、部署和预测的完整流程。随镜像交付时，同步检查镜像依赖及 CI 验证范围。确认支持范围后，补充使用示例并更新[模型兼容性](../models/compatibility.md)。

## 测试与文档

扩展完成后，应验证新功能及其对已有行为的影响，并同步使用说明。提交前确认以下内容：

- **测试覆盖**：验证正常流程、边界条件和失败场景，涉及数据库或模型执行时补充集成验证。测试环境和执行方式见[测试](testing.md)。
- **文档同步**：更新受影响的操作指南和示例；命令、配置或请求模型发生变化时，重新生成参考文档并检查一致性。具体步骤见[文档维护](documentation.md)。
- **交付验证**：依赖、迁移或构建配置发生变化时，确认安装包和镜像包含所需内容。验证方式见[构建与发布](release.md)。

将实现、测试、必要的迁移和对应文档一并提交，便于审阅和验证完整变更。
