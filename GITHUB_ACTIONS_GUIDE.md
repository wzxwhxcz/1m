# GitHub Actions 自动构建配置

本项目配置了两个 GitHub Actions 工作流，用于自动构建和发布：

## 1. Rust 二进制构建 (rust-build.yml)

### 触发条件
- Push 到 main/master 分支
- Pull Request 到 main/master 分支
- 手动触发 (workflow_dispatch)

### 构建矩阵
自动为以下平台构建二进制文件：
- **Linux x64** (ubuntu-latest, x86_64-unknown-linux-gnu)
- **Windows x64** (windows-latest, x86_64-pc-windows-msvc)
- **macOS x64** (macos-latest, x86_64-apple-darwin)

### 构建产物
- **Linux/macOS**: `rust-services-{platform}.tar.gz`
  - 包含：`rust-recall-service` 和 `rust-proxy-service` 可执行文件
- **Windows**: `rust-services-windows-x64.zip`
  - 包含：`rust-recall-service.exe` 和 `rust-proxy-service.exe`

### 自动发布
当 push 到主分支时，会自动创建 GitHub Release：
- 标签：`v{run_number}` (例如 v123)
- 包含所有平台的二进制包

### 下载使用
```bash
# Linux
wget https://github.com/YOUR_USERNAME/YOUR_REPO/releases/latest/download/rust-services-linux-x64.tar.gz
tar -xzf rust-services-linux-x64.tar.gz
chmod +x rust-recall-service rust-proxy-service

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/YOUR_USERNAME/YOUR_REPO/releases/latest/download/rust-services-windows-x64.zip" -OutFile rust-services.zip
Expand-Archive rust-services.zip -DestinationPath .
```

## 2. Docker 镜像构建 (docker-build.yml)

### 触发条件
- Push 到 main/master 分支
- 手动触发 (workflow_dispatch)

### 构建服务
- `rust-recall-service` - Rust 召回服务
- `rust-proxy-service` - Rust 代理服务
- `admin-dashboard` - React 管理面板

### 镜像仓库
镜像推送到 GitHub Container Registry (ghcr.io)：
```
ghcr.io/YOUR_USERNAME/rust-recall-service:latest
ghcr.io/YOUR_USERNAME/rust-proxy-service:latest
ghcr.io/YOUR_USERNAME/admin-dashboard:latest
```

### 镜像标签策略
- `latest` - 主分支最新版本
- `main-{sha}` - 特定提交的镜像
- `{branch}` - 分支名称

### 拉取使用
```bash
# 登录 GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# 拉取镜像
docker pull ghcr.io/YOUR_USERNAME/rust-recall-service:latest
docker pull ghcr.io/YOUR_USERNAME/rust-proxy-service:latest
docker pull ghcr.io/YOUR_USERNAME/admin-dashboard:latest

# 更新 docker-compose.yml
# 将 build: 替换为 image: ghcr.io/YOUR_USERNAME/SERVICE_NAME:latest
```

## 缓存优化

两个工作流都启用了缓存以加速构建：

### Rust 构建缓存
- Cargo registry
- Cargo index
- Target 目录

### Docker 构建缓存
- GitHub Actions Cache (GHA)
- 最大化缓存模式 (mode=max)

## 本地测试

在推送前可以本地测试工作流：

```bash
# 安装 act (GitHub Actions 本地运行工具)
# Linux/macOS
brew install act

# Windows
choco install act-cli

# 运行 Rust 构建工作流
act -W .github/workflows/rust-build.yml

# 运行 Docker 构建工作流
act -W .github/workflows/docker-build.yml
```

## 环境变量配置

工作流使用以下环境变量：

### Rust 构建
- `CARGO_TERM_COLOR=always` - 彩色输出

### Docker 构建
- `REGISTRY=ghcr.io` - 容器镜像仓库
- `IMAGE_PREFIX=${{ github.repository_owner }}` - 镜像前缀

### Secrets
- `GITHUB_TOKEN` - 自动提供，用于推送 Release 和 Docker 镜像

## 监控构建状态

在 GitHub 仓库页面：
1. 点击 **Actions** 标签
2. 查看最近的工作流运行
3. 点击具体的运行查看详细日志
4. 下载构建产物 (Artifacts)

## 故障排查

### Rust 构建失败
1. 检查 `Cargo.toml` 依赖版本
2. 确保所有平台兼容的依赖
3. 查看具体平台的构建日志

### Docker 构建失败
1. 确保 Dockerfile 路径正确
2. 检查基础镜像可用性
3. 验证构建上下文包含所有必要文件

### 权限问题
确保仓库设置中启用了：
- Settings → Actions → General → Workflow permissions
- 选择 "Read and write permissions"
- 勾选 "Allow GitHub Actions to create and approve pull requests"
