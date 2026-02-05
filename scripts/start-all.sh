#!/bin/bash
# 启动所有 nanobot 实例

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 venv 是否存在
if [ ! -d "./venv" ]; then
    log_error "venv 目录不存在，请先运行 ./scripts/setup-venv.sh"
    exit 1
fi

log_info "启动所有 nanobot 实例..."

if docker-compose up -d; then
    log_info "所有实例启动成功！"
    echo ""
    ./scripts/status.sh
else
    log_error "启动失败，请检查错误信息"
    exit 1
fi
