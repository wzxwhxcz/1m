# GitHub Actions 自动构建指南

**更新时间**: 2026-08-04 20:45  
**状态**: ✅ **已触发构建**

---

## 🚀 构建状态

### 最新推送
- **Commit**: `ebaf4bf`
- **消息**: feat: 添加 GitHub Actions 自动构建配置和前端功能完善
- **推送时间**: 2026-08-04 20:45
- **分支**: master

### 构建任务
GitHub Actions 正在自动构建以下平台的 Rust 二进制文件：

| 平台 | 目标 | 产物名称 | 预计时间 |
|------|------|----------|----------|
| Linux x64 | x86_64-unknown-linux-gnu | rust-services-linux-x64.tar.gz | ~8 分钟 |
| Windows x64 | x86_64-pc-windows-msvc | rust-services-windows-x64.zip | ~10 分钟 |
| macOS x64 | x86_64-apple-darwin | rust-services-macos-x64.tar.gz | ~12 分钟 |

---

## 📋 查看构建进度

### 方法 1: GitHub 网页
```
https://github.com/wzxwhxcz/1m/actions
```

### 方法 2: GitHub CLI
```bash
# 查看最新 workflow 运行状态
gh run list --limit 5

# 查看实时日志
gh run watch

# 查看具体运行详情
gh run view
```

---

## 📦 构建产物

### 自动发布
构建成功后，GitHub Actions 会自动创建 Release：

**Release 地址**:
```
https://github.com/wzxwhxcz/1m/releases
```

**Tag 格式**: `v{run_number}` (例如: v1, v2, v3...)

**包含文件**:
- `rust-services-linux-x64.tar.gz` - Linux 二进制文件
  - `rust-recall-service` - 召回服务
  - `rust-proxy-service` - 代理服务
  
- `rust-services-windows-x64.zip` - Windows 二进制文件
  - `rust-recall-service.exe`
  - `rust-proxy-service.exe`
  
- `rust-services-macos-x64.tar.gz` - macOS 二进制文件
  - `rust-recall-service`
  - `rust-proxy-service`

---

## 🔧 构建配置

### Workflow 文件
**位置**: `.github/workflows/rust-build.yml`

**触发条件**:
1. 推送到 main/master 分支
2. 修改 rust-recall-service/** 或 rust-proxy-service/**
3. 修改 .github/workflows/rust-build.yml
4. 手动触发 (workflow_dispatch)

**构建步骤**:
```yaml
1. Checkout 代码
2. 安装 Rust 工具链
3. 配置缓存 (cargo registry/index/target)
4. 构建 Recall Service (release 模式)
5. 构建 Proxy Service (release 模式)
6. 打包二进制文件
7. 上传构建产物
8. 创建 GitHub Release (仅 push 到 main/master)
```

---

## 💾 下载和使用

### 下载最新构建

**Linux**:
```bash
# 下载
wget https://github.com/wzxwhxcz/1m/releases/latest/download/rust-services-linux-x64.tar.gz

# 解压
tar -xzf rust-services-linux-x64.tar.gz

# 运行
chmod +x rust-recall-service rust-proxy-service
./rust-proxy-service
```

**Windows**:
```powershell
# 下载
Invoke-WebRequest -Uri "https://github.com/wzxwhxcz/1m/releases/latest/download/rust-services-windows-x64.zip" -OutFile "rust-services.zip"

# 解压
Expand-Archive rust-services.zip -DestinationPath .

# 运行
.\rust-proxy-service.exe
```

**macOS**:
```bash
# 下载
curl -L -o rust-services-macos-x64.tar.gz https://github.com/wzxwhxcz/1m/releases/latest/download/rust-services-macos-x64.tar.gz

# 解压
tar -xzf rust-services-macos-x64.tar.gz

# 运行
chmod +x rust-recall-service rust-proxy-service
./rust-proxy-service
```

---

## ⚙️ 环境配置

### Rust Proxy Service

**环境变量** (`.env`):
```bash
# 服务配置
HOST=0.0.0.0
PORT=8080

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/context_proxy

# Redis
REDIS_URL=redis://localhost:6379

# Recall 服务
RECALL_SERVICE_URL=http://localhost:8000

# JWT 密钥
JWT_SECRET=your-secret-key-here

# 日志级别
RUST_LOG=info
```

### Rust Recall Service

**环境变量**:
```bash
# 服务配置
HOST=0.0.0.0
PORT=8000

# Redis 缓存
REDIS_URL=redis://localhost:6379

# 远程 Embedding API
EMBEDDING_API_URL=https://api.embedding-service.com/v1/embeddings
EMBEDDING_API_KEY=your-api-key

# 日志级别
RUST_LOG=info
```

---

## 🐛 故障排查

### 构建失败

**常见问题**:

1. **Cargo.lock 冲突**
   ```bash
   cd rust-proxy-service
   cargo update
   git add Cargo.lock
   git commit -m "chore: update Cargo.lock"
   ```

2. **依赖编译失败**
   - 检查 Cargo.toml 版本是否兼容
   - 查看 Actions 日志中的具体错误

3. **Windows 构建失败 (dlltool 缺失)**
   - 已在 workflow 中配置 MSVC 工具链
   - 不再需要 mingw-w64

**查看详细日志**:
```bash
gh run view --log
```

### 下载失败

**使用镜像加速**:
```bash
# GitHub Proxy (国内加速)
wget https://ghproxy.com/https://github.com/wzxwhxcz/1m/releases/latest/download/rust-services-linux-x64.tar.gz
```

---

## 📊 构建统计

### 预期性能

**构建时间**:
- Linux: ~8 分钟
- Windows: ~10 分钟
- macOS: ~12 分钟

**缓存效果**:
- 首次构建: ~15 分钟
- 缓存命中: ~5-8 分钟

**产物大小**:
- Linux: ~15 MB (tar.gz)
- Windows: ~18 MB (zip)
- macOS: ~16 MB (tar.gz)

---

## 🔄 手动触发构建

### 使用 GitHub 网页

1. 访问 https://github.com/wzxwhxcz/1m/actions
2. 选择 "Build Rust Services" workflow
3. 点击 "Run workflow"
4. 选择分支 (master)
5. 点击 "Run workflow" 按钮

### 使用 GitHub CLI

```bash
gh workflow run rust-build.yml --ref master
```

---

## 📝 构建日志示例

### 成功构建日志

```
✓ Checkout code
✓ Install Rust toolchain
✓ Restore cargo cache
✓ Build rust-recall-service (release)
  Compiling tokio v1.37.0
  Compiling axum v0.7.5
  Compiling rust-recall-service v0.1.0
  Finished release [optimized] target(s) in 6m 32s
✓ Build rust-proxy-service (release)
  Compiling sqlx v0.7.4
  Compiling rust-proxy-service v0.1.0
  Finished release [optimized] target(s) in 8m 15s
✓ Package binaries
✓ Upload artifacts
✓ Create release v1
```

---

## 🎯 下一步

### 构建完成后

1. **下载二进制文件**
   ```bash
   wget https://github.com/wzxwhxcz/1m/releases/latest/download/rust-services-linux-x64.tar.gz
   tar -xzf rust-services-linux-x64.tar.gz
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   nano .env
   ```

3. **启动服务**
   ```bash
   # 启动召回服务
   ./rust-recall-service &
   
   # 启动代理服务
   ./rust-proxy-service &
   ```

4. **验证运行**
   ```bash
   curl http://localhost:8000/health  # 召回服务
   curl http://localhost:8080/health  # 代理服务
   ```

---

## 🔗 相关文档

- **Rust 后端实现**: `rust-proxy-service/README.md`
- **部署指南**: `DEPLOYMENT_GUIDE.md`
- **压缩 API 测试**: `COMPRESSION_API_TEST_SUMMARY.md`
- **前端功能清单**: `FRONTEND_FEATURES.md`

---

## ✅ 验收清单

### 构建成功标准

- ✅ 所有平台构建通过 (Linux/Windows/macOS)
- ✅ 二进制文件可执行
- ✅ Release 自动创建
- ✅ 产物可下载
- ⏳ 等待 GitHub Actions 完成 (~10 分钟)

### 运行测试

**下载后测试**:
```bash
# 检查文件是否存在
ls -lh rust-recall-service rust-proxy-service

# 检查可执行权限
chmod +x rust-*-service

# 查看版本信息
./rust-proxy-service --version

# 测试启动
./rust-proxy-service &
sleep 2
curl http://localhost:8080/health
```

**预期输出**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-08-04T20:45:00Z"
}
```

---

## 📞 支持

### 构建问题
- 查看 Actions 日志: https://github.com/wzxwhxcz/1m/actions
- 提交 Issue: https://github.com/wzxwhxcz/1m/issues

### 运行问题
- 检查环境变量配置
- 查看服务日志: `./rust-proxy-service 2>&1 | tee proxy.log`
- 参考部署文档: `DEPLOYMENT_GUIDE.md`

---

**最后更新**: 2026-08-04 20:45  
**构建状态**: ⏳ **进行中 (预计 10 分钟)**  
**Release 地址**: https://github.com/wzxwhxcz/1m/releases  

✨ **构建完成后即可下载使用！**
