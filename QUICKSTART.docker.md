# Nanobot Docker 多实例部署 - 快速参考

## 快速开始（3 步）

```bash
# 1. 构建 venv（首次使用）
./scripts/setup-venv.sh

# 2. 构建运行时镜像
docker build -f Dockerfile.multi-instance -t nanobot:latest .

# 3. 创建并启动实例
./scripts/create-instance.sh alice 18790
docker-compose up -d alice
```

## 常用命令

### venv 管理
```bash
./scripts/setup-venv.sh              # 构建 venv
./scripts/update-venv.sh             # 更新 venv
```

### 实例管理
```bash
./scripts/create-instance.sh <name> [port] [model]  # 创建实例
./scripts/start-all.sh               # 启动所有实例
./scripts/stop-all.sh                # 停止所有实例
./scripts/status.sh                  # 查看实例状态
```

### Docker Compose
```bash
docker-compose up -d [instance]      # 启动实例
docker-compose stop [instance]       # 停止实例
docker-compose restart [instance]    # 重启实例
docker-compose logs -f [instance]    # 查看日志
docker-compose down -v [instance]    # 删除实例
```

### 容器操作
```bash
docker exec -it nanobot-<name> bash  # 进入容器
docker port nanobot-<name> 18790     # 查看端口映射
docker stats nanobot-<name>          # 查看资源使用
```

## 目录结构

```
venv/                    # 共享虚拟环境（构建后生成）
instances/               # 实例目录
  └── <name>/
    ├── config/          # 配置和会话
    └── workspace/       # 工作空间（SOUL.md, memory, skills）
scripts/                 # 管理脚本
docker/                  # 配置模板
```

## 人格模板

- **assistant**: 友好的个人助理
- **expert**: 技术专家，深度分析
- **creative**: 富有创造力，艺术气息
- **custom**: 完全自定义

## 快速验证

```bash
./venv/bin/python -c "import nanobot; print('✓ OK')"
docker images nanobot:latest           # 应该 ~80MB
docker run nanobot:latest which python # 应该为空
./scripts/status.sh                    # 查看实例状态
```

## 故障排查

```bash
# 检查 venv
ls -la venv/bin/python

# 检查端口占用
netstat -tuln | grep 18790

# 查看详细日志
docker-compose logs <instance>

# 重建 venv
./scripts/setup-venv.sh

# 重建镜像
docker build -f Dockerfile.multi-instance -t nanobot:latest .
```

## 示例场景

### 创建 3 个不同人格的实例

```bash
# 助手人格
./scripts/create-instance.sh alice 18790 gpt-4o-mini
# 选择: 1) assistant

# 专家人格
./scripts/create-instance.sh bob 18791 claude-3-5-sonnet
# 选择: 2) expert

# 创意人格
./scripts/create-instance.sh charlie 18792 gpt-4o
# 选择: 3) creative

# 启动所有实例
docker-compose up -d
```

### 自定义人格

```bash
./scripts/create-instance.sh my-bot 18793
# 选择: 4) custom

# 编辑人格定义
nano instances/my-bot/workspace/SOUL.md

# 启动实例
docker-compose up -d my-bot
```

## 资源优势

- **镜像大小**: ~80MB（不含 Python）
- **venv 大小**: ~300MB（共享）
- **N 实例总大小**: 80MB + 300MB（vs 传统方式 N × 450MB）
- **10 实例节省**: ~3.3GB 磁盘空间

## 完整文档

详细说明请参考: [README.docker.md](README.docker.md)

---

**版本**: 1.0 | **更新**: 2025-02-05
