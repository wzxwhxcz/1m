#!/bin/bash
# 下载并安装 MinGW-w64 工具链

MINGW_URL="https://github.com/niXman/mingw-builds-binaries/releases/download/14.2.0-rt_v12-rev0/x86_64-14.2.0-release-posix-seh-msvcrt-rt_v12-rev0.7z"
MINGW_DIR="$HOME/.mingw64"

echo "📦 下载 MinGW-w64..."
mkdir -p "$MINGW_DIR"

# 检查是否已安装 7z
if ! command -v 7z &> /dev/null; then
    echo "❌ 需要安装 7-Zip"
    echo "   下载: https://www.7-zip.org/download.html"
    exit 1
fi

# 下载并解压
curl -L "$MINGW_URL" -o /tmp/mingw.7z
7z x /tmp/mingw.7z -o"$MINGW_DIR" -y

# 添加到 PATH
export PATH="$MINGW_DIR/mingw64/bin:$PATH"

echo "✅ MinGW-w64 已安装到: $MINGW_DIR"
echo "   请运行: export PATH=\"$MINGW_DIR/mingw64/bin:\$PATH\""
