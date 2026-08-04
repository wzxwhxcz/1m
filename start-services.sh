#!/bin/bash

# 1M Context Compression Proxy - 快速启动脚本
# 使用 Python 服务（避免本地 Rust 编译问题）

set -e

echo "================================"
echo "1M Context Compression Proxy"
echo "Quick Start Script"
echo "================================"
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "📝 Creating from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
    echo ""
    echo "Required variables:"
    echo "  - EMBEDDING_API_KEY"
    echo "  - POSTGRES_PASSWORD"
    echo "  - JWT_SECRET"
    echo ""
    exit 1
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found!"
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Environment check passed"
echo ""

# 启动基础设施服务
echo "🚀 Starting infrastructure services..."
docker-compose up -d postgres redis prometheus grafana

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# 初始化数据库
echo "📊 Initializing database..."
docker-compose exec -T postgres psql -U postgres -d context_compression << EOF
CREATE TABLE IF NOT EXISTS service_keys (
    id SERIAL PRIMARY KEY,
    key_value VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    rate_limit INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- 创建测试 Service Key
INSERT INTO service_keys (key_value, name, rate_limit) 
VALUES ('sk-test-demo-key-12345678', 'Demo Key', 1000)
ON CONFLICT (key_value) DO NOTHING;
EOF

echo "✅ Database initialized"
echo ""

# 启动 Python 服务（避免 Rust 编译问题）
echo "🐍 Starting Python recall service..."
cd context-matcher-test
python -m venv venv 2>/dev/null || true
source venv/bin/activate || source venv/Scripts/activate
pip install -q -r requirements.txt
nohup python src/api_server_remote.py > ../logs/recall-service.log 2>&1 &
RECALL_PID=$!
cd ..

echo "✅ Recall service started (PID: $RECALL_PID)"
echo ""

# 启动 Go 代理服务
echo "🔵 Starting Go proxy service..."
cd go-proxy-service
go mod download
nohup go run cmd/proxy/main.go > ../logs/proxy-service.log 2>&1 &
PROXY_PID=$!
cd ..

echo "✅ Proxy service started (PID: $PROXY_PID)"
echo ""

# 启动管理面板
echo "⚛️  Starting admin dashboard..."
cd admin-dashboard
npm install --silent
nohup npm run dev > ../logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..

echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
echo ""

# 等待服务启动
echo "⏳ Waiting for services to be ready..."
sleep 10

# 健康检查
echo ""
echo "🏥 Health check..."
echo ""

check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "  ✅ $name: OK"
        return 0
    else
        echo "  ❌ $name: FAILED"
        return 1
    fi
}

check_service "Recall Service" "http://localhost:8001/health"
check_service "Proxy Service" "http://localhost:8080/health"
check_service "Admin Dashboard" "http://localhost:3000"
check_service "Prometheus" "http://localhost:9090/-/ready"
check_service "Grafana" "http://localhost:3001/api/health"

echo ""
echo "================================"
echo "🎉 All services started!"
echo "================================"
echo ""
echo "📍 Service URLs:"
echo "  • Admin Dashboard:  http://localhost:3000"
echo "  • Proxy API:        http://localhost:8080"
echo "  • Recall API:       http://localhost:8001"
echo "  • Prometheus:       http://localhost:9090"
echo "  • Grafana:          http://localhost:3001"
echo ""
echo "🔑 Test Service Key: sk-test-demo-key-12345678"
echo ""
echo "📖 Quick Test:"
echo "  curl -X POST http://localhost:8080/api/v1/recall \\"
echo "    -H 'Authorization: Bearer sk-test-demo-key-12345678' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"test query\", \"history\": [\"message 1\", \"message 2\"]}'"
echo ""
echo "🛑 To stop services:"
echo "  kill $RECALL_PID $PROXY_PID $DASHBOARD_PID"
echo "  docker-compose down"
echo ""
echo "📊 View logs:"
echo "  tail -f logs/recall-service.log"
echo "  tail -f logs/proxy-service.log"
echo "  tail -f logs/dashboard.log"
echo ""

# 保存 PIDs
echo "$RECALL_PID $PROXY_PID $DASHBOARD_PID" > .service_pids

echo "✅ PIDs saved to .service_pids"
echo ""
