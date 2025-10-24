CREATE TABLE IF NOT EXISTS model_registry (
  id SERIAL PRIMARY KEY,                         -- 自增主键
  business_name VARCHAR(256),                    -- 业务名称
  model_name VARCHAR(256) NOT NULL,              -- 模型名称
  model_type VARCHAR(256) NOT NULL,              -- 模型类型
  model_path VARCHAR(2048) NOT NULL,             -- 模型路径
  version VARCHAR(64) NOT NULL,                  -- 模型版本
  framework VARCHAR(64) NOT NULL,                -- 模型框架
  hash CHAR(64) NOT NULL UNIQUE,                 -- 哈希值
  tag VARCHAR(256) UNIQUE,                       -- 模型标签
  uuid UUID UNIQUE DEFAULT gen_random_uuid(),    -- 唯一标识
  status STATUS DEFAULT 'active',                -- 生效状态
  registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,          -- 注册时间
  CONSTRAINT uq_model UNIQUE (business_name, model_name, version, hash)  -- 唯一约束
);

-- 添加表备注
COMMENT ON TABLE model_registry IS '模型注册表，存储模型的元数据信息。';

-- 添加列备注
COMMENT ON COLUMN model_registry.id IS '自增主键。';
COMMENT ON COLUMN model_registry.business_name IS '模型所属的业务名称。';
COMMENT ON COLUMN model_registry.model_name IS '模型名称。';
COMMENT ON COLUMN model_registry.model_type IS '模型类型：decision_tree|random_forest|xgboost|lightgbm|logistic_regression。';
COMMENT ON COLUMN model_registry.model_path IS '模型文件的存储路径。';
COMMENT ON COLUMN model_registry.version IS '模型的版本号。';
COMMENT ON COLUMN model_registry.framework IS '模型框架：sklearn|xgboost|lightgbm|torch|tensorflow|onnx|catboost。';
COMMENT ON COLUMN model_registry.hash IS '模型文件的SHA256哈希值，用于确保文件的唯一性。';
COMMENT ON COLUMN model_registry.tag IS '模型标签，由BentoML生成，格式为：model_name:version。';
COMMENT ON COLUMN model_registry.uuid IS '模型的唯一标识符。';
COMMENT ON COLUMN model_registry.status IS '模型的生效状态：active|inactive|archived。';
COMMENT ON COLUMN model_registry.registered_at IS '模型注册的时间。';

-- 创建索引,提高查询的效率
CREATE UNIQUE INDEX IF NOT EXISTS uq_idx_model_registry_uuid ON model_registry (uuid);