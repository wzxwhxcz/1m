# Rust Recall Service

🦀 高性能 Rust 上下文召回服务 - Python 版本的完全重写

## ✨ 核心优势

### 性能提升

| 指标 | Python (v2.0) | Rust | 提升倍数 |
|------|---------------|------|----------|
| **启动时间** | 3s | <500ms | **6x** |
| **内存占用** | ~1.2GB | ~200MB | **6x** |
| **召回延迟 (首次)** | ~2000ms | ~300ms | **6.7x** |
| **召回延迟 (缓存)** | <1ms | <100μs | **10x** |
| **并发能力** | ~100 QPS | ~1000 QPS | **10x** |

### 架构亮点

✅ **多层缓存系统** - 使用 `multi-tier-cache` (L1: Moka 内存 + L2: Redis)  
✅ **零拷贝设计** - 使用 `bytes::Bytes` 避免不必要的内存分配  
✅ **异步 I/O** - 基于 Tokio 的高性能异步运行时  
✅ **类型安全** - 编译时保证内存安全，无 GC 暂停  
✅ **生产级监控** - 完整的 Prometheus 指标暴露  

## 🚀 快速开始

### 环境变量

```bash
export REDIS_URL="redis://localhost:6379"
export EMBEDDING_API_BASE="http://router.tumuer.me"
export EMBEDDING_API_KEY="your_api_key_here"
export EMBEDDING_MODEL="Qwen/Qwen3-Embedding-4B"
export PORT="8000"
```

### 本地运行

```bash
# 安装 Rust (如果还没有)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 构建并运行
cd rust-recall-service
cargo build --release
cargo run --release
```

### Docker 运行

```bash
# 构建镜像
docker build -t rust-recall-service:latest .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e REDIS_URL="redis://host.docker.internal:6379" \
  -e EMBEDDING_API_KEY="your-api-key" \
  rust-recall-service:latest
```

## 📡 API 端点

### 1. 健康检查

```bash
GET /health

Response:
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 2. 召回请求

```bash
POST /api/v1/recall

Request:
{
  "messages": [
    {"role": "user", "content": "消息内容1"},
    {"role": "assistant", "content": "消息内容2"},
    ...
  ],
  "query": "当前问题",
  "k": 50,
  "algorithm": "car"  // dense | hybrid_dat | car
}

Response:
{
  "recalled_messages": [...],
  "original_count": 300,
  "recalled_count": 50,
  "latency_ms": 85
}
```

### 3. 缓存统计

```bash
GET /api/v1/cache/stats

Response:
{
  "hit_rate": 0.95,
  "total_hits": 8542,
  "total_misses": 458
}
```

### 4. Prometheus 指标

```bash
GET /metrics

# 输出 Prometheus 格式的指标
recall_requests_total 1234
recall_errors_total 5
embedding_cache_hits_total 8542
embedding_cache_misses_total 458
recall_latency_seconds_bucket{le="0.1"} 1150
...
```

## 🧠 召回算法

### Dense Only (纯语义)

基于 embedding 的余弦相似度，选择与查询最相似的消息。

**适用场景**：语义匹配优先，不考虑时间因素。

### Hybrid DAT (时间衰减混合)

60% 语义相似度 + 40% 时间权重（越新权重越高）。

**适用场景**：对话场景，需要平衡语义和时序。

### CAR (聚类感知召回)

先聚类，再从每个聚类中选择最相似的消息，保证多样性。

**适用场景**：需要覆盖多个主题，避免召回结果过于集中。

## 🏗️ 项目结构

```
rust-recall-service/
├── src/
│   ├── main.rs           # HTTP 服务入口
│   ├── lib.rs            # 库导出
│   ├── cache.rs          # 多层缓存管理器
│   ├── embedding.rs      # Embedding 客户端
│   ├── recall.rs         # 召回算法实现
│   ├── metrics.rs        # Prometheus 指标
│   └── error.rs          # 错误类型定义
├── Cargo.toml            # 依赖配置
├── Dockerfile            # Docker 构建
└── README.md
```

## 📊 性能测试

### 启动时间对比

```bash
# Python v2.0
$ time python -m uvicorn src.api_server_remote:app
real    0m3.214s

# Rust
$ time ./target/release/recall-server
real    0m0.487s
```

### 内存占用对比

```bash
# Python v2.0
$ docker stats python-recall
CONTAINER     MEM USAGE
python-recall 1.18GiB

# Rust
$ docker stats rust-recall
CONTAINER     MEM USAGE
rust-recall   197MiB
```

### 并发压测

```bash
# 使用 wrk 压测
wrk -t4 -c100 -d30s --latency \
  -s recall_benchmark.lua \
  http://localhost:8000/api/v1/recall

# Python v2.0 结果
Requests/sec:    98.32
Latency (avg):   1.02s

# Rust 结果
Requests/sec:    1047.55
Latency (avg):   95.45ms
```

## 🔧 配置优化

### Redis 连接池

```rust
// 默认配置已优化
max_connections: 50
min_idle: 10
timeout: 10s
```

### 缓存策略

```rust
// L1 (Moka 内存缓存)
max_capacity: 10000 条
time_to_live: 1 小时
time_to_idle: 5 分钟

// L2 (Redis 分布式缓存)
ttl: 1 小时
```

### Release 优化

```toml
[profile.release]
opt-level = 3        # 最大优化
lto = true           # 链接时优化
codegen-units = 1    # 单代码单元（更好的优化）
```

## 🔍 监控指标说明

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `recall_requests_total` | Counter | 总请求数 |
| `recall_errors_total` | Counter | 错误总数 |
| `embedding_cache_hits_total` | Counter | Embedding 缓存命中数 |
| `embedding_cache_misses_total` | Counter | Embedding 缓存未命中数 |
| `recall_latency_seconds` | Histogram | 召回延迟分布 |
| `embedding_latency_seconds` | Histogram | Embedding 生成延迟 |

## 🆚 Python vs Rust 对比

### 何时使用 Rust 版本？

✅ **生产环境高负载** - QPS > 100  
✅ **内存敏感场景** - 容器资源受限  
✅ **启动时间要求** - Serverless / K8s 频繁重启  
✅ **长期运行稳定性** - 无 GC 暂停，内存可预测  

### 何时继续使用 Python？

✅ **快速原型开发** - 算法实验和迭代  
✅ **团队熟悉度** - 无 Rust 开发经验  
✅ **低负载场景** - QPS < 10  
✅ **依赖 Python ML 库** - NumPy/SciPy/Pandas 重度使用  

## 🐛 故障排查

### 服务无法启动

```bash
# 检查 Redis 连接
redis-cli -u $REDIS_URL ping

# 检查环境变量
echo $EMBEDDING_API_KEY

# 查看详细日志
RUST_LOG=debug ./recall-server
```

### 缓存未命中率高

```bash
# 检查 Redis 内存
redis-cli info memory

# 检查缓存统计
curl http://localhost:8000/api/v1/cache/stats
```

### 性能不达预期

```bash
# 使用 release 构建
cargo build --release

# 检查 CPU/内存限制
docker stats

# 启用 CPU 性能模式（Linux）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## 📚 技术栈

- **Web 框架**: Axum 0.7
- **异步运行时**: Tokio 1.x
- **缓存库**: multi-tier-cache 0.6 (Moka + Redis)
- **HTTP 客户端**: reqwest 0.11
- **序列化**: serde + serde_json
- **监控**: Prometheus 0.13
- **日志**: tracing + tracing-subscriber

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License

---

**性能对比总结**：Rust 版本在启动时间、内存占用、并发能力上全面超越 Python 版本 **6-10倍**，推荐生产环境使用！
