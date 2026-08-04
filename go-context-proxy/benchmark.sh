#!/bin/bash

# Performance Benchmark Script for Pure Rust Architecture

set -e

echo "🚀 Starting Performance Benchmark..."
echo ""

# Check prerequisites
if ! command -v wrk &> /dev/null; then
    echo "⚠️  wrk not found. Installing..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y wrk
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install wrk
    else
        echo "❌ Please install wrk manually: https://github.com/wg/wrk"
        exit 1
    fi
fi

# Configuration
TARGET_URL="http://localhost/v1/chat/completions"
SERVICE_KEY="test-key-001"
DURATION="30s"
THREADS=8
CONNECTIONS=100

# Create test payload
cat > /tmp/wrk_payload.lua << 'EOF'
wrk.method = "POST"
wrk.body = '{"model":"gpt-4","messages":[{"role":"user","content":"test"}],"stream":false}'
wrk.headers["Content-Type"] = "application/json"
wrk.headers["x-service-key"] = "test-key-001"
EOF

echo "📊 Benchmark Configuration:"
echo "  Target URL: $TARGET_URL"
echo "  Duration: $DURATION"
echo "  Threads: $THREADS"
echo "  Connections: $CONNECTIONS"
echo ""

# Warm-up
echo "🔥 Warming up (10s)..."
wrk -t 2 -c 10 -d 10s -s /tmp/wrk_payload.lua $TARGET_URL > /dev/null 2>&1

echo "✅ Warm-up complete"
echo ""

# Run benchmark
echo "⚡ Running benchmark..."
echo ""

wrk -t $THREADS -c $CONNECTIONS -d $DURATION -s /tmp/wrk_payload.lua --latency $TARGET_URL

echo ""
echo "📈 Performance Summary:"
echo ""

# Get current metrics
echo "🔍 Current Metrics from Prometheus:"
echo ""

# Total requests
total_requests=$(curl -s 'http://localhost:9090/api/v1/query?query=sum(proxy_requests_total)' | grep -o '"value":\[[^]]*\]' | grep -o '\[[^]]*\]' | tail -1 | cut -d',' -f2 | tr -d '"]' || echo "N/A")
echo "  📊 Total Requests: $total_requests"

# Error rate
error_rate=$(curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(proxy_errors_total[5m]))' | grep -o '"value":\[[^]]*\]' | grep -o '\[[^]]*\]' | tail -1 | cut -d',' -f2 | tr -d '"]' || echo "N/A")
echo "  ❌ Error Rate: $error_rate/s"

# Recall triggered
recall_triggered=$(curl -s 'http://localhost:9090/api/v1/query?query=sum(proxy_recall_triggered_total)' | grep -o '"value":\[[^]]*\]' | grep -o '\[[^]]*\]' | tail -1 | cut -d',' -f2 | tr -d '"]' || echo "N/A")
echo "  🧠 Recall Triggered: $recall_triggered"

echo ""

# Resource usage
echo "💾 Resource Usage:"
echo ""
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
  $(docker ps -qf "name=rust-proxy") \
  $(docker ps -qf "name=rust-recall")

echo ""
echo "✅ Benchmark complete!"
echo ""
echo "📚 View detailed metrics:"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana: http://localhost:3000"
echo ""

# Cleanup
rm -f /tmp/wrk_payload.lua
