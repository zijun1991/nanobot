#!/bin/bash
# 查看所有 nanobot 实例状态

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检查是否有运行中的容器
CONTAINERS=$(docker ps -a --filter "name=nanobot-" --format "{{.Names}}" 2>/dev/null)

if [ -z "$CONTAINERS" ]; then
    echo -e "${YELLOW}未找到 nanobot 实例${NC}"
    echo ""
    echo "提示:"
    echo "  1. 确保已构建镜像: docker build -f Dockerfile.multi-instance -t nanobot:latest ."
    echo "  2. 创建实例: ./scripts/create-instance.sh <name>"
    echo "  3. 启动实例: docker-compose up -d"
    exit 0
fi

echo -e "${BLUE}Nanobot 实例状态${NC}"
echo "========================================"

for container in $CONTAINERS; do
    # 获取容器状态
    STATUS=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)

    # 获取端口映射
    PORT=$(docker port "$container" 18790 2>/dev/null | cut -d':' -f2)

    # 获取实例名
    INSTANCE_NAME=$(echo "$container" | sed 's/nanobot-//')

    # 显示状态
    if [ "$STATUS" = "running" ]; then
        echo -e "  ${GREEN}✓${NC} $INSTANCE_NAME (port ${PORT:-N/A}) - ${GREEN}running${NC}"
    else
        echo -e "  ${RED}✗${NC} $INSTANCE_NAME (port ${PORT:-N/A}) - ${RED}$STATUS${NC}"
    fi
done

echo "========================================"
echo ""

# 显示资源使用情况
RUNNING_CONTAINERS=$(docker ps --filter "name=nanobot-" --format "{{.Names}}")
if [ -n "$RUNNING_CONTAINERS" ]; then
    echo -e "${BLUE}资源使用情况${NC}"
    echo "----------------------------------------"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        $(echo $RUNNING_CONTAINERS | tr '\n' ' ') 2>/dev/null || echo "无法获取资源信息"
    echo "========================================"
fi
