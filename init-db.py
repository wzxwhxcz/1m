#!/usr/bin/env python3
import sqlite3
import sys
from pathlib import Path

DB_FILE = "proxy.db"

# Check if database exists
if Path(DB_FILE).exists():
    response = input(f"Database {DB_FILE} already exists. Recreate? (y/N): ")
    if response.lower() != 'y':
        print("Keeping existing database")
        sys.exit(0)
    Path(DB_FILE).unlink()
    print("Deleted existing database")

print("Creating SQLite database...")

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Create admins table
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_key TEXT UNIQUE NOT NULL,
    email TEXT,
    plan TEXT DEFAULT 'free',
    quota_daily INTEGER DEFAULT 1000,
    quota_used_today INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Create request_logs table
cursor.execute("""
CREATE TABLE IF NOT EXISTS request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    upstream_url TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    recall_triggered INTEGER DEFAULT 0,
    recall_latency_ms INTEGER,
    total_latency_ms INTEGER NOT NULL,
    status INTEGER NOT NULL,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# Create indexes
cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_service_key ON users(service_key)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_user_id ON request_logs(user_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username)")

# Insert default admin (password: admin123)
# bcrypt hash: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7667N8hFJu
cursor.execute("""
INSERT OR IGNORE INTO admins (username, password_hash) 
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7667N8hFJu')
""")

# Insert demo users
demo_users = [
    ('sk-test-demo-key-12345678', 'demo@example.com', 'free', 1000, 1),
    ('sk-test-basic-key-11111111', 'basic@example.com', 'basic', 5000, 1),
    ('sk-test-premium-key-22222222', 'premium@example.com', 'premium', 20000, 1),
    ('sk-test-enterprise-key-33333333', 'enterprise@example.com', 'enterprise', 100000, 1)
]

for user in demo_users:
    cursor.execute("""
    INSERT OR IGNORE INTO users (service_key, email, plan, quota_daily, is_active) 
    VALUES (?, ?, ?, ?, ?)
    """, user)

conn.commit()
conn.close()

print("✅ Database initialized successfully!")
print("")
print("Demo service keys created:")
print("  - sk-test-demo-key-12345678 (free, 1000/day)")
print("  - sk-test-basic-key-11111111 (basic, 5000/day)")
print("  - sk-test-premium-key-22222222 (premium, 20000/day)")
print("  - sk-test-enterprise-key-33333333 (enterprise, 100000/day)")
print("")
print("Admin credentials:")
print("  - Username: admin")
print("  - Password: admin123")
