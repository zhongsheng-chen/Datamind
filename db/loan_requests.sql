CREATE TABLE IF NOT EXISTS loan_requests (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    request_data JSONB NOT NULL,
    result_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
