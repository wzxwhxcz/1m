-- SQLite Schema for 1M Context Compression Proxy

-- Create admins table
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_key TEXT UNIQUE NOT NULL,
    email TEXT,
    plan TEXT DEFAULT 'free',
    quota_daily INTEGER DEFAULT 1000,
    quota_used_today INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create request_logs table
CREATE TABLE IF NOT EXISTS request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    upstream_url TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    recall_triggered BOOLEAN DEFAULT 0,
    recall_latency_ms INTEGER,
    total_latency_ms INTEGER NOT NULL,
    status INTEGER NOT NULL,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_service_key ON users(service_key);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_request_logs_user_id ON request_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username);

-- Insert default admin (username: admin, password: admin123)
-- bcrypt hash of "admin123"
INSERT OR IGNORE INTO admins (username, password_hash) 
VALUES ('admin', '$2b$10$YourBcryptHashHere');

-- Insert demo users
INSERT OR IGNORE INTO users (service_key, email, plan, quota_daily, is_active) 
VALUES 
    ('sk-test-demo-key-12345678', 'demo@example.com', 'free', 1000, 1),
    ('sk-test-basic-key-11111111', 'basic@example.com', 'basic', 5000, 1),
    ('sk-test-premium-key-22222222', 'premium@example.com', 'premium', 20000, 1),
    ('sk-test-enterprise-key-33333333', 'enterprise@example.com', 'enterprise', 100000, 1);
