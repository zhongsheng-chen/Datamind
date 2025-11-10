DROP TYPE IF EXISTS response_status;
CREATE TYPE response_status AS ENUM ('completed', 'failed', 'running');

CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,                                       -- 自增主键
    request_id UUID UNIQUE DEFAULT gen_random_uuid(),            -- 请求ID
    serial_number VARCHAR(64) NOT NULL,                          -- 业务流水号
    endpoint VARCHAR(64) NOT NULL,                               -- 请求接口
    workflow_name VARCHAR(256) NOT NULL,                         -- 工作流名称
    business_name VARCHAR(256) NOT NULL,                         -- 业务名称
    model_name VARCHAR(256) NOT NULL,                            -- 模型名称
    request_data JSONB,                                          -- 请求数据
    result_data JSONB,                                           -- 返回数据
    status response_status NOT NULL,                             -- 请求状态
    error_msg TEXT,                                              -- 错误信息
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,              -- 请求开始时间
    end_time TIMESTAMP,                                          -- 请求结束时间
    response_time NUMERIC(12, 3),                                -- 请求处理时长
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,              -- 创建日期
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP               -- 更新时间
);

-- 表备注
COMMENT ON TABLE requests IS '请求表，记录每次服务请求的详细信息，包括请求数据、响应数据、请求状态等';

-- 列备注：
COMMENT ON COLUMN requests.id IS '自增主键';
COMMENT ON COLUMN requests.request_id IS '请求ID，使用UUID确保请求唯一';
COMMENT ON COLUMN requests.serial_number IS '业务流水号，用于关联业务数据';
COMMENT ON COLUMN requests.endpoint IS '请求接口，记录访问的API接口';
COMMENT ON COLUMN requests.workflow_name IS '工作流名称，标识当前请求属于哪个工作流';
COMMENT ON COLUMN requests.business_name IS '业务名称，标识当前请求属于哪个业务';
COMMENT ON COLUMN requests.model_name IS '模型名称，标识当前请求使用的模型';
COMMENT ON COLUMN requests.request_data IS '请求数据，存储以JSON格式传递的请求参数';
COMMENT ON COLUMN requests.result_data IS '返回数据，存储模型返回的JSON结果数据';
COMMENT ON COLUMN requests.status IS '请求状态，表示请求的当前状态（completed, failed, running）';
COMMENT ON COLUMN requests.error_msg IS '错误信息，记录请求失败时的详细错误信息';
COMMENT ON COLUMN requests.start_time IS '请求开始时间，表示请求处理的开始时刻';
COMMENT ON COLUMN requests.end_time IS '请求结束时间，表示请求处理的结束时刻';
COMMENT ON COLUMN requests.response_time IS '请求处理时长，表示请求从开始到结束所花费的时间（毫秒）';
COMMENT ON COLUMN requests.created_at IS '创建日期，表示记录的创建时间';
COMMENT ON COLUMN requests.updated_at IS '更新时间，表示记录的最后更新时间';

-- 创建索引,提高查询的效率
CREATE UNIQUE INDEX IF NOT EXISTS uq_idx_requests_request_id ON requests (request_id);
CREATE INDEX IF NOT EXISTS idx_requests_serial_number ON requests(serial_number);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_workflow_name ON requests(workflow_name);
CREATE INDEX IF NOT EXISTS idx_requests_business_name ON requests(business_name);
CREATE INDEX IF NOT EXISTS idx_requests_model_name ON requests(model_name);
CREATE INDEX IF NOT EXISTS idx_requests_start_time ON requests(start_time);
CREATE INDEX IF NOT EXISTS idx_requests_end_time ON requests(end_time);

-- 创建触发函数
CREATE OR REPLACE FUNCTION update_response_time() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.end_time IS NOT NULL THEN
        -- 将时间差转为毫秒
        NEW.response_time := EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器，requests 更新时触发
DROP TRIGGER IF EXISTS trigger_update_response_time ON requests;
CREATE TRIGGER trigger_update_response_time
BEFORE INSERT OR UPDATE ON requests
FOR EACH ROW
EXECUTE FUNCTION update_response_time();


-- 创建触发函数, 自动更新时间
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发函数
DROP TRIGGER IF EXISTS trg_updated_at ON requests;
CREATE TRIGGER trg_updated_at
BEFORE UPDATE ON requests
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
