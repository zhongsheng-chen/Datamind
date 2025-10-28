--CREATE TYPE model_status AS ENUM ('pending', 'active', 'inactive', 'archived');
--CREATE TYPE model_task AS ENUM ('scoring', 'fraud');

CREATE TABLE IF NOT EXISTS model_registry (
  id SERIAL PRIMARY KEY,                                              -- 自增主键
  model_name VARCHAR(256) NOT NULL,                                   -- 模型名称
  model_type VARCHAR(64) NOT NULL,                                    -- 模型类型
  model_path VARCHAR(2048) NOT NULL,                                  -- 模型路径
  version VARCHAR(64) NOT NULL,                                       -- 模型版本
  framework VARCHAR(64) NOT NULL,                                     -- 模型框架
  task model_task NOT NULL,                                           -- 任务类型
  hash CHAR(64) NOT NULL,                                             -- 哈希值
  tag VARCHAR(256) UNIQUE,                                            -- 模型标签
  uuid UUID UNIQUE DEFAULT gen_random_uuid(),                         -- 唯一标识
  status model_status DEFAULT 'pending',                              -- 生效状态
  registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,   -- 创建时间
  registered_by VARCHAR(64) DEFAULT current_user,                     -- 创建人
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,      -- 最近更新时间
  updated_by VARCHAR(64) DEFAULT current_user,                        -- 最近更新人
  CONSTRAINT uq_model UNIQUE (model_name, version, hash, task)        -- 唯一约束
);

-- 添加表备注
COMMENT ON TABLE model_registry IS '模型注册表，存储模型的元数据信息。';

-- 添加列备注
COMMENT ON COLUMN model_registry.id IS '自增主键。';
COMMENT ON COLUMN model_registry.model_name IS '模型名称。';
COMMENT ON COLUMN model_registry.model_type IS '模型类型：decision_tree|random_forest|xgboost|lightgbm|logistic_regression。';
COMMENT ON COLUMN model_registry.model_path IS '模型文件的存储路径。';
COMMENT ON COLUMN model_registry.version IS '模型的版本号。';
COMMENT ON COLUMN model_registry.framework IS '模型框架：sklearn|xgboost|lightgbm|torch|tensorflow|onnx|catboost。';
COMMENT ON COLUMN model_registry.task IS '任务类型：scoring-评分，fraud-欺诈检测。';
COMMENT ON COLUMN model_registry.hash IS '模型文件的SHA256哈希值，用于确保文件的唯一性。';
COMMENT ON COLUMN model_registry.tag IS '模型标签，由BentoML生成，格式为：model_name:version。';
COMMENT ON COLUMN model_registry.uuid IS '模型的唯一标识符。';
COMMENT ON COLUMN model_registry.status IS '模型的生效状态：active|inactive|archived|pending。';
COMMENT ON COLUMN model_registry.registered_at IS '注册模型的时间。';
COMMENT ON COLUMN model_registry.registered_by IS '注册模型的人员。';
COMMENT ON COLUMN model_registry.updated_at IS '更新模型的时间。';
COMMENT ON COLUMN model_registry.updated_by IS '更新模型的人员。';

-- 创建索引,提高查询的效率
CREATE UNIQUE INDEX IF NOT EXISTS uq_idx_model_registry_uuid ON model_registry (uuid);
CREATE INDEX IF NOT EXISTS idx_model_registry_hash ON model_registry (hash);
CREATE INDEX IF NOT EXISTS idx_model_registry_status ON model_registry (status);
CREATE INDEX IF NOT EXISTS idx_model_registry_framework ON model_registry (framework);
CREATE INDEX IF NOT EXISTS idx_model_registry_task ON model_registry (task);
CREATE INDEX IF NOT EXISTS idx_model_registry_name_version ON model_registry (model_name, version);
CREATE INDEX IF NOT EXISTS idx_model_registry_name_version_status ON model_registry (model_name, version, status);

-- 创建触发函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.updated_by = current_user;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器，每次更新 model_registry 时触发
CREATE TRIGGER trg_update_model_registry
BEFORE UPDATE ON model_registry
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();