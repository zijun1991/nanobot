#!/bin/bash
# 更新 venv 依赖
# 用法: ./scripts/update-venv.sh

set -e

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

# 检查 venv 是否存在
if [ ! -d "./venv" ]; then
    log_error "venv 目录不存在，请先运行 ./scripts/setup-venv.sh"
    exit 1
fi

# 检查 pyproject.toml 是否变化
if [ -f "./venv/.pyproject.md5" ]; then
    CURRENT_MD5=$(md5sum pyproject.toml | cut -d' ' -f1)
    OLD_MD5=$(cat ./venv/.pyproject.md5)

    if [ "$CURRENT_MD5" = "$OLD_MD5" ]; then
        log_info "pyproject.toml 未变化，无需更新"
        log_info "如需强制更新，请删除 ./venv/.pyproject.md5 后重试"
        exit 0
    fi
fi

log_info "检测到依赖变化，开始更新 venv..."

# 备份当前 venv
BACKUP_DIR="./venv.backup.$(date +%Y%m%d_%H%M%S)"
log_info "备份当前 venv 到 $BACKUP_DIR..."
cp -r ./venv "$BACKUP_DIR"

# 重建 venv
log_info "重新构建 venv..."
./scripts/setup-venv.sh

if [ $? -eq 0 ]; then
    # 保存新的 pyproject.toml MD5
    md5sum pyproject.toml > ./venv/.pyproject.md5

    log_info "venv 更新成功！"
    log_info "旧 venv 已备份到: $BACKUP_DIR"
    log_info "建议重启所有实例: docker-compose restart"
else
    log_error "venv 更新失败，正在恢复备份..."
    rm -rf ./venv
    mv "$BACKUP_DIR" ./venv
    log_error "已恢复到旧版本 venv"
    exit 1
fi
