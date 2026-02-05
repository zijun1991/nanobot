#!/bin/bash
# 停止所有 nanobot 实例

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_info "停止所有 nanobot 实例..."

if docker-compose down; then
    log_info "所有实例已停止"
else
    log_warn "停止过程中出现错误"
    exit 1
fi
