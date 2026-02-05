#!/bin/bash
# 创建新的 nanobot 实例
# 用法: ./scripts/create-instance.sh <instance-name> [port] [model]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_prompt() {
    echo -e "${BLUE}[PROMPT]${NC} $1"
}

# 检查参数
if [ -z "$1" ]; then
    log_error "用法: $0 <instance-name> [port] [model]"
    echo ""
    echo "参数说明:"
    echo "  instance-name: 实例名称（必需，如 alice, bob）"
    echo "  port: 端口号（可选，默认从 18790 开始自动分配）"
    echo "  model: 模型名称（可选，默认为 gpt-4o-mini）"
    echo ""
    echo "示例:"
    echo "  $0 alice 18790 gpt-4o-mini"
    echo "  $0 bob"
    exit 1
fi

INSTANCE_NAME="$1"
PORT="${2:-}"
MODEL="${3:-gpt-4o-mini}"

# 验证实例名称
if [[ ! "$INSTANCE_NAME" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    log_error "实例名称只能包含小写字母、数字和连字符，且必须以字母或数字开头和结尾"
    exit 1
fi

# 检查 venv 是否存在
if [ ! -d "./venv" ]; then
    log_error "venv 目录不存在，请先运行 ./scripts/setup-venv.sh"
    exit 1
fi

# 检查实例是否已存在
INSTANCE_DIR="./instances/$INSTANCE_NAME"
if [ -d "$INSTANCE_DIR" ]; then
    log_error "实例 $INSTANCE_NAME 已存在于 $INSTANCE_DIR"
    exit 1
fi

log_info "创建实例: $INSTANCE_NAME"

# 创建目录结构
log_info "创建目录结构..."
mkdir -p "$INSTANCE_DIR/config/sessions"
mkdir -p "$INSTANCE_DIR/workspace/memory"
mkdir -p "$INSTANCE_DIR/workspace/skills"

# 自动分配端口（如果未指定）
if [ -z "$PORT" ]; then
    # 查找已使用的最大端口
    MAX_PORT=18789
    if [ -d "./instances" ]; then
        for dir in ./instances/*/; do
            if [ -f "$dir/docker-compose.override.yml" ]; then
                DIR_PORT=$(grep -oP 'ports:.*\n.*-\s+"\K[0-9]+' "$dir/docker-compose.override.yml" | head -1)
                if [ -n "$DIR_PORT" ] && [ "$DIR_PORT" -gt "$MAX_PORT" ]; then
                    MAX_PORT=$DIR_PORT
                fi
            fi
        done
    fi
    PORT=$((MAX_PORT + 1))
    log_info "自动分配端口: $PORT"
fi

# 选择 soul 模板
log_info ""
log_info "选择人格模板:"
echo "  1) assistant - 助手人格：友好、专业的个人助理"
echo "  2) expert - 专家人格：技术专家、深度分析"
echo "  3) creative - 创意人格：富有创造力、艺术气息"
echo "  4) custom - 自定义人格"
echo ""

read -p "$(echo -e ${BLUE}"选择 [1-4] [默认: 1]: "${NC})" SOUL_CHOICE
SOUL_CHOICE=${SOUL_CHOICE:-1}

case $SOUL_CHOICE in
    1)
        SOUL_TEMPLATE="assistant"
        ;;
    2)
        SOUL_TEMPLATE="expert"
        ;;
    3)
        SOUL_TEMPLATE="creative"
        ;;
    4)
        SOUL_TEMPLATE="custom"
        ;;
    *)
        log_warn "无效选择，使用默认助手人格"
        SOUL_TEMPLATE="assistant"
        ;;
esac

# 复制或创建 SOUL.md
if [ "$SOUL_TEMPLATE" != "custom" ]; then
    if [ -f "./docker/souls/${SOUL_TEMPLATE}.md" ]; then
        cp "./docker/souls/${SOUL_TEMPLATE}.md" "$INSTANCE_DIR/workspace/SOUL.md"
        log_info "使用人格模板: $SOUL_TEMPLATE"
    else
        log_warn "未找到模板文件: ./docker/souls/${SOUL_TEMPLATE}.md"
        log_warn "将创建默认 SOUL.md"
        SOUL_TEMPLATE="custom"
    fi
fi

if [ "$SOUL_TEMPLATE" = "custom" ]; then
    log_info "创建自定义人格..."
    cat > "$INSTANCE_DIR/workspace/SOUL.md" << EOF
# ${INSTANCE_NAME^} Soul

你是一个 AI 助手，名为 **${INSTANCE_NAME^}**。

## 核心特征
- **身份**: ${INSTANCE_NAME^} AI 助手
- **模型**: $MODEL

## 个性与能力
请根据需要自定义这部分内容来定义 ${INSTANCE_name^} 的个性、专业领域和交互风格。

## 交互原则
1. 保持友好和专业
2. 提供准确和有用的信息
3. 承认知识局限性
4. 主动寻求澄清（当需要时）

---
*此文件由 create-instance.sh 自动生成*
*请根据需要编辑此文件以定义 ${INSTANCE_NAME^} 的独特人格*
EOF
fi

# 生成配置文件
log_info "生成配置文件..."

# 获取 API key（如果存在）
API_KEY=""
if [ -f "./docker/config-template.json" ]; then
    API_KEY=$(grep -oP '"api_key":\s*"\K[^"]+' ./docker/config-template.json 2>/dev/null || echo "")
fi

cat > "$INSTANCE_DIR/config/config.json" << EOF
{
  "model": "$MODEL",
  "api_key": "${API_KEY:-your-api-key-here}",
  "temperature": 0.7,
  "max_tokens": 4096,
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790
  },
  "workspace": "/data/.nanobot/workspace",
  "sessions_dir": "/data/.nanobot/sessions",
  "log_level": "INFO"
}
EOF

# 生成 docker-compose.override.yml
log_info "生成 docker-compose.override.yml..."

cat > "$INSTANCE_DIR/docker-compose.override.yml" << EOF
services:
  $INSTANCE_NAME:
    container_name: nanobot-$INSTANCE_NAME
    ports:
      - "$PORT:18790"
    environment:
      - INSTANCE_NAME=$INSTANCE_NAME
EOF

# 更新主 docker-compose.yml（追加新实例）
log_info "更新 docker-compose.yml..."

if ! grep -q "^  $INSTANCE_NAME:" docker-compose.yml 2>/dev/null; then
    # 在 bob 实例后添加新实例
    sed -i.bak "/^  bob:/a\\
\\
  # 实例: $INSTANCE_NAME\\
  $INSTANCE_NAME:\\
    <<: *nanobot-config\\
    container_name: nanobot-$INSTANCE_NAME\\
    ports:\\
      - \"$PORT:18790\"\\
    environment:\\
      - INSTANCE_NAME=$INSTANCE_NAME
" docker-compose.yml

    # 删除备份文件
    rm -f docker-compose.yml.bak
fi

# 创建实例信息文件
cat > "$INSTANCE_DIR/INSTANCE_INFO.txt" << EOF
Nanobot Instance: $INSTANCE_NAME
================================

Instance Name: $INSTANCE_NAME
Port: $PORT
Model: $MODEL
Soul Template: $SOUL_TEMPLATE
Created: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

Directory Structure:
  - config/config.json: 配置文件
  - config/sessions/: 会话存储
  - workspace/SOUL.md: 人格定义
  - workspace/memory/: 记忆存储
  - workspace/skills/: 技能定义

Quick Start:
  1. 编辑配置: nano $INSTANCE_DIR/config/config.json
  2. 自定义人格: nano $INSTANCE_DIR/workspace/SOUL.md
  3. 启动实例: docker-compose up -d $INSTANCE_NAME
  4. 查看日志: docker-compose logs -f $INSTANCE_NAME
  5. 进入容器: docker exec -it nanobot-$INSTANCE_NAME bash

Management:
  - 停止: docker-compose stop $INSTANCE_NAME
  - 重启: docker-compose restart $INSTANCE_NAME
  - 删除: docker-compose down -v $INSTANCE_NAME

Generated by: create-instance.sh
EOF

log_info "实例创建完成！"
echo ""
log_info "实例信息:"
echo "  名称: $INSTANCE_NAME"
echo "  端口: $PORT"
echo "  模型: $MODEL"
echo "  人格: $SOUL_TEMPLATE"
echo ""
log_info "目录位置: $INSTANCE_DIR"
log_info "详细说明: $INSTANCE_DIR/INSTANCE_INFO.txt"
echo ""
log_info "下一步操作:"
echo "  1. 编辑配置文件: nano $INSTANCE_DIR/config/config.json"
echo "  2. 自定义人格: nano $INSTANCE_DIR/workspace/SOUL.md"
echo "  3. 启动实例: docker-compose up -d $INSTANCE_NAME"
echo "  4. 查看日志: docker-compose logs -f $INSTANCE_NAME"
