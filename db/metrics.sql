DROP TYPE IF EXISTS health_status;
CREATE TYPE health_status AS ENUM ('healthy', 'degraded', 'overloaded', 'unavailable');

CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,                                       -- 自增主键
    endpoint VARCHAR(128) NOT NULL,                              -- 请求接口
    status health_status NOT NULL,                               -- 服务状态
    request_count INT DEFAULT 0,                                 -- 请求计数
    error_count INT DEFAULT 0,                                   -- 错误请求计数
    avg_response_time DECIMAL(10, 2) DEFAULT 0,                  -- 平均响应时间 (毫秒)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,              -- 创建日期
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,              -- 最近一次更新时间
    CONSTRAINT uq_endpoint UNIQUE (endpoint)                     -- 唯一约束
);

-- 表备注
COMMENT ON TABLE metrics IS '性能指示表，记录服务的性能数据，包括请求数量、错误数量、平均响应时间等';
COMMENT ON COLUMN metrics.id IS '自增主键';
COMMENT ON COLUMN metrics.endpoint IS '请求接口，表示API接口';
COMMENT ON COLUMN metrics.status IS '服务状态，记录服务的健康状态';
COMMENT ON COLUMN metrics.request_count IS '请求计数，表示在该时间段内的请求数量';
COMMENT ON COLUMN metrics.error_count IS '错误请求计数，表示在该时间段内的错误请求数量';
COMMENT ON COLUMN metrics.avg_response_time IS '平均响应时间，表示在该时间段内的平均响应时间（毫秒）';
COMMENT ON COLUMN metrics.created_at IS '创建日期，记录该数据的时间';
COMMENT ON COLUMN metrics.updated_at IS '更新时间，最近一次更新数据的时间';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_metrics_endpoint_created_at ON metrics(endpoint, created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_status ON metrics(status);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_updated_at ON metrics(updated_at);

-- 创建触发函数
CREATE OR REPLACE FUNCTION update_metrics_from_requests() RETURNS TRIGGER AS $$
DECLARE
    response_ms DECIMAL(10,2);
    new_error INT;
BEGIN
    response_ms := COALESCE(NEW.response_time, 0);
    new_error := CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END;

    INSERT INTO metrics (endpoint, request_count, error_count, avg_response_time, status, updated_at)
    VALUES (
        NEW.endpoint,
        1,
        new_error,
        response_ms,
        'healthy',
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (endpoint) DO UPDATE
    SET
        request_count = metrics.request_count + 1,
        error_count = metrics.error_count + new_error,
        avg_response_time = ((COALESCE(metrics.avg_response_time,0) * metrics.request_count) + response_ms) / (metrics.request_count + 1),
        updated_at = CURRENT_TIMESTAMP,
        status = CASE
            WHEN ((metrics.error_count + new_error)::float / (metrics.request_count + 1)) >= 0.5 THEN 'unavailable'::health_status
            WHEN ((metrics.error_count + new_error)::float / (metrics.request_count + 1)) >= 0.2 THEN 'degraded'::health_status
            WHEN ((COALESCE(metrics.avg_response_time,0) * metrics.request_count + response_ms)/(metrics.request_count + 1)) > 2000 THEN 'overloaded'::health_status
            ELSE 'healthy'::health_status
        END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器，当 requests 新增记录时触发
DROP TRIGGER IF EXISTS trigger_update_metrics ON requests;
CREATE TRIGGER trigger_update_metrics
AFTER INSERT ON requests
FOR EACH ROW
EXECUTE FUNCTION update_metrics_from_requests();

-- 创建触发函数
CREATE OR REPLACE FUNCTION update_metrics_on_update() RETURNS TRIGGER AS $$
DECLARE
    response_ms DECIMAL(10,2);
    old_error INT;
    new_error INT;
BEGIN
    IF NEW.response_time IS NULL THEN
        RETURN NEW;
    ELSE
        response_ms := NEW.response_time;
    END IF;

    old_error := CASE WHEN OLD.status = 'failed' THEN 1 ELSE 0 END;
    new_error := CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END;

    UPDATE metrics
    SET
        avg_response_time = ((COALESCE(avg_response_time,0) * request_count - COALESCE(OLD.response_time,0) + response_ms) / request_count),
        error_count = error_count - old_error + new_error,
        updated_at = CURRENT_TIMESTAMP,
        status = CASE
            WHEN ((error_count - old_error + new_error)::float/request_count) >= 0.5 THEN 'unavailable'::health_status
            WHEN ((error_count - old_error + new_error)::float/request_count) >= 0.2 THEN 'degraded'::health_status
            WHEN avg_response_time > 2000 THEN 'overloaded'::health_status
            ELSE 'healthy'::health_status
        END
    WHERE endpoint = NEW.endpoint;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器，当 requests UPDATE 时触发
DROP TRIGGER IF EXISTS trigger_update_metrics_on_update ON requests;
CREATE TRIGGER trigger_update_metrics_on_update
AFTER UPDATE OF end_time, response_time, status ON requests
FOR EACH ROW
WHEN (OLD.end_time IS DISTINCT FROM NEW.end_time OR OLD.response_time IS DISTINCT FROM NEW.response_time OR OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION update_metrics_on_update();
