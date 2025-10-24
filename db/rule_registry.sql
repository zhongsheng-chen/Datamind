CREATE TABLE IF NOT EXISTS rule_registry (
    id SERIAL PRIMARY KEY,                           -- 自增主键
    rule_id VARCHAR(32) UNIQUE NOT NULL,             -- 规则编号
    rule_name VARCHAR(256),                          -- 规则名称
    rule_type VARCHAR(256) NOT NULL,                 -- 规则类型
    rule_desc TEXT,                                  -- 规则描述
    rule_path VARCHAR(2048) NOT NULL,                -- 规则路径
    rule_category VARCHAR(256),                      -- 规则大类
    rule_group VARCHAR(256),                         -- 规则小类
    stage STAGE NOT NULL,                            -- 应用阶段
    version VARCHAR(64),                             -- 规则版本
    status STATUS DEFAULT 'active',                  -- 规则状态
    decision DECISION NOT NULL,                      -- 规则动作
    business_name VARCHAR(256) NOT NULL,             -- 业务名称
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建日期
    created_by VARCHAR(128),                         -- 创建人员
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新日期
    updated_by VARCHAR(128),                         -- 更新人员
    hash CHAR(64) NOT NULL UNIQUE,                   -- 哈希值
    priority INT DEFAULT 10,                         -- 优先级
    hint TEXT,                                       -- 规则提示
    violation TEXT,                                  -- 触发详情
    rejected_code VARCHAR(32),                       -- 拒绝代码
    stop_on_fail BOOLEAN DEFAULT FALSE,              -- 拒绝立即终止
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),      -- 规则标识
    effective_date DATE NOT NULL,                    -- 生效日期
    expiration_date DATE DEFAULT '9999-12-31',       -- 到期日期
    CONSTRAINT chk_date CHECK (effective_date <= expiration_date),
    CONSTRAINT uq_rule UNIQUE (rule_id, business_name)
);

-- 表备注
COMMENT ON TABLE rule_registry IS '规则注册表，存储授信和支用阶段规则元数据信息';

-- 列备注
COMMENT ON COLUMN rule_registry.id IS '自增主键';
COMMENT ON COLUMN rule_registry.rule_id IS '规则编号。';
COMMENT ON COLUMN rule_registry.rule_name IS '规则名称。';
COMMENT ON COLUMN rule_registry.rule_desc IS '规则描述。';
COMMENT ON COLUMN rule_registry.rule_path IS '规则文件的存储路径。';
COMMENT ON COLUMN rule_registry.rule_category IS '规则大类。';
COMMENT ON COLUMN rule_registry.rule_group IS '规则小类。';
COMMENT ON COLUMN rule_registry.stage IS '规则应用阶段：underwriting-授信阶段, disbursement-支用阶段';
COMMENT ON COLUMN rule_registry.version IS '规则版本号。';
COMMENT ON COLUMN rule_registry.status IS '规则状态：active-启用, inactive-停用, deprecated-弃用, pending-待启用';
COMMENT ON COLUMN rule_registry.decision IS '规则决策结果：approved-通过, warning-提示, rejected-拒绝, manual_review-人工复核';
COMMENT ON COLUMN rule_registry.business_name IS '业务名称。';
COMMENT ON COLUMN rule_registry.created_at IS '创建时间。';
COMMENT ON COLUMN rule_registry.created_by IS '创建人。';
COMMENT ON COLUMN rule_registry.updated_at IS '最后更新时间。';
COMMENT ON COLUMN rule_registry.updated_by IS '最后更新人。';
COMMENT ON COLUMN rule_registry.hash IS '规则文件SHA256哈希值，用于热更新检测';
COMMENT ON COLUMN rule_registry.priority IS '优先级。';
COMMENT ON COLUMN rule_registry.hint IS '规则提示。';
COMMENT ON COLUMN rule_registry.violation IS '触发详情。';
COMMENT ON COLUMN rule_registry.rejected_code IS '拒绝代码。';
COMMENT ON COLUMN rule_registry.stop_on_fail IS '拒绝立即终止。';
COMMENT ON COLUMN rule_registry.uuid IS '规则全局唯一标识';
COMMENT ON COLUMN rule_registry.effective_date IS '规则生效日期';
COMMENT ON COLUMN rule_registry.expiration_date IS '规则失效日期，默认9999-12-31表示长期有效';

-- 触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_rule_registry
BEFORE UPDATE ON rule_registry
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- 创建索引,提高查询的效率
CREATE UNIQUE INDEX IF NOT EXISTS uq_idx_rule_registry_id ON rule_registry (rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_registry_business_name ON rule_registry(business_name);
CREATE INDEX IF NOT EXISTS idx_rule_registry_date ON rule_registry(effective_date, expiration_date);

