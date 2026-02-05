#!/bin/bash
# Nanobot Docker 启动脚本
# 检查 venv 是否挂载，然后启动服务

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查 venv 是否挂载
if [ ! -f "/opt/venv/bin/python" ]; then
    log_error "venv 未挂载！"
    log_error "请使用卷挂载: docker run -v /path/to/venv:/opt/venv:ro ..."
    exit 1
fi

# 检查 Python 是否可执行
if ! /opt/venv/bin/python --version >/dev/null 2>&1; then
    log_error "venv 中的 Python 无法执行！"
    log_error "这可能是因为宿主机的架构与容器不匹配。"
    log_error "宿主机架构: $(uname -m)"
    log_error "容器架构: $(uname -m)"
    exit 1
fi

# 显示版本信息
log_info "Nanobot Docker 容器启动"
log_info "Python 版本: $(/opt/venv/bin/python --version)"
log_info "Nanobot 版本: $(/opt/venv/bin/pip show nanobot-ai 2>/dev/null | grep Version | cut -d' ' -f2- || echo 'unknown')"

# 执行传入的命令
exec /opt/venv/bin/python "$@"
