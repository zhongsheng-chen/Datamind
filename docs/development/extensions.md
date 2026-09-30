# 数据库与扩展

扩展时同时维护入口、服务约束、持久化、权限与测试。CLI 和 Console 负责接收请求，共享业务校验放在 Service 或公共模块。

## 配置体系

字段与校验定义在 `datamind/config/`。新增配置要选择稳定前缀，设置类型、默认值和 validator，同步 `.env.example` 与容器模板，覆盖合法和非法输入测试。运行 `python -m scripts.generate_docs_reference` 更新[配置 Reference](../reference/configuration.md)。嵌套配置有独立环境变量前缀，进程中的 provider 缓存需要在测试隔离时清理。

## Migration

迁移位于 `datamind/db/migrations/versions/`，应用入口 `datamind db upgrade` 升级到 head，无需工作目录里的 alembic.ini。修改数据库模型后，在专用开发数据库生成迁移：

```python
from pathlib import Path
from alembic import command
from alembic.config import Config
import datamind.db.migration as migration

config = Config()
config.set_main_option("script_location", str(Path(migration.__file__).parent / "migrations"))
command.revision(config, message="describe schema change", autogenerate=True)
```

配置由迁移 env 读取，先提供正确的服务环境和数据库 URL。人工检查生成的 upgrade/downgrade，尤其是重命名、数据回填、约束和索引。自动生成的结构差异不能替代数据迁移设计。对空数据库及已有旧版数据分别运行升级，核对模型 metadata 和迁移 head。

需要验证 downgrade 时在隔离开发数据库用上述 Config 调用 `command.downgrade(config, "-1")`，再升级回来并核对数据。当前产品 CLI 没有 downgrade/revision 命令。生产回退要经过备份恢复评估。

## 新增 CLI

1. 在相应命令组实现 Typer 函数，必要时注册到 `datamind/cli/main.py`。
2. 解析参数和输出格式，使用现有身份上下文，声明实际资源权限。
3. 调用共享服务，并保持 JSON 输出、非零失败退出码及审计行为。
4. 增加 CLI 与服务测试，覆盖无权限、非法输入、环境不一致及资源状态冲突。
5. 运行 Reference 生成器，更新使用指南和导航。用 `--check` 验证参数表一致性。

## 新增模型框架

1. 在 Framework、ModelType、框架与类型映射中声明能力，并定义支持的制品格式。
2. 为 `models/artifact/handlers/` 注册真实加载器，覆盖合法文件、错误文件及缺失可选依赖。
3. 在 `models/schema.py` 提取有序特征信息。检查序列化后名称是否保留。
4. 实现 `core/inference/adapters/` 的适配器与 factory 注册，覆盖输入对齐、概率和预测输出。评分能力需要单独校验。
5. 添加 optional extra、示例、框架 Unit/Integration、`scripts.verify_framework` 验证和 CI 矩阵。交付镜像也必须有对应依赖与 Smoke。
6. 更新[兼容性](../models/compatibility.md)、示例及开发说明。

一个 extra 只解决安装依赖，不能替代加载、Schema、推理与交付验证。扩展不得破坏现有框架的注册约束或改变预测字段的含义。
