CREATE TABLE IF NOT EXISTS metrics_history (
    id SERIAL PRIMARY KEY,                     -- 自增主键
    endpoint VARCHAR(128) NOT NULL,           -- 请求接口
    status health_status NOT NULL,            -- 服务状态
    request_count INT DEFAULT 0,              -- 请求计数
    error_count INT DEFAULT 0,                -- 错误请求计数
    avg_response_time DECIMAL(10,2) DEFAULT 0,-- 平均响应时间
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- 快照时间
);

-- 表备注
COMMENT ON TABLE metrics_history IS 'metrics 表历史快照表，每次更新记录一条快照';

COMMENT ON COLUMN metrics_history.id IS '自增主键';
COMMENT ON COLUMN metrics_history.endpoint IS '请求接口';
COMMENT ON COLUMN metrics_history.status IS '服务状态';
COMMENT ON COLUMN metrics_history.request_count IS '请求计数';
COMMENT ON COLUMN metrics_history.error_count IS '错误请求计数';
COMMENT ON COLUMN metrics_history.avg_response_time IS '平均响应时间（毫秒）';
COMMENT ON COLUMN metrics_history.snapshot_at IS '快照时间';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_metrics_history_endpoint ON metrics_history(endpoint);
CREATE INDEX IF NOT EXISTS idx_metrics_history_snapshot_at ON metrics_history(snapshot_at);

-- 创建触发函数
CREATE OR REPLACE FUNCTION record_metrics_history() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO metrics_history (endpoint, status, request_count, error_count, avg_response_time, snapshot_at)
    VALUES (NEW.endpoint, NEW.status, NEW.request_count, NEW.error_count, NEW.avg_response_time, CURRENT_TIMESTAMP);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
DROP TRIGGER IF EXISTS trigger_metrics_history ON metrics;
CREATE TRIGGER trigger_metrics_history
AFTER UPDATE ON metrics
FOR EACH ROW
EXECUTE FUNCTION record_metrics_history();
