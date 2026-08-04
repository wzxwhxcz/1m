-- Initialize database for 1M Context Compression Proxy

-- Create service_keys table
CREATE TABLE IF NOT EXISTS service_keys (
    id SERIAL PRIMARY KEY,
    key_value VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    rate_limit INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    total_requests INTEGER DEFAULT 0
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_service_keys_value ON service_keys(key_value);
CREATE INDEX IF NOT EXISTS idx_service_keys_active ON service_keys(is_active);

-- Create usage_logs table (optional)
CREATE TABLE IF NOT EXISTS usage_logs (
    id SERIAL PRIMARY KEY,
    service_key_id INTEGER REFERENCES service_keys(id),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_key ON usage_logs(service_key_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created ON usage_logs(created_at);

-- Insert demo service key
INSERT INTO service_keys (key_value, name, rate_limit, is_active) 
VALUES ('sk-test-demo-key-12345678', 'Demo Key', 1000, true)
ON CONFLICT (key_value) DO NOTHING;

-- Insert sample keys for testing
INSERT INTO service_keys (key_value, name, rate_limit, is_active) 
VALUES 
    ('sk-test-basic-key-11111111', 'Basic Tier', 100, true),
    ('sk-test-premium-key-22222222', 'Premium Tier', 500, true),
    ('sk-test-enterprise-key-33333333', 'Enterprise Tier', 10000, true)
ON CONFLICT (key_value) DO NOTHING;

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Success message
\echo 'Database initialized successfully!'
\echo 'Demo keys created:'
\echo '  - sk-test-demo-key-12345678 (1000 req/min)'
\echo '  - sk-test-basic-key-11111111 (100 req/min)'
\echo '  - sk-test-premium-key-22222222 (500 req/min)'
\echo '  - sk-test-enterprise-key-33333333 (10000 req/min)'
