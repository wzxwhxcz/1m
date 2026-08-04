#!/bin/bash
# 快速启动脚本 (使用 Python 版本)

echo "🚀 启动 1M→400K Context Compression System..."
echo ""

# 检查必要服务
echo "📊 检查必要组件..."
services_ok=true

if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "❌ Python 未安装"
    services_ok=false
else
    echo "✅ Python 已安装"
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    services_ok=false
else
    echo "✅ Node.js 已安装"
fi

if [ "$services_ok" = false ]; then
    echo ""
    echo "⚠️  请先安装必要组件"
    exit 1
fi

echo ""
echo "🔧 启动后端服务..."

# 启动召回服务 (Python FastAPI)
cd D:/1m/context-matcher-test
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

echo "🚀 启动召回服务 (端口 8001)..."
python src/api_server_remote.py &
RECALL_PID=$!
echo "✅ 召回服务已启动 (PID: $RECALL_PID)"

sleep 2

# 启动管理面板 (React)
cd D:/1m/admin-panel
echo "🚀 启动管理面板 (端口 3000)..."
npm start &
PANEL_PID=$!
echo "✅ 管理面板已启动 (PID: $PANEL_PID)"

echo ""
echo "✅ 所有服务已启动！"
echo ""
echo "📍 服务访问地址:"
echo "  - 召回服务 API: http://localhost:8001"
echo "  - 管理面板: http://localhost:3000"
echo ""
echo "🛑 停止服务:"
echo "  kill $RECALL_PID $PANEL_PID"
echo ""
echo "💾 保存 PID..."
echo "$RECALL_PID" > /tmp/recall.pid
echo "$PANEL_PID" > /tmp/panel.pid

# 等待用户测试
echo ""
echo "⏳ 服务运行中，按 Ctrl+C 停止..."
wait
