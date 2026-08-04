# 部署指南

本文档详细说明如何在生产环境中部署 1M→400K 上下文压缩代理系统。

## 目录

- [系统要求](#系统要求)
- [快速部署](#快速部署)
- [生产环境配置](#生产环境配置)
- [HTTPS 配置](#https-配置)
- [性能优化](#性能优化)
- [监控和日志](#监控和日志)
- [备份和恢复](#备份和恢复)
- [故障排查](#故障排查)

## 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **CPU** | 4 核 | 8 核 |
| **内存** | 8 GB | 16 GB |
| **磁盘** | 50 GB SSD | 100 GB SSD |
| **网络** | 100 Mbps | 1 Gbps |

### 软件要求

- **操作系统**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **端口要求**:
  - 80 (HTTP)
  - 443 (HTTPS)
  - 5432 (PostgreSQL, 可选外部访问)
  - 6379 (Redis, 可选外部访问)
  - 3000 (Grafana)
  - 9090 (Prometheus)

## 快速部署

### 1. 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

### 2. 克隆仓库

```bash
git clone https://github.com/yourusername/context-proxy.git
cd context-proxy
```

### 3. 构建前端

```bash
cd go-context-proxy/web
npm install
npm run build
cd ../..
```

### 4. 启动服务

```bash
cd go-context-proxy
docker-compose up -d
```

### 5. 验证部署

```bash
# 检查所有服务状态
docker-compose ps

# 预期输出（所有服务 State 应为 Up）:
# NAME                         STATE
# contextproxy-go-1            Up (healthy)
# contextproxy-go-2            Up (healthy)
# contextproxy-go-3            Up (healthy)
# contextproxy-nginx           Up (healthy)
# contextproxy-postgres        Up (healthy)
# contextproxy-prometheus      Up
# contextproxy-python-1        Up (healthy)
# contextproxy-python-2        Up (healthy)
# contextproxy-redis           Up (healthy)
# contextproxy-grafana         Up

# 测试 API 健康检查
curl http://localhost/health
# 预期输出: {"status":"ok"}

# 测试管理后台
curl http://localhost/admin
# 预期输出: HTML 页面
```

## 生产环境配置

### 1. 修改默认密码

#### 管理员密码

生成新的 bcrypt 密码哈希:

```bash
# 使用 Python
python3 -c "import bcrypt; print(bcrypt.hashpw(b'your_new_password', bcrypt.gensalt()).decode())"

# 或使用在线工具: https://bcrypt-generator.com/
```

编辑 `init.sql`:
```sql
INSERT INTO admins (username, password_hash) 
VALUES ('admin', '$2a$10$YOUR_NEW_HASH_HERE')
ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash;
```

#### 数据库密码

编辑 `docker-compose.yml`:
```yaml
postgres:
  environment:
    POSTGRES_PASSWORD: YOUR_STRONG_PASSWORD_HERE

go-proxy-1:
  environment:
    POSTGRES_URL: postgres://admin:YOUR_STRONG_PASSWORD_HERE@postgres:5432/contextproxy?sslmode=disable
```

### 2. 配置防火墙

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 5432/tcp  # 禁止外部访问数据库
sudo ufw deny 6379/tcp  # 禁止外部访问 Redis
sudo ufw enable

# 允许特定 IP 访问监控服务（可选）
sudo ufw allow from YOUR_ADMIN_IP to any port 3000
sudo ufw allow from YOUR_ADMIN_IP to any port 9090
```

### 3. 配置资源限制

编辑 `docker-compose.yml`，为每个服务添加资源限制:

```yaml
services:
  go-proxy-1:
    # ... 其他配置
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    restart: always

  python-recall-1:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 3G
        reservations:
          cpus: '1'
          memory: 2G
    restart: always

  redis:
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 1.5G

  postgres:
    deploy:
      resources:
        limits:
          memory: 2G
```

### 4. 持久化配置

确保数据持久化到宿主机:

```yaml
volumes:
  postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/contextproxy/postgres

  redis-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/contextproxy/redis
```

创建目录:
```bash
sudo mkdir -p /data/contextproxy/{postgres,redis,prometheus,grafana}
sudo chown -R 999:999 /data/contextproxy/postgres  # Postgres UID
sudo chown -R 1000:1000 /data/contextproxy/redis
```

## HTTPS 配置

### 使用 Let's Encrypt (推荐)

#### 1. 安装 Certbot

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
```

#### 2. 申请证书

```bash
sudo certbot certonly --standalone -d your-domain.com
# 证书将保存在: /etc/letsencrypt/live/your-domain.com/
```

#### 3. 更新 Nginx 配置

编辑 `nginx.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # HTTP 自动跳转 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL 优化配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # ... 其他配置保持不变
}
```

#### 4. 挂载证书到 Docker

编辑 `docker-compose.yml`:

```yaml
nginx:
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./web/dist:/usr/share/nginx/html:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro  # 添加此行
  ports:
    - "80:80"
    - "443:443"  # 添加 HTTPS 端口
```

#### 5. 自动续期

```bash
# 测试续期
sudo certbot renew --dry-run

# 添加自动续期任务
sudo crontab -e
# 添加以下行（每天凌晨 2 点检查）
0 2 * * * certbot renew --quiet && docker-compose -f /path/to/docker-compose.yml restart nginx
```

## 性能优化

### 1. PostgreSQL 优化

创建 `postgresql.conf`:

```ini
# 连接设置
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10MB
min_wal_size = 1GB
max_wal_size = 4GB
```

挂载到容器:
```yaml
postgres:
  volumes:
    - ./postgresql.conf:/etc/postgresql/postgresql.conf:ro
  command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

### 2. Redis 优化

```yaml
redis:
  command: >
    redis-server
    --maxmemory 2gb
    --maxmemory-policy allkeys-lru
    --save 900 1
    --save 300 10
    --save 60 10000
    --appendonly yes
    --appendfsync everysec
```

### 3. Go 服务优化

设置环境变量:
```yaml
go-proxy-1:
  environment:
    - GOGC=100
    - GOMAXPROCS=4
```

### 4. Python 服务优化

```yaml
python-recall-1:
  command: >
    uvicorn src.api_server:app
    --host 0.0.0.0
    --port 8000
    --workers 4
    --loop uvloop
    --limit-concurrency 1000
```

### 5. Nginx 优化

```nginx
# 添加到 nginx.conf http 块
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # 启用 Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;
    
    # 连接优化
    keepalive_timeout 65;
    keepalive_requests 100;
    
    # 缓冲区优化
    client_body_buffer_size 1M;
    client_max_body_size 50M;
    client_header_buffer_size 4k;
    large_client_header_buffers 4 8k;
}
```

## 监控和日志

### 1. 日志收集

#### 集中日志目录

```bash
sudo mkdir -p /var/log/contextproxy
```

修改 `docker-compose.yml`:
```yaml
services:
  go-proxy-1:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
        labels: "service=go-proxy"
```

#### 查看日志

```bash
# 实时日志
docker-compose logs -f --tail=100 go-proxy-1

# 查看错误日志
docker-compose logs --tail=1000 | grep ERROR

# 导出日志
docker-compose logs --no-color > contextproxy-logs-$(date +%Y%m%d).log
```

### 2. Prometheus 告警规则

创建 `alert.rules.yml`:

```yaml
groups:
  - name: contextproxy
    interval: 30s
    rules:
      # 高错误率告警
      - alert: HighErrorRate
        expr: rate(contextproxy_upstream_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "高错误率: {{ $value }}"
          description: "服务错误率超过 5%"

      # 高延迟告警
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(contextproxy_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 延迟: {{ $value }}s"
          description: "请求延迟过高"

      # 服务宕机告警
      - alert: ServiceDown
        expr: up{job="go-proxy"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务宕机: {{ $labels.instance }}"
```

挂载到 Prometheus:
```yaml
prometheus:
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - ./alert.rules.yml:/etc/prometheus/alert.rules.yml:ro
```

### 3. Grafana 配置

访问 `http://localhost:3000`，创建仪表盘:

**关键指标面板**:

1. **QPS 监控**:
```promql
sum(rate(contextproxy_requests_total[1m])) by (status)
```

2. **P99 延迟**:
```promql
histogram_quantile(0.99, 
  sum(rate(contextproxy_request_duration_seconds_bucket[5m])) by (le)
)
```

3. **错误率**:
```promql
sum(rate(contextproxy_upstream_errors_total[5m])) / 
sum(rate(contextproxy_requests_total[5m])) * 100
```

4. **召回触发率**:
```promql
sum(rate(contextproxy_recall_triggered_total[5m])) / 
sum(rate(contextproxy_requests_total[5m])) * 100
```

## 备份和恢复

### 1. PostgreSQL 备份

#### 自动备份脚本

创建 `backup-postgres.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER="contextproxy-postgres"

mkdir -p $BACKUP_DIR

# 备份所有数据库
docker exec $CONTAINER pg_dumpall -U admin | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# 保留最近 30 天的备份
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/backup_$DATE.sql.gz"
```

添加定时任务:
```bash
sudo chmod +x backup-postgres.sh
sudo crontab -e
# 每天凌晨 3 点备份
0 3 * * * /path/to/backup-postgres.sh >> /var/log/postgres-backup.log 2>&1
```

#### 恢复数据库

```bash
# 从备份恢复
gunzip < backup_20260804_030000.sql.gz | \
docker exec -i contextproxy-postgres psql -U admin
```

### 2. Redis 备份

Redis 已配置 AOF 持久化，数据自动保存到 `redis-data` 卷。

手动备份:
```bash
# 触发 RDB 快照
docker exec contextproxy-redis redis-cli BGSAVE

# 复制 RDB 文件
docker cp contextproxy-redis:/data/dump.rdb ./backup-redis-$(date +%Y%m%d).rdb
```

## 故障排查

### 常见问题

#### 1. 服务启动失败

```bash
# 查看详细日志
docker-compose logs --tail=100 go-proxy-1

# 检查端口占用
sudo netstat -tuln | grep -E '80|8080|5432|6379'

# 重启单个服务
docker-compose restart go-proxy-1
```

#### 2. 数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose exec postgres pg_isready -U admin

# 进入数据库
docker-compose exec postgres psql -U admin -d contextproxy

# 检查连接数
SELECT count(*) FROM pg_stat_activity;
```

#### 3. Redis 内存溢出

```bash
# 检查内存使用
docker-compose exec redis redis-cli INFO memory

# 清理过期键
docker-compose exec redis redis-cli FLUSHDB

# 调整 maxmemory
docker-compose exec redis redis-cli CONFIG SET maxmemory 2gb
```

#### 4. Python 服务 OOM

```bash
# 检查内存使用
docker stats contextproxy-python-1

# 重启服务
docker-compose restart python-recall-1

# 增加内存限制（docker-compose.yml）
python-recall-1:
  deploy:
    resources:
      limits:
        memory: 4G
```

### 调试模式

启用详细日志:

```yaml
go-proxy-1:
  environment:
    - LOG_LEVEL=debug

python-recall-1:
  environment:
    - LOG_LEVEL=debug
```

## 性能基准

### 预期性能指标

| 场景 | QPS | P99 延迟 | 内存占用 |
|------|-----|---------|---------|
| 小请求 (<10K tokens) | 1200+ | <100ms | ~6GB |
| 大请求 (>400K tokens) | 150+ | <500ms | ~8GB |
| 混合负载 (80% 小, 20% 大) | 900+ | <150ms | ~7GB |

### 压力测试脚本

创建 `test-small.json`:
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "stream": false
}
```

运行测试:
```bash
ab -n 10000 -c 100 \
   -p test-small.json \
   -T application/json \
   -H "Authorization: Bearer sk-test" \
   http://localhost/sk-test-001/https%3A%2F%2Fapi.openai.com/v1/chat/completions
```

## 总结

按照本指南，你应该能够:

- ✅ 部署完整的生产环境
- ✅ 配置 HTTPS 和安全策略
- ✅ 优化系统性能
- ✅ 设置监控和告警
- ✅ 配置自动备份
- ✅ 排查常见故障

如有问题，请参考 [README.md](./README.md) 或提交 Issue。
