-- Create database if not exists
CREATE DATABASE IF NOT EXISTS contextproxy;

-- Connect to database
\c contextproxy;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    service_key VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255),
    plan VARCHAR(32) DEFAULT 'free',
    quota_daily INTEGER DEFAULT 100,
    quota_used_today INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Admins table
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Request logs table
CREATE TABLE IF NOT EXISTS request_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    upstream_url VARCHAR(512),
    input_tokens INTEGER,
    output_tokens INTEGER,
    recall_triggered BOOLEAN DEFAULT false,
    recall_latency_ms INTEGER,
    total_latency_ms INTEGER,
    status VARCHAR(32),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_key ON users(service_key);
CREATE INDEX IF NOT EXISTS idx_logs_user_time ON request_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_status ON request_logs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_created ON request_logs(created_at DESC);

-- Insert default admin (username: admin, password: admin123)
INSERT INTO admins (username, password_hash) 
VALUES ('admin', '$2b$10$6.gh6KN5m/UR5z6qRXVcj.C3s0JU.x9FHko43TgWOkCaxe5IxhSd2')
ON CONFLICT (username) DO NOTHING;

-- Insert test users
INSERT INTO users (service_key, email, plan, quota_daily) 
VALUES 
    ('sk-test-001', 'test1@example.com', 'free', 100),
    ('sk-test-002', 'test2@example.com', 'pro', 1000),
    ('sk-test-003', 'test3@example.com', 'enterprise', 10000)
ON CONFLICT (service_key) DO NOTHING;

-- Create function to reset daily quotas
CREATE OR REPLACE FUNCTION reset_daily_quotas()
RETURNS void AS $$
BEGIN
    UPDATE users SET quota_used_today = 0;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE contextproxy TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
