# Rust Proxy Service - 编译和部署指南

## 项目概述

纯 Rust 实现的 1M→400K 上下文压缩代理服务，支持：
- 动态路由 `/{service_key}/{upstream_url}`
- API Key 认证和配额管理
- 速率限制（Redis）
- 自动召回服务（Recall Service）
- 完整的管理后台 API

---

## 方式 1：Docker 编译（推荐）

### 环境要求
- Docker 20.10+
- Docker Compose 2.0+

### 快速启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd rust-proxy-service

# 2. 启动所有服务（自动编译）
docker-compose up -d

# 3. 查看日志
docker-compose logs -f proxy-service

# 4. 运行数据库迁移
docker-compose exec proxy-service /app/rust-proxy-service migrate

# 5. 创建管理员账号
docker-compose exec proxy-service /app/rust-proxy-service create-admin

# 6. 健康检查
curl http://localhost:8081/health
```

### 服务端口
- `8080` - 代理服务（用户请求）
- `8081` - 管理 API
- `5432` - PostgreSQL
- `6379` - Redis
- `8082` - Recall Service

---

## 方式 2：GitHub Actions 自动编译

项目已配置 GitHub Actions，每次推送到 `main` 分支或创建标签时自动编译多平台二进制文件。

### 触发编译

```bash
# 推送代码触发编译
git push origin main

# 或创建版本标签
git tag v1.0.0
git push origin v1.0.0
```

### 下载预编译二进制

编译完成后，在 GitHub Actions 的 Artifacts 中下载：
- `rust-proxy-service-linux-amd64` - Linux x64
- `rust-proxy-service-linux-amd64-musl` - Linux x64 (静态链接)
- `rust-proxy-service-windows-amd64.exe` - Windows x64
- `rust-proxy-service-macos-amd64` - macOS Intel
- `rust-proxy-service-macos-arm64` - macOS Apple Silicon

---

## 方式 3：本地编译

### Windows 环境问题

⚠️ **Windows 本地编译需要 MinGW 工具链，存在环境配置复杂性。**

如果遇到 `dlltool` 或 `link.exe` 错误，建议使用 Docker 或 GitHub Actions。

### Linux/macOS 本地编译

```bash
# 1. 安装 Rust（如果未安装）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2. 安装依赖
# Ubuntu/Debian
sudo apt-get install pkg-config libssl-dev

# macOS
brew install openssl

# 3. 编译
cd rust-proxy-service
cargo build --release

# 4. 二进制文件位置
# target/release/rust-proxy-service
```

---

## 配置说明

### 环境变量

创建 `.env` 文件：

```bash
# 数据库
DATABASE_URL=postgresql://proxy_user:proxy_pass@localhost:5432/proxy_db

# Redis
REDIS_URL=redis://localhost:6379

# Recall Service（多个用逗号分隔）
RECALL_SERVICE_URLS=http://localhost:8082,http://localhost:8083

# 服务器
PROXY_PORT=8080
ADMIN_PORT=8081
RUST_LOG=info

# JWT 密钥（生产环境必须更改）
JWT_SECRET=your-super-secret-jwt-key-change-me

# 速率限制
RATE_LIMIT_PER_MINUTE=60

# CORS（可选）
CORS_ALLOW_ORIGIN=*
```

### 数据库迁移

```bash
# Docker 环境
docker-compose exec proxy-service /app/rust-proxy-service migrate

# 本地环境
./target/release/rust-proxy-service migrate
```

---

## 使用示例

### 1. 创建用户和 API Key

```bash
curl -X POST http://localhost:8081/api/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-jwt-token>" \
  -d '{
    "username": "test_user",
    "email": "test@example.com",
    "plan_type": "pro",
    "quota_requests": 10000,
    "quota_tokens": 1000000
  }'
```

响应会包含 `service_key`（例如 `sk-user-abc123`）

### 2. 用户调用代理

```bash
# 通过代理访问 OpenAI
curl -X POST http://localhost:8080/sk-user-abc123/https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-openai-your-key" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

**路径格式：** `/{service_key}/{upstream_url}`

### 3. 管理后台登录

前端面板需要先登录获取 JWT Token：

```bash
curl -X POST http://localhost:8081/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

---

## 生产部署建议

### 1. 修改默认密码

```bash
# 修改 JWT_SECRET
export JWT_SECRET=$(openssl rand -base64 32)

# 修改数据库密码
export POSTGRES_PASSWORD=$(openssl rand -base64 16)
```

### 2. 使用反向代理

```nginx
# Nginx 配置示例
upstream proxy_service {
    server 127.0.0.1:8080;
}

upstream admin_api {
    server 127.0.0.1:8081;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 用户代理端点
    location / {
        proxy_pass http://proxy_service;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # 支持流式响应
        proxy_buffering off;
    }

    # 管理 API
    location /api/admin/ {
        proxy_pass http://admin_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

### 3. 监控和日志

```bash
# 查看日志
docker-compose logs -f proxy-service

# Prometheus 指标端点（需要启用）
curl http://localhost:8081/metrics

# 健康检查
curl http://localhost:8081/health
```

### 4. 备份数据库

```bash
# 导出数据库
docker-compose exec postgres pg_dump -U proxy_user proxy_db > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U proxy_user proxy_db < backup.sql
```

---

## 故障排查

### 1. 端口被占用

```bash
# Windows
netstat -ano | findstr :8080
taskkill /F /PID <PID>

# Linux/macOS
lsof -i :8080
kill -9 <PID>
```

### 2. 数据库连接失败

检查 PostgreSQL 是否启动：
```bash
docker-compose ps postgres
docker-compose logs postgres
```

### 3. Redis 连接失败

检查 Redis 是否启动：
```bash
docker-compose ps redis
docker-compose exec redis redis-cli ping
```

### 4. Recall Service 不可用

检查 Recall Service 配置：
```bash
# 测试连接
curl http://localhost:8082/health

# 查看日志
docker-compose logs recall-service
```

---

## 性能调优

### 1. 数据库连接池

在 `.env` 中调整：
```bash
DATABASE_MAX_CONNECTIONS=20
DATABASE_MIN_CONNECTIONS=5
```

### 2. Redis 连接池

```bash
REDIS_POOL_SIZE=10
```

### 3. Worker 线程数

```bash
# 默认为 CPU 核心数
TOKIO_WORKER_THREADS=8
```

---

## 开发模式

```bash
# 安装 cargo-watch（自动重新编译）
cargo install cargo-watch

# 监听文件变化并重新运行
cargo watch -x run

# 运行测试
cargo test

# 代码检查
cargo clippy

# 格式化代码
cargo fmt
```

---

## 技术栈

- **Web 框架**: Axum 0.7
- **异步运行时**: Tokio 1.43
- **数据库**: PostgreSQL + SQLx 0.8
- **缓存**: Redis + redis-rs 0.26
- **HTTP 客户端**: Reqwest 0.12
- **序列化**: Serde + serde_json
- **JWT**: jsonwebtoken 9.3
- **日志**: tracing + tracing-subscriber

---

## 许可证

MIT License

---

## 联系方式

如有问题，请提交 Issue 或 Pull Request。
