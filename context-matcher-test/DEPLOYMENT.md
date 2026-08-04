# 1M→400K Context Compression - 部署指南

**版本**: 1.0.0  
**更新日期**: 2026-08-04

---

## 📋 目录

1. [快速开始](#快速开始)
2. [系统要求](#系统要求)
3. [本地开发](#本地开发)
4. [Docker部署](#docker部署)
5. [生产部署](#生产部署)
6. [监控告警](#监控告警)
7. [故障排查](#故障排查)
8. [性能优化](#性能优化)

---

## 🚀 快速开始

### 最简单的方式（Docker Compose）

```bash
# 1. 克隆仓库
git clone https://github.com/wzxwhxcz/1m.git
cd 1m/context-matcher-test

# 2. 启动所有服务
docker-compose up -d

# 3. 检查服务状态
docker-compose ps

# 4. 访问服务
# API文档: http://localhost/docs
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

就这么简单！✅

---

## 💻 系统要求

### 最低配置（单实例）

| 组件 | 要求 |
|------|------|
| CPU | 2核心 |
| 内存 | 4GB |
| 存储 | 10GB |
| 操作系统 | Linux / macOS / Windows |
| Docker | 20.10+ |
| Docker Compose | 1.29+ |

### 推荐配置（生产环境 - 3实例集群）

| 组件 | 要求 |
|------|------|
| CPU | 8核心 (3实例 × 2核 + Redis 1核 + Nginx 1核) |
| 内存 | 16GB (3实例 × 4GB + Redis 2GB + 其他 2GB) |
| 存储 | 100GB SSD |
| 网络 | 100Mbps+ |
| 操作系统 | Ubuntu 22.04 LTS / CentOS 8+ |

---

## 🛠️ 本地开发

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动开发服务器

```bash
# 启动API服务
cd src
uvicorn api_server:app --reload --port 8000

# 访问API文档
open http://localhost:8000/docs
```

### 3. 运行测试

```bash
# 单元测试
python src/test_production_service.py

# 大规模测试
python src/test_large_scale.py

# CAR算法测试
python src/test_car_retrieval.py
```

---

## 🐳 Docker部署

### 单实例部署

```bash
# 1. 构建镜像
docker build -t context-compression:latest .

# 2. 启动容器
docker run -d \
  --name context-api \
  -p 8000:8000 \
  -e CACHE_BACKEND=memory \
  -e ENABLE_MONITORING=true \
  context-compression:latest

# 3. 检查健康状态
curl http://localhost:8000/health
```

### 多实例集群部署

```bash
# 启动完整集群（3个API实例 + Redis + Nginx + 监控）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api-1

# 扩容（增加到5个API实例）
docker-compose up -d --scale api-1=2 --scale api-2=2 --scale api-3=1

# 停止服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

---

## 🏭 生产部署

### 架构图

```
                    ┌──────────────────┐
                    │   用户请求        │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │  Nginx (80)      │  ← 负载均衡
                    │  Load Balancer   │
                    └────────┬─────────┘
                             ↓
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  API Node 1  │    │  API Node 2  │    │  API Node 3  │
│  (8001)      │    │  (8002)      │    │  (8003)      │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       └────────────────────┼────────────────────┘
                            ↓
                   ┌──────────────────┐
                   │  Redis (6379)    │  ← 共享缓存
                   │  Cache Cluster   │
                   └──────────────────┘
                            ↓
       ┌────────────────────┼────────────────────┐
       ↓                    ↓                    ↓
┌─────────────┐   ┌──────────────┐   ┌──────────────┐
│ Prometheus  │   │   Grafana    │   │  AlertManager│
│   (9090)    │   │   (3000)     │   │   (9093)     │
└─────────────┘   └──────────────┘   └──────────────┘
```

### 部署步骤

#### 1. 准备服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### 2. 克隆代码

```bash
# 克隆仓库
git clone https://github.com/wzxwhxcz/1m.git
cd 1m/context-matcher-test

# 检查文件
ls -la
```

#### 3. 配置环境变量

```bash
# 创建环境变量文件
cat > .env << EOF
# API配置
CACHE_BACKEND=redis
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_TTL=3600
ENABLE_MONITORING=true

# Redis配置
REDIS_MAX_MEMORY=2gb
REDIS_MAX_MEMORY_POLICY=allkeys-lru

# Grafana配置
GF_SECURITY_ADMIN_PASSWORD=your_secure_password_here
EOF

# 设置权限
chmod 600 .env
```

#### 4. 启动服务

```bash
# 拉取镜像
docker-compose pull

# 启动服务（后台运行）
docker-compose up -d

# 查看启动日志
docker-compose logs -f

# 等待服务就绪（约30秒）
sleep 30
```

#### 5. 验证部署

```bash
# 检查所有服务状态
docker-compose ps

# 应该看到所有服务都是 "Up" 状态:
# api-1, api-2, api-3, redis, nginx, prometheus, grafana

# 测试API健康检查
curl http://localhost/health

# 应该返回:
# {"status": "healthy", ...}

# 测试API功能
curl -X POST http://localhost/api/v1/clusters/build \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "messages": [
      {"content": "How to use React hooks?", "role": "user"},
      {"content": "React hooks allow...", "role": "assistant"}
    ],
    "n_clusters": 2
  }'
```

#### 6. 配置监控

```bash
# 访问Grafana
open http://localhost:3000

# 默认登录: admin / admin (首次登录会要求修改密码)

# 添加Prometheus数据源:
# 1. Configuration → Data Sources → Add data source
# 2. 选择 Prometheus
# 3. URL: http://prometheus:9090
# 4. Save & Test

# 导入仪表板:
# 1. Create → Import
# 2. Upload JSON file 或使用仪表板ID
# 3. 选择Prometheus数据源
# 4. Import
```

---

## 📊 监控告警

### Grafana仪表板

访问 http://localhost:3000，使用以下面板监控服务：

#### 1. 系统概览面板

- 总请求数 (24小时)
- 平均延迟 (实时)
- 错误率 (%)
- 缓存命中率 (%)
- 在线API实例数

#### 2. 性能面板

- 延迟分布 (P50, P95, P99)
- 请求吞吐量 (QPS)
- 各端点延迟对比
- 缓存操作延迟

#### 3. 资源面板

- CPU使用率
- 内存使用率
- 网络I/O
- 磁盘I/O

#### 4. Redis面板

- 连接数
- 命令执行速率
- 缓存键数量
- 内存使用

### Prometheus查询

访问 http://localhost:9090，常用查询：

```promql
# 平均延迟
avg(api_latency_seconds)

# P95延迟
histogram_quantile(0.95, api_latency_seconds_bucket)

# 请求速率
rate(api_requests_total[5m])

# 错误率
sum(rate(api_requests_total{status="error"}[5m])) / sum(rate(api_requests_total[5m]))

# 缓存命中率
cache_hit_rate
```

### 告警规则

已配置的告警（参见 `alerts.yml`）：

| 告警名称 | 触发条件 | 严重程度 |
|---------|---------|---------|
| HighLatency | 平均延迟 > 200ms 持续2分钟 | warning |
| VeryHighLatency | 平均延迟 > 500ms 持续1分钟 | critical |
| LowCacheHitRate | 缓存命中率 < 70% 持续5分钟 | warning |
| HighErrorRate | 错误率 > 5% 持续1分钟 | critical |
| ServiceUnhealthy | 服务实例下线 持续1分钟 | critical |
| RedisDown | Redis不可用 持续1分钟 | critical |

---

## 🔧 故障排查

### 常见问题

#### 1. 服务启动失败

**症状**: `docker-compose up` 失败

**排查步骤**:
```bash
# 查看详细日志
docker-compose logs api-1

# 检查端口占用
netstat -tulpn | grep 8000
netstat -tulpn | grep 6379

# 检查Docker资源
docker system df
docker system prune  # 清理未使用的资源
```

**解决方案**:
- 确保端口未被占用
- 确保Docker有足够的内存和磁盘空间
- 检查 `.env` 配置是否正确

#### 2. Redis连接失败

**症状**: API日志显示 "Redis连接失败"

**排查步骤**:
```bash
# 检查Redis状态
docker-compose ps redis

# 测试Redis连接
docker exec -it context-redis redis-cli ping
# 应该返回: PONG

# 检查Redis日志
docker-compose logs redis
```

**解决方案**:
```bash
# 重启Redis
docker-compose restart redis

# 如果持续失败，删除数据卷重建
docker-compose down -v
docker-compose up -d
```

#### 3. 高延迟问题

**症状**: API响应时间 > 500ms

**排查步骤**:
```bash
# 查看监控指标
curl http://localhost/metrics

# 查看健康状态
curl http://localhost/health

# 检查缓存命中率
# 如果 cache_hit_rate < 70%，可能需要预热缓存
```

**解决方案**:
- 增加API实例数量
- 优化聚类数量 (n_clusters)
- 检查是否需要实施优化方案1（预计算embeddings）

#### 4. 内存溢出

**症状**: 容器频繁重启，日志显示OOM

**排查步骤**:
```bash
# 查看容器内存使用
docker stats

# 查看系统内存
free -h
```

**解决方案**:
```bash
# 增加容器内存限制
# 编辑 docker-compose.yml
services:
  api-1:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

---

## ⚡ 性能优化

### 优化清单

#### 立即优化（必须）

- [ ] **实施预计算embeddings缓存** （方案1）
  - 修改 `production_service.py`
  - 在 `build_clusters_async` 中缓存所有embeddings
  - 在 `car_retrieval_async` 中使用缓存
  - 预期效果: 延迟从546ms → 50ms

#### 短期优化（推荐）

- [ ] **启用Redis持久化**
  - 配置 RDB 快照: `save 900 1`
  - 配置 AOF: `appendonly yes`
  
- [ ] **优化聚类参数**
  - 根据数据规模调整 `n_clusters`
  - 100-300条消息: 5-10个簇
  - 300-1000条消息: 10-20个簇

- [ ] **添加请求限流**
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  
  @app.post("/api/v1/retrieve")
  @limiter.limit("100/minute")
  async def retrieve_context(...):
      ...
  ```

#### 长期优化（可选）

- [ ] **GPU加速**
  - 使用GPU版本的sentence-transformers
  - 修改Dockerfile添加CUDA支持

- [ ] **分布式部署**
  - 使用Kubernetes编排
  - 跨多台服务器水平扩展

- [ ] **CDN缓存**
  - 对静态响应使用CDN
  - 减少源站压力

### 性能基准

| 优化阶段 | 延迟 | 吞吐量 | 成本 |
|---------|------|--------|------|
| 当前（未优化）| 546ms | 5.5 QPS | - |
| 方案1（预计算）| 50ms | 50 QPS | 1小时开发 |
| 方案1+Redis | 30ms | 100 QPS | +Redis服务器 |
| 方案1+Redis+GPU | 10ms | 200 QPS | +GPU服务器 |

---

## 📚 API使用示例

### Python客户端

```python
import requests

BASE_URL = "http://localhost"

# 1. 构建聚类索引
response = requests.post(
    f"{BASE_URL}/api/v1/clusters/build",
    json={
        "session_id": "my-session",
        "messages": [
            {"content": "How to use React hooks?", "role": "user"},
            {"content": "What's the difference between useState and useEffect?", "role": "user"},
            # ... 更多消息
        ],
        "n_clusters": 10
    }
)
print(response.json())

# 2. 召回相关上下文
response = requests.post(
    f"{BASE_URL}/api/v1/retrieve",
    json={
        "session_id": "my-session",
        "query": "How can I optimize React performance?",
        "k": 50
    }
)
results = response.json()
print(f"召回 {len(results['results'])} 条消息")
print(f"延迟: {results['latency_ms']}ms")
```

### cURL示例

```bash
# 健康检查
curl http://localhost/health

# 构建聚类
curl -X POST http://localhost/api/v1/clusters/build \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test",
    "messages": [{"content": "test", "role": "user"}],
    "n_clusters": 5
  }'

# 召回上下文
curl -X POST http://localhost/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test",
    "query": "How to optimize performance?",
    "k": 50
  }'
```

---

## 🔒 安全建议

### 生产环境安全清单

- [ ] 使用HTTPS (TLS/SSL证书)
- [ ] 配置API密钥认证
- [ ] 启用请求限流
- [ ] 配置CORS白名单
- [ ] 定期更新依赖包
- [ ] 启用Docker安全扫描
- [ ] 配置防火墙规则
- [ ] 定期备份Redis数据
- [ ] 监控异常访问模式
- [ ] 使用强密码（Grafana、Redis）

---

## 📞 支持与联系

- **GitHub Issues**: https://github.com/wzxwhxcz/1m/issues
- **文档**: https://github.com/wzxwhxcz/1m/blob/master/README.md
- **测试报告**: `reports/`

---

**最后更新**: 2026-08-04  
**维护者**: wzxwhxcz
