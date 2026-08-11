# 1M Context Compression Proxy - 快速启动指南

## 本地运行（SQLite 版本）

### 前置条件
- 无需 PostgreSQL，使用 SQLite 本地数据库
- 无需 Redis（可选）
- Python Recall 服务可选

### 快速启动步骤

1. **初始化数据库**（已完成）
   ```bash
   python init-db.py
   ```
   
2. **配置环境变量**
   ```bash
   # .env 文件已创建，默认配置：
   DATABASE_URL=sqlite://proxy.db
   REDIS_URL=redis://localhost:6379  # 可选
   PYTHON_RECALL_URLS=http://localhost:8001  # 可选
   JWT_SECRET=your-secret-key-change-in-production
   ```

3. **等待构建完成**
   当前正在等待 GitHub Actions 构建包含 SQLite 支持的新版本二进制文件。
   
   构建完成后会生成：
   - `proxy-server-linux-x86_64`（Linux 版本）
   - `proxy-server-windows-x86_64.exe`（Windows 版本）

4. **下载并运行**
   ```bash
   # 从 GitHub Actions artifacts 下载二进制文件
   # 或者本地编译：
   cargo build --release --features sqlite
   
   # 运行服务
   ./proxy-server
   ```

5. **访问管理后台**
   ```
   http://localhost:8080/admin
   
   默认账号：admin
   默认密码：admin123
   ```

## 测试用 Service Keys

- `sk-test-demo-key-12345678`（免费版，1000次/天）
- `sk-test-basic-key-11111111`（基础版，5000次/天）
- `sk-test-premium-key-22222222`（高级版，20000次/天）
- `sk-test-enterprise-key-33333333`（企业版，100000次/天）

## 使用示例

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-test-demo-key-12345678" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

## 当前状态

✅ 数据库已初始化（proxy.db）
✅ 配置文件已准备（.env）
✅ 测试账号已创建
⏳ 等待 GitHub Actions 构建新版本二进制文件

## 下一步

1. 等待 Actions 构建完成
2. 下载对应平台的二进制文件
3. 启动服务并测试
4. （可选）启动前端管理界面
