#!/bin/bash
# 本地启动脚本 (无需 Docker)

export PATH="$HOME/.cargo/bin:$PATH"

echo "🚀 启动 Pure Rust 架构 (本地模式)..."
echo ""

# 检查 PostgreSQL
echo "📊 检查 PostgreSQL..."
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL 未安装，需要手动安装"
    echo "   下载: https://www.postgresql.org/download/"
fi

# 检查 Redis
echo "📊 检查 Redis..."
if ! command -v redis-server &> /dev/null; then
    echo "⚠️  Redis 未安装，需要手动安装"
    echo "   Windows: https://github.com/microsoftarchive/redis/releases"
fi

echo ""
echo "🔧 启动服务..."

# 启动 PostgreSQL (如果未运行)
# pg_ctl -D /path/to/data start

# 启动 Redis (如果未运行)
# redis-server &

# 构建并启动召回服务
echo "📦 构建 Rust 召回服务..."
cd D:/1m/rust-recall-service
cargo build --release

echo "🚀 启动召回服务 (端口 9100)..."
RUST_LOG=info \
PORT=9100 \
EMBEDDING_API_BASE=http://router.tumuer.me \
EMBEDDING_API_KEY=your_api_key_here \
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B \
REDIS_URL=redis://localhost:6379 \
./target/release/rust-recall-service &

RECALL_PID=$!
echo "✅ 召回服务已启动 (PID: $RECALL_PID)"

sleep 2

# 构建并启动代理服务
echo "📦 构建 Rust 代理服务..."
cd D:/1m/rust-proxy-service
cargo build --release

echo "🚀 启动代理服务 (端口 8080)..."
RUST_LOG=info \
PORT=8080 \
HOST=0.0.0.0 \
POSTGRES_URL=postgresql://proxy_user:proxy_pass_2024@localhost:5432/context_proxy \
PYTHON_RECALL_URLS=http://localhost:9100 \
UPSTREAM_API_URL=https://api.openai.com/v1/chat/completions \
UPSTREAM_API_KEY=sk-your-openai-key \
./target/release/rust-proxy-service &

PROXY_PID=$!
echo "✅ 代理服务已启动 (PID: $PROXY_PID)"

echo ""
echo "✅ 所有服务已启动！"
echo ""
echo "📍 服务访问地址:"
echo "  - 召回服务: http://localhost:9100/health"
echo "  - 代理服务: http://localhost:8080/health"
echo ""
echo "🛑 停止服务:"
echo "  kill $RECALL_PID $PROXY_PID"
echo ""
echo "保存 PID 到文件..."
echo "$RECALL_PID" > /tmp/rust-recall.pid
echo "$PROXY_PID" > /tmp/rust-proxy.pid
