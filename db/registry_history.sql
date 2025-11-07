CREATE TABLE IF NOT EXISTS registry_history (
    id SERIAL PRIMARY KEY,                                              -- 自增主键
    model_id INT,                                                       -- 模型编号
    model_name VARCHAR(256) NOT NULL,                                   -- 模型名称
    model_type VARCHAR(64) NOT NULL,                                    -- 模型类型
    model_path VARCHAR(2048) NOT NULL,                                  -- 模型路径
    version VARCHAR(64) NOT NULL,                                       -- 模型版本
    framework VARCHAR(64) NOT NULL,                                     -- 模型框架
    task model_task NOT NULL,                                           -- 任务类型
    hash CHAR(64) NOT NULL,                                             -- 哈希值
    tag VARCHAR(256) NOT NULL,                                          -- 模型标签
    uuid UUID NOT NULL,                                                 -- 唯一标识
    status model_status DEFAULT 'inactivate',                           -- 生效状态
    change_type VARCHAR(32) NOT NULL,                                   -- 变更类型
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,      -- 变更日期
    changed_by VARCHAR(256) DEFAULT current_user,                       -- 变更人员
    remarks TEXT,                                                       -- 可选说明，比如更新内容
    CONSTRAINT fk_model FOREIGN KEY (model_id) REFERENCES registry(id) ON DELETE SET NULL
);

-- 添加表备注
COMMENT ON TABLE registry_history IS '模型注册表历史表，存储模型每次变动的记录。';

-- 添加列备注
COMMENT ON COLUMN registry_history.id IS '自增主键。';
COMMENT ON COLUMN registry_history.model_id IS '对应 registry.id 外键。';
COMMENT ON COLUMN registry_history.model_name IS '模型名称。';
COMMENT ON COLUMN registry_history.model_type IS '模型类型。';
COMMENT ON COLUMN registry_history.model_path IS '模型文件路径。';
COMMENT ON COLUMN registry_history.version IS '模型版本。';
COMMENT ON COLUMN registry_history.framework IS '模型框架。';
COMMENT ON COLUMN registry_history.task IS '任务类型：scoring-评分，fraud-欺诈检测。';
COMMENT ON COLUMN registry_history.hash IS '模型文件的SHA256哈希值，用于确保文件的唯一性。';
COMMENT ON COLUMN registry_history.tag IS '模型标签，由BentoML生成，格式为：model_name:version。';
COMMENT ON COLUMN registry_history.uuid IS '模型唯一标识。';
COMMENT ON COLUMN registry_history.status IS '模型的生效状态：active|inactive|archived|pending。';
COMMENT ON COLUMN registry_history.change_type IS '变更类型：create, update, activate, deactivate';
COMMENT ON COLUMN registry_history.changed_at IS '记录变更时间。';
COMMENT ON COLUMN registry_history.changed_by IS '记录变更人员。';
COMMENT ON COLUMN registry_history.remarks IS '更新内容备注。';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_registry_history_model_id ON registry_history(model_id);
CREATE INDEX IF NOT EXISTS idx_registry_history_changed_at ON registry_history(changed_at);
CREATE INDEX IF NOT EXISTS idx_registry_history_framework ON registry_history(framework);
CREATE INDEX IF NOT EXISTS idx_registry_history_task ON registry_history(task);
CREATE INDEX IF NOT EXISTS idx_registry_history_hash ON registry_history(hash);

-- 创建触发函数
CREATE OR REPLACE FUNCTION update_changed_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.changed_at = NOW();
    NEW.changed_by = current_user;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器，每次更新 registry_history 时触发
DROP TRIGGER IF EXISTS trg_update_registry_history ON registry_history;
CREATE TRIGGER trg_update_registry_history
BEFORE UPDATE ON registry_history
FOR EACH ROW
EXECUTE FUNCTION update_changed_at_column();
