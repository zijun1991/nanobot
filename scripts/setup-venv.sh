#!/bin/bash
# 构建 venv 虚拟环境并提取到本地
# 用法: ./scripts/setup-venv.sh [输出目录]

set -e

# 默认输出目录
VENV_OUTPUT_DIR="${1:-./venv}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 是否可用
if ! command -v docker &> /dev/null; then
    log_error "Docker 未安装或不在 PATH 中"
    exit 1
fi

log_info "开始构建 venv builder 镜像..."

# 构建 venv-builder 目标
if ! docker build --target venv-builder -t nanobot:venv .; then
    log_error "venv builder 镜像构建失败"
    exit 1
fi

log_info "venv builder 镜像构建成功"

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

log_info "从容器中提取 venv.tar.gz..."

# 提取 venv.tar.gz
if ! docker run --rm nanobot:venv cat /venv.tar.gz > "$TEMP_DIR/venv.tar.gz"; then
    log_error "提取 venv.tar.gz 失败"
    exit 1
fi

# 检查 tar.gz 是否有效
if ! tar -tzf "$TEMP_DIR/venv.tar.gz" > /dev/null 2>&1; then
    log_error "venv.tar.gz 不是有效的 tar 文件"
    exit 1
fi

VENV_SIZE=$(du -h "$TEMP_DIR/venv.tar.gz" | cut -f1)
log_info "venv.tar.gz 提取成功（大小: $VENV_SIZE）"

# 创建输出目录
mkdir -p "$VENV_OUTPUT_DIR"

log_info "解压 venv 到 $VENV_OUTPUT_DIR..."

# 解压 venv
if ! tar xzf "$TEMP_DIR/venv.tar.gz" -C "$VENV_OUTPUT_DIR" --strip-components=1; then
    log_error "解压 venv 失败"
    exit 1
fi

# 验证 venv
if [ ! -f "$VENV_OUTPUT_DIR/bin/python" ]; then
    log_error "venv 中未找到 Python 解释器"
    exit 1
fi

# 生成版本锁定文件
log_info "生成版本锁定文件..."

cat > "$VENV_OUTPUT_DIR/VERSION.txt" << EOF
Nanobot venv Build Info
========================
Build Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Build Host: $(hostname)
Docker Image: nanobot:venv

Python Version: $($VENV_OUTPUT_DIR/bin/python --version)

Nanobot Version: $($VENV_OUTPUT_DIR/bin/pip show nanobot 2>/dev/null | grep Version | cut -d' ' -f2-)

Dependency Hash: $(find $VENV_OUTPUT_DIR/lib -type f -name "*.dist-info" | sort | md5sum | cut -d' ' -f1)
EOF

# 复制 venv.tar.gz 到项目根目录（供备份使用）
cp "$TEMP_DIR/venv.tar.gz" ./venv.tar.gz

log_info "venv 构建完成！"
log_info "venv 位置: $VENV_OUTPUT_DIR"
log_info "venv.tar.gz: ./venv.tar.gz"
log_info "版本信息: $VENV_OUTPUT_DIR/VERSION.txt"

# 验证测试
log_info "运行验证测试..."
if $VENV_OUTPUT_DIR/bin/python -c "import nanobot; print('✓ nanobot 导入成功')" 2>/dev/null; then
    log_info "venv 验证通过！"
else
    log_warn "venv 验证失败，请检查依赖安装"
fi

echo ""
log_info "下一步操作："
echo "  1. 构建运行时镜像: docker build -f Dockerfile.multi-instance -t nanobot:latest ."
echo "  2. 创建实例: ./scripts/create-instance.sh <instance-name> <port>"
echo "  3. 启动实例: docker-compose up -d"
