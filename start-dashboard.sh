#!/bin/bash

# 简化启动脚本 - 无需 Docker
# 只启动管理面板进行测试

set -e

echo "================================"
echo "1M Context Compression Proxy"
echo "Simplified Start (No Docker)"
echo "================================"
echo ""

# 检查 .env
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cat > .env << 'EOF'
# Embedding API
EMBEDDING_API_BASE=https://router.tumuer.me/v1
EMBEDDING_API_KEY=your-api-key-here
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B

# Database (使用内存 SQLite 进行测试)
DATABASE_URL=sqlite:///./test.db

# Redis (可选)
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=test-secret-key-change-in-production

# Server
RECALL_SERVICE_HOST=127.0.0.1
RECALL_SERVICE_PORT=8001
PROXY_SERVICE_HOST=127.0.0.1
PROXY_SERVICE_PORT=8080
EOF
    echo "✅ .env created"
fi

# 创建日志目录
mkdir -p logs

# 启动管理面板
echo "⚛️  Starting Admin Dashboard..."
cd admin-dashboard

if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

echo "🚀 Starting development server..."
echo ""
echo "================================"
echo "✅ Dashboard starting..."
echo "================================"
echo ""
echo "📍 Open in browser:"
echo "   http://localhost:3000"
echo ""
echo "🔧 Backend services are mocked for testing"
echo "   You can test the UI without backend"
echo ""
echo "💡 To start with real backend:"
echo "   1. Install Docker Desktop"
echo "   2. Run: docker-compose up -d"
echo "   3. Run this script again"
echo ""

npm run dev
