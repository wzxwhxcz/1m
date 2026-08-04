#!/bin/bash
# Pure Rust 架构启动脚本
# 用法: ./start-pure-rust.sh

set -e

echo "🚀 启动 Pure Rust 架构..."
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未找到 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，从 .env.example 创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件"
    echo ""
    echo "⚠️  重要: 请编辑 .env 文件，填写以下信息:"
    echo "  - EMBEDDING_API_KEY (必须)"
    echo "  - OPENAI_API_KEY (必须)"
    echo "  - 修改默认密码 (推荐)"
    echo ""
    read -p "按 Enter 继续启动 (使用默认配置)，或 Ctrl+C 取消..."
fi

echo "📦 拉取最新镜像..."
docker compose -f docker-compose.pure-rust.yml pull

echo ""
echo "🏗️  构建 Rust 服务..."
docker compose -f docker-compose.pure-rust.yml build

echo ""
echo "🚀 启动服务..."
docker compose -f docker-compose.pure-rust.yml up -d

echo ""
echo "⏳ 等待服务启动..."
sleep 10

echo ""
echo "🔍 检查服务状态..."
docker compose -f docker-compose.pure-rust.yml ps

echo ""
echo "✅ Pure Rust 架构已启动！"
echo ""
echo "📍 服务访问地址:"
echo "  - 代理服务: http://localhost:80"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000 (admin / \$GRAFANA_ADMIN_PASSWORD)"
echo ""
echo "🔍 查看日志:"
echo "  docker compose -f docker-compose.pure-rust.yml logs -f"
echo ""
echo "🛑 停止服务:"
echo "  docker compose -f docker-compose.pure-rust.yml down"
