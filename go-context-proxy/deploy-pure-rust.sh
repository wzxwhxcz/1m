#!/bin/bash

# Pure Rust Architecture Deployment Script

set -e

echo "🚀 Starting Pure Rust Architecture Deployment..."

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# Check environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set. Please export it:"
    echo "   export OPENAI_API_KEY=sk-xxx"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build services
echo ""
echo "🔨 Building Rust services..."
cd "$(dirname "$0")"

# Build Rust Recall Service
echo "  📦 Building Rust Recall Service..."
cd ../rust-recall-service
cargo build --release
cd ../go-context-proxy

# Build Rust Proxy Service
echo "  📦 Building Rust Proxy Service..."
cd ../rust-proxy-service
cargo build --release
cd ../go-context-proxy

# Start services
echo ""
echo "🐳 Starting Docker Compose services..."
docker-compose -f docker-compose.pure-rust.yml up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Health checks
echo ""
echo "🏥 Running health checks..."

declare -A services=(
    ["PostgreSQL"]="localhost:5432"
    ["Redis"]="localhost:6379"
    ["Rust Recall 1"]="http://localhost:9100/health"
    ["Rust Recall 2"]="http://localhost:9101/health"
    ["Rust Proxy 1"]="http://localhost:8080/health"
    ["Rust Proxy 2"]="http://localhost:8081/health"
    ["Rust Proxy 3"]="http://localhost:8082/health"
    ["Nginx"]="http://localhost:80/health"
    ["Prometheus"]="http://localhost:9090/-/healthy"
    ["Grafana"]="http://localhost:3000/api/health"
)

all_healthy=true

for service in "${!services[@]}"; do
    url="${services[$service]}"
    
    if [[ $url == http* ]]; then
        if curl -sf "$url" > /dev/null 2>&1; then
            echo "  ✅ $service is healthy"
        else
            echo "  ❌ $service is NOT healthy"
            all_healthy=false
        fi
    else
        echo "  ⏭️  $service (skipping port check)"
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    echo "✨ All services are healthy!"
else
    echo "⚠️  Some services are not healthy. Check logs with:"
    echo "   docker-compose -f docker-compose.pure-rust.yml logs"
fi

# Display service URLs
echo ""
echo "📊 Service URLs:"
echo "  🌐 Nginx Load Balancer:  http://localhost"
echo "  🔧 Rust Proxy 1:         http://localhost:8080"
echo "  🔧 Rust Proxy 2:         http://localhost:8081"
echo "  🔧 Rust Proxy 3:         http://localhost:8082"
echo "  🧠 Rust Recall 1:        http://localhost:9100"
echo "  🧠 Rust Recall 2:        http://localhost:9101"
echo "  📈 Prometheus:           http://localhost:9090"
echo "  📊 Grafana:              http://localhost:3000 (admin/admin)"
echo ""

# Test API
echo "🧪 Testing API..."
echo ""

# Create test user
echo "  📝 Creating test user..."
docker exec -it $(docker ps -qf "name=postgres") psql -U proxy_user -d context_proxy -c "
INSERT INTO users (service_key, email, plan, quota_daily, is_active)
VALUES ('test-key-001', 'test@example.com', 'premium', 10000, true)
ON CONFLICT (service_key) DO NOTHING;
" 2>/dev/null || echo "  ⚠️  User might already exist"

# Test request
echo ""
echo "  🚀 Sending test request..."
response=$(curl -s -w "\n%{http_code}" -X POST http://localhost/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-service-key: test-key-001" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }' 2>/dev/null || echo "ERROR\n000")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "  ✅ API test passed (HTTP $http_code)"
else
    echo "  ❌ API test failed (HTTP $http_code)"
    echo "     Response: $body"
fi

# Performance stats
echo ""
echo "📊 Quick Performance Check:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
  $(docker ps -qf "name=rust-proxy") \
  $(docker ps -qf "name=rust-recall") 2>/dev/null || echo "  ⚠️  Docker stats unavailable"

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📚 Next steps:"
echo "  1. Import Grafana dashboard from ./grafana-dashboard.json"
echo "  2. Run performance tests: ./benchmark.sh"
echo "  3. Monitor metrics: http://localhost:9090"
echo "  4. Check logs: docker-compose -f docker-compose.pure-rust.yml logs -f"
echo ""
echo "🛑 To stop all services:"
echo "   docker-compose -f docker-compose.pure-rust.yml down"
echo ""
