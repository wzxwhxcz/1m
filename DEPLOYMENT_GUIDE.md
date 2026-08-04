# 🚀 Pure Rust 架构部署指南

## 📋 目录

1. [快速启动](#快速启动)
2. [安全配置](#安全配置)
3. [服务验证](#服务验证)
4. [管理面板访问](#管理面板访问)
5. [故障排查](#故障排查)
6. [性能监控](#性能监控)

---

## 快速启动

### 前置要求

- Docker 20.10+
- Docker Compose v2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

### 一键启动

```bash
cd go-context-proxy

# 方式 1: 使用启动脚本 (推荐)
./start-pure-rust.sh

# 方式 2: 手动启动
docker compose -f docker-compose.pure-rust.yml up -d
```

### 启动过程

```
🚀 启动 Pure Rust 架构...
📦 拉取最新镜像...
🏗️  构建 Rust 服务...
🚀 启动服务...
⏳ 等待服务启动...
✅ Pure Rust 架构已启动！
```

启动完成后，所有服务应该处于 `healthy` 状态。

---

## 安全配置

### ⚠️ 生产环境必须修改

在生产环境部署前，**必须**修改 `.env` 文件中的敏感信息：

```bash
# 1. 复制示例配置
cp .env.example .env

# 2. 编辑 .env 文件
nano .env
```

### 必须修改的配置

#### 1. **Embedding API Key** (高优先级)

```env
# ❌ 错误: 使用示例中的 Key
EMBEDDING_API_KEY=your_api_key_here

# ✅ 正确: 使用你自己的 Key
EMBEDDING_API_KEY=sk-your-real-api-key-here
```

**获取 API Key**: http://router.tumuer.me/

#### 2. **OpenAI API Key** (高优先级)

```env
# ❌ 错误: 使用占位符
OPENAI_API_KEY=sk-your-openai-api-key-here

# ✅ 正确: 使用真实的 OpenAI Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

#### 3. **数据库密码** (中优先级)

```bash
# 生成强密码
openssl rand -base64 32 | tr -d "=+/" | cut -c1-25

# 或使用在线工具: https://passwordsgenerator.net/
```

```env
# ❌ 错误: 使用默认密码
POSTGRES_PASSWORD=proxy_pass_2024

# ✅ 正确: 使用强密码
POSTGRES_PASSWORD=Xy9mK4nP2vL8qR5wT3jH6zF1d
```

#### 4. **Redis 密码** (中优先级)

```env
# ❌ 错误: 使用默认密码
REDIS_PASSWORD=redis_pass_2024

# ✅ 正确: 使用强密码
REDIS_PASSWORD=Bq7sW9tY1uI4oP6aS8dF3gH5k
```

#### 5. **Grafana 管理员密码** (中优先级)

```env
# ❌ 错误: 使用默认密码
GRAFANA_ADMIN_PASSWORD=admin

# ✅ 正确: 使用强密码
GRAFANA_ADMIN_PASSWORD=Cn8xZ2vB5nM9lK4tR7wQ1eP3j
```

### 完整的生产配置示例

```env
# Database
POSTGRES_PASSWORD=Xy9mK4nP2vL8qR5wT3jH6zF1d

# Redis
REDIS_PASSWORD=Bq7sW9tY1uI4oP6aS8dF3gH5k

# API Keys
EMBEDDING_API_KEY=sk-your-real-embedding-api-key
OPENAI_API_KEY=sk-proj-your-real-openai-api-key

# Grafana
GRAFANA_ADMIN_PASSWORD=Cn8xZ2vB5nM9lK4tR7wQ1eP3j
```

### 安全检查清单

修改配置后，运行安全检查：

```bash
# 1. 确认 .env 已被 .gitignore
git status .env
# 应该显示: nothing to commit

# 2. 确认密码不是默认值
grep "proxy_pass_2024\|redis_pass_2024\|admin" .env
# 应该没有输出

# 3. 确认 API Key 已填写
grep "your-api-key-here\|sk-ob6GsynU" .env
# 应该没有输出
```

---

## 服务验证

### 1. 检查服务状态

```bash
docker compose -f docker-compose.pure-rust.yml ps
```

**预期输出**:

```
NAME                STATUS              PORTS
postgres            Up (healthy)        
redis               Up (healthy)        
rust-recall-1       Up (healthy)        0.0.0.0:9100->9100/tcp
rust-recall-2       Up (healthy)        0.0.0.0:9101->9100/tcp
rust-proxy-1        Up (healthy)        0.0.0.0:8080->8080/tcp
rust-proxy-2        Up (healthy)        0.0.0.0:8081->8080/tcp
rust-proxy-3        Up (healthy)        0.0.0.0:8082->8080/tcp
nginx               Up (healthy)        0.0.0.0:80->80/tcp
prometheus          Up                  0.0.0.0:9090->9090/tcp
grafana             Up                  0.0.0.0:3000->3000/tcp
```

### 2. 健康检查

```bash
# 代理服务健康检查
curl http://localhost/health

# 召回服务健康检查
curl http://localhost:9100/health

# Prometheus 健康检查
curl http://localhost:9090/-/healthy

# Grafana 健康检查
curl http://localhost:3000/api/health
```

### 3. 数据库初始化验证

```bash
# 进入 PostgreSQL 容器
docker compose -f docker-compose.pure-rust.yml exec postgres psql -U proxy_user -d context_proxy

# 检查表是否创建成功
\dt

# 应该看到:
#  Schema |     Name      | Type  |   Owner    
# --------+---------------+-------+------------
#  public | service_keys  | table | proxy_user
#  public | usage_logs    | table | proxy_user

# 退出
\q
```

### 4. 查看服务日志

```bash
# 查看所有服务日志
docker compose -f docker-compose.pure-rust.yml logs -f

# 查看特定服务日志
docker compose -f docker-compose.pure-rust.yml logs -f rust-proxy-1
docker compose -f docker-compose.pure-rust.yml logs -f rust-recall-1
docker compose -f docker-compose.pure-rust.yml logs -f postgres
```

---

## 管理面板访问

### 1. Grafana 监控面板

**访问地址**: http://localhost:3000

**登录信息**:
- 用户名: `admin`
- 密码: `.env` 文件中的 `GRAFANA_ADMIN_PASSWORD`

**首次登录**:
1. 访问 http://localhost:3000
2. 输入用户名和密码
3. Grafana 会提示修改密码（可选）
4. 进入主界面

**添加 Prometheus 数据源**:
1. 点击左侧菜单 `Configuration` → `Data Sources`
2. 点击 `Add data source`
3. 选择 `Prometheus`
4. 配置:
   - **Name**: `Prometheus`
   - **URL**: `http://prometheus:9090`
   - **Access**: `Server (default)`
5. 点击 `Save & Test`

**导入仪表盘** (可选):

推荐的现成仪表盘:
- Rust 应用: https://grafana.com/grafana/dashboards/15489
- PostgreSQL: https://grafana.com/grafana/dashboards/9628
- Redis: https://grafana.com/grafana/dashboards/11835
- Nginx: https://grafana.com/grafana/dashboards/12708

导入步骤:
1. 点击左侧菜单 `+` → `Import`
2. 输入仪表盘 ID (如 `15489`)
3. 选择数据源 `Prometheus`
4. 点击 `Import`

### 2. Prometheus 指标查询

**访问地址**: http://localhost:9090

**常用查询**:

```promql
# 代理服务 QPS
rate(http_requests_total[1m])

# 平均响应时间
rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])

# 内存使用
process_resident_memory_bytes / 1024 / 1024

# CPU 使用率
rate(process_cpu_seconds_total[1m]) * 100

# 召回服务缓存命中率
recall_cache_hits / (recall_cache_hits + recall_cache_misses) * 100

# 数据库连接池使用
db_pool_connections_active / db_pool_connections_max * 100
```

### 3. 管理 API (需要 Service Key)

#### 创建 Service Key

```bash
# 进入 PostgreSQL
docker compose -f docker-compose.pure-rust.yml exec postgres psql -U proxy_user -d context_proxy

# 创建一个测试 Service Key
INSERT INTO service_keys (service_key, user_id, rate_limit, is_active, created_at, updated_at)
VALUES (
  'test-key-12345678',
  'test-user',
  100,
  true,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
);

# 退出
\q
```

#### 测试代理请求

```bash
curl -X POST http://localhost/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Service-Key: test-key-12345678" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
  }'
```

---

## 故障排查

### 问题 1: 服务无法启动

**症状**:
```
Error: Cannot connect to the Docker daemon
```

**解决**:
```bash
# 检查 Docker 是否运行
docker ps

# 启动 Docker Desktop (Windows/Mac)
# 或启动 Docker 服务 (Linux)
sudo systemctl start docker
```

### 问题 2: 端口被占用

**症状**:
```
Error: Ports are not available: listen tcp 0.0.0.0:80: bind: address already in use
```

**解决**:
```bash
# 查看占用端口的进程
netstat -ano | grep :80
lsof -i :80

# 停止占用端口的服务
# 或修改 docker-compose.pure-rust.yml 中的端口映射
ports:
  - "8000:80"  # 改为 8000 端口
```

### 问题 3: 健康检查失败

**症状**:
```
rust-proxy-1    Up (unhealthy)
```

**解决**:
```bash
# 查看详细日志
docker compose -f docker-compose.pure-rust.yml logs rust-proxy-1

# 常见原因:
# 1. 数据库未就绪 → 等待 postgres 变为 healthy
# 2. API Key 未配置 → 检查 .env 文件
# 3. 内存不足 → 增加 Docker 内存限制
```

### 问题 4: Embedding API 连接失败

**症状**:
```
ERROR Failed to connect to embedding API: Connection timeout
```

**解决**:
```bash
# 1. 检查 API Key 是否正确
grep EMBEDDING_API_KEY .env

# 2. 测试 API 连通性
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://router.tumuer.me/v1/embeddings \
  -d '{"input": "test", "model": "Qwen/Qwen3-Embedding-4B"}'

# 3. 检查网络代理设置 (如果在中国大陆)
```

### 问题 5: Redis 连接失败

**症状**:
```
ERROR Failed to connect to Redis: No connection could be made
```

**解决**:
```bash
# 1. 检查 Redis 是否运行
docker compose -f docker-compose.pure-rust.yml ps redis

# 2. 检查 Redis 密码
docker compose -f docker-compose.pure-rust.yml exec redis redis-cli -a YOUR_REDIS_PASSWORD ping

# 3. 重启 Redis
docker compose -f docker-compose.pure-rust.yml restart redis
```

---

## 性能监控

### 关键指标

#### 1. 代理服务性能

| 指标 | 目标 | 查询 |
|------|------|------|
| QPS | ≥ 1000 | `rate(http_requests_total[1m])` |
| P99 延迟 | ≤ 100ms | `histogram_quantile(0.99, http_request_duration_seconds_bucket)` |
| 内存使用 | ≤ 256MB | `process_resident_memory_bytes{job="rust-proxy"}` |
| CPU 使用 | ≤ 200% | `rate(process_cpu_seconds_total{job="rust-proxy"}[1m]) * 100` |

#### 2. 召回服务性能

| 指标 | 目标 | 查询 |
|------|------|------|
| 缓存命中率 | ≥ 90% | `recall_cache_hits / (recall_cache_hits + recall_cache_misses)` |
| 召回延迟 | ≤ 50ms | `histogram_quantile(0.99, recall_duration_seconds_bucket)` |
| 内存使用 | ≤ 512MB | `process_resident_memory_bytes{job="rust-recall"}` |

#### 3. 数据库性能

```bash
# 查看活跃连接
docker compose -f docker-compose.pure-rust.yml exec postgres psql -U proxy_user -d context_proxy -c "SELECT count(*) FROM pg_stat_activity;"

# 查看慢查询
docker compose -f docker-compose.pure-rust.yml exec postgres psql -U proxy_user -d context_proxy -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

### 性能基准测试

```bash
# 运行基准测试
./benchmark.sh

# 预期结果:
# - Throughput: ≥ 1000 req/s
# - Avg Latency: ≤ 50ms
# - P99 Latency: ≤ 100ms
# - Memory: ≤ 256MB per instance
```

---

## 常用命令

### 服务管理

```bash
# 启动所有服务
docker compose -f docker-compose.pure-rust.yml up -d

# 停止所有服务
docker compose -f docker-compose.pure-rust.yml down

# 重启特定服务
docker compose -f docker-compose.pure-rust.yml restart rust-proxy-1

# 查看服务状态
docker compose -f docker-compose.pure-rust.yml ps

# 查看资源使用
docker compose -f docker-compose.pure-rust.yml stats
```

### 日志管理

```bash
# 查看所有日志
docker compose -f docker-compose.pure-rust.yml logs

# 实时查看日志
docker compose -f docker-compose.pure-rust.yml logs -f

# 查看最近 100 行
docker compose -f docker-compose.pure-rust.yml logs --tail=100

# 查看特定服务
docker compose -f docker-compose.pure-rust.yml logs -f rust-proxy-1
```

### 数据管理

```bash
# 备份数据库
docker compose -f docker-compose.pure-rust.yml exec postgres pg_dump -U proxy_user context_proxy > backup.sql

# 恢复数据库
cat backup.sql | docker compose -f docker-compose.pure-rust.yml exec -T postgres psql -U proxy_user context_proxy

# 清空 Redis 缓存
docker compose -f docker-compose.pure-rust.yml exec redis redis-cli -a YOUR_REDIS_PASSWORD FLUSHALL
```

---

## 下一步

1. ✅ 完成服务启动和验证
2. ✅ 配置 Grafana 监控面板
3. 📝 创建管理 Service Keys
4. 🧪 运行性能基准测试
5. 🚀 部署到生产环境

---

**需要帮助?**

- 📖 查看安全审计报告: `SECURITY_AUDIT.md`
- 📊 查看架构对比: `RUST_REWRITE_ANALYSIS.md`
- 🔧 查看完整交付文档: `DELIVERY_SUMMARY.md`
