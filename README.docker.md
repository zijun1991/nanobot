# Nanobot Docker 多实例部署指南

## 概述

本方案支持使用 Docker 快速部署多个独立的 Nanobot 实例，每个实例具有不同的人格和配置。

## 架构特点

- **多阶段构建**: 分离构建环境和运行时环境
- **共享 venv**: 多个实例共享同一个虚拟环境（只读挂载）
- **资源高效**: N 实例仅需 1 份 Python + 依赖副本
- **完全隔离**: 每个实例独立配置、数据、端口
- **快速部署**: 预构建 venv，容器启动即用

## 镜像大小对比

| 方案 | 单实例大小 | N 实例总大小 | 说明 |
|------|-----------|-------------|------|
| 传统方式（镜像含 Python） | ~450MB | N × 450MB | 每个镜像重复包含 Python |
| 方案 A（Python 基础镜像 + venv 挂载） | ~150MB | N × 150MB + 300MB | 仍重复包含系统 Python |
| **本方案（Debian Slim + venv 挂载）** | **~80MB** | **80MB + 300MB** | venv 已含 Python，运行时不重复 |

**实际优势**:
- 10 实例节省 ~3.3GB（vs 传统方式）
- 10 实例额外节省 ~630MB（vs 方案 A）

## 快速开始

### 1. 构建 venv 虚拟环境

首次使用需要构建包含 Python 3.12 和所有依赖的 venv：

```bash
./scripts/setup-venv.sh
```

**输出**:
- `./venv/` - 虚拟环境目录（~300MB）
- `./venv.tar.gz` - venv 压缩包（~200MB）
- `./venv/VERSION.txt` - 版本锁定文件

**验证**:
```bash
./venv/bin/python -c "import nanobot; print('✓ OK')"
```

### 2. 构建运行时镜像

```bash
docker build -f Dockerfile.multi-instance -t nanobot:latest .
```

**预期结果**:
- 构建时间: 1-2 分钟
- 镜像大小: ~80MB（不含 Python）
- 验证无系统 Python: `docker run nanobot:latest which python`（应该为空）

### 3. 创建实例

**交互式创建**:
```bash
./scripts/create-instance.sh alice 18790
```

**命令行参数**:
```bash
./scripts/create-instance.sh <instance-name> [port] [model]
```

**示例**:
```bash
./scripts/create-instance.sh alice 18790 gpt-4o-mini
./scripts/create-instance.sh bob 18791 claude-3-5-sonnet
./scripts/create-instance.sh expert 18792
```

**创建流程**:
1. 选择人格模板（assistant/expert/creative/custom）
2. 创建目录结构
3. 生成配置文件
4. 更新 docker-compose.yml

### 4. 配置实例

编辑实例配置文件：

```bash
nano instances/alice/config/config.json
```

**配置示例**:
```json
{
  "model": "gpt-4o-mini",
  "api_key": "your-api-key-here",
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
```

**自定义人格**:
```bash
nano instances/alice/workspace/SOUL.md
```

### 5. 启动实例

**启动所有实例**:
```bash
docker-compose up -d
# 或
./scripts/start-all.sh
```

**启动特定实例**:
```bash
docker-compose up -d alice
```

### 6. 查看状态

```bash
./scripts/status.sh
```

**输出示例**:
```
Nanobot 实例状态
========================================
  ✓ alice (port 18790) - running
  ✓ bob (port 18791) - running
========================================

资源使用情况
----------------------------------------
Nanobot Instance   CPU %   Mem Usage / Limit
nanobot-alice      0.50%   150MiB / 8GiB
nanobot-bob        0.45%   145MiB / 8GiB
========================================
```

## 实例管理

### 查看日志

**单个实例**:
```bash
docker-compose logs -f alice
```

**所有实例**:
```bash
docker-compose logs -f
```

### 进入容器

```bash
docker exec -it nanobot-alice bash
```

### 停止实例

**单个实例**:
```bash
docker-compose stop alice
```

**所有实例**:
```bash
./scripts/stop-all.sh
# 或
docker-compose down
```

### 重启实例

```bash
docker-compose restart alice
```

### 删除实例

```bash
docker-compose down -v alice
rm -rf instances/alice
```

**注意**: 这会删除实例的数据和配置，请谨慎操作。

## venv 管理

### 更新 venv

当 `pyproject.toml` 变化时更新 venv：

```bash
./scripts/update-venv.sh
```

**流程**:
1. 检测 `pyproject.toml` MD5 变化
2. 备份当前 venv
3. 重建 venv
4. 恢复或更新版本锁定文件

### 强制更新

```bash
rm ./venv/.pyproject.md5
./scripts/update-venv.sh
```

## 目录结构

```
project/
├── Dockerfile.multi-instance      # 多阶段构建文件
├── docker-compose.yml              # 多实例编排配置
├── .dockerignore                   # Docker 构建排除规则
├── README.docker.md                # 本文档
├── scripts/
│   ├── setup-venv.sh              # 构建 venv 脚本
│   ├── update-venv.sh             # 更新 venv 脚本
│   ├── create-instance.sh         # 创建实例脚本
│   ├── start-all.sh               # 启动所有实例
│   ├── stop-all.sh                # 停止所有实例
│   └── status.sh                  # 查看实例状态
├── docker/
│   ├── config-template.json       # 配置模板
│   └── souls/
│       ├── assistant.md           # 助手人格
│       ├── expert.md              # 专家人格
│       └── creative.md            # 创意人格
├── venv/                          # 共享虚拟环境（生成）
│   ├── bin/                       # Python 和可执行文件
│   ├── lib/                       # Python 库
│   └── VERSION.txt                # 版本信息
├── venv.tar.gz                    # venv 压缩包（生成）
└── instances/
    ├── alice/
    │   ├── config/
    │   │   ├── config.json        # 实例配置
    │   │   └── sessions/          # 会话存储
    │   ├── workspace/
    │   │   ├── SOUL.md            # 人格定义
    │   │   ├── AGENTS.md
    │   │   ├── memory/            # 记忆存储
    │   │   └── skills/            # 技能定义
    │   ├── docker-compose.override.yml
    │   └── INSTANCE_INFO.txt      # 实例信息
    └── bob/
        └── ...
```

## 人格模板

### Assistant（助手）

**特点**: 友好、专业的个人助理

**适用场景**: 日常事务协助、信息查询、任务管理

**创建**:
```bash
./scripts/create-instance.sh my-assistant 18790 gpt-4o-mini
# 选择: 1) assistant
```

### Expert（专家）

**特点**: 技术专家、深度分析

**适用场景**: 编程、系统架构、技术咨询

**创建**:
```bash
./scripts/create-instance.sh my-expert 18791 claude-3-5-sonnet
# 选择: 2) expert
```

### Creative（创意）

**特点**: 富有创造力、艺术气息

**适用场景**: 创意写作、头脑风暴、设计思维

**创建**:
```bash
./scripts/create-instance.sh my-creative 18792 gpt-4o
# 选择: 3) creative
```

### Custom（自定义）

**特点**: 完全自定义人格

**适用场景**: 特定需求、个性化定制

**创建**:
```bash
./scripts/create-instance.sh my-custom 18793
# 选择: 4) custom
```

## 验证测试

### 完整验证流程

```bash
# 1. 验证 venv
./venv/bin/python -c "import nanobot; print('✓ venv OK')"

# 2. 验证镜像大小
docker images nanobot:latest
# 预期: ~80MB

# 3. 验证无系统 Python
docker run nanobot:latest which python
# 预期: 为空

# 4. 验证 venv 中的 Python
docker run -v $(pwd)/venv:/opt/venv:ro nanobot:latest /opt/venv/bin/python --version
# 预期: Python 3.12.x

# 5. 创建测试实例
./scripts/create-instance.sh test-instance 18999

# 6. 启动测试实例
docker-compose up -d test-instance

# 7. 查看实例状态
docker ps | grep test-instance

# 8. 测试 API（假设暴露 18999 端口）
curl http://localhost:18999/health

# 9. 查看日志
docker-compose logs test-instance

# 10. 清理测试实例
docker-compose down -v test-instance
rm -rf instances/test-instance
```

## 故障排查

### 问题 1: venv 构建失败

**症状**: `./scripts/setup-venv.sh` 报错

**可能原因**:
- Docker 未运行
- 网络问题导致依赖下载失败
- 磁盘空间不足

**解决方案**:
```bash
# 检查 Docker 状态
docker ps

# 清理 Docker 缓存
docker system prune -af

# 重试构建
./scripts/setup-venv.sh
```

### 问题 2: 容器启动失败

**症状**: `docker-compose up -d` 报错

**可能原因**:
- venv 未正确挂载
- 端口冲突
- 配置文件错误

**解决方案**:
```bash
# 检查 venv 是否存在
ls -la venv/bin/python

# 检查端口占用
netstat -tuln | grep 18790

# 查看详细日志
docker-compose logs alice

# 验证配置文件
cat instances/alice/config/config.json | jq .
```

### 问题 3: 实例无法连接

**症状**: 无法访问实例 API

**可能原因**:
- 端口映射错误
- 防火墙阻止
- 实例未启动

**解决方案**:
```bash
# 检查端口映射
docker port nanobot-alice

# 检查实例状态
./scripts/status.sh

# 测试容器内部网络
docker exec nanobot-alice curl http://localhost:18790/health
```

### 问题 4: 依赖导入错误

**症状**: `ModuleNotFoundError: No module named 'xxx'`

**可能原因**:
- venv 不完整
- pyproject.toml 变化后未更新 venv

**解决方案**:
```bash
# 重新构建 venv
./scripts/setup-venv.sh

# 或更新 venv
./scripts/update-venv.sh

# 重启实例
docker-compose restart
```

## 高级配置

### 资源限制

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  alice:
    <<: *nanobot-config
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 日志聚合

配置日志驱动：

```yaml
services:
  alice:
    <<: *nanobot-config
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 环境变量

使用 `.env` 文件管理敏感信息：

```bash
# .env
API_KEY=sk-xxx
ALICE_MODEL=gpt-4o-mini
BOB_MODEL=claude-3-5-sonnet
```

```yaml
# docker-compose.yml
services:
  alice:
    environment:
      - API_KEY=${ALICE_API_KEY}
      - MODEL=${ALICE_MODEL}
```

### 自定义网络

```yaml
networks:
  nanobot-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## 性能优化

### 1. 使用多阶段构建缓存

```bash
# 构建时使用缓存
docker build --cache-from nanobot:latest -f Dockerfile.multi-instance -t nanobot:latest .
```

### 2. 压缩 venv

```bash
# 使用更高压缩率
./venv/bin/pip freeze | xargs -n 1 ./venv/bin/pip install --no-cache-dir --compile
```

### 3. 清理不必要的依赖

编辑 `pyproject.toml`，移除不需要的依赖：

```toml
[project.optional-dependencies]
dev = ["pytest", "black", "mypy"]
```

### 4. 使用 BuildKit

```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.multi-instance -t nanobot:latest .
```

## 安全建议

1. **不要在配置文件中硬编码 API Key**，使用环境变量或 Docker secrets
2. **限制容器权限**，避免使用 `--privileged` 模式
3. **只读挂载 venv**，避免容器修改共享环境
4. **定期更新基础镜像**，获取安全补丁
5. **使用非 root 用户运行容器**（如果支持）
6. **限制网络访问**，使用防火墙规则

## 备份与恢复

### 备份实例

```bash
# 备份单个实例
tar czf alice-backup-$(date +%Y%m%d).tar.gz instances/alice/

# 备份所有实例
tar czf nanobot-backup-$(date +%Y%m%d).tar.gz instances/

# 备份 venv
cp venv.tar.gz venv-backup-$(date +%Y%m%d).tar.gz
```

### 恢复实例

```bash
# 解压备份
tar xzf alice-backup-20240101.tar.gz

# 重启实例
docker-compose up -d alice
```

## 迁移指南

### 从单实例迁移

1. **导出现有配置**:
   ```bash
   cp ~/.nanobot/config.json instances/migrated/config/
   cp -r ~/.nanobot/workspace instances/migrated/
   cp -r ~/.nanobot/sessions instances/migrated/config/
   ```

2. **创建新实例**:
   ```bash
   ./scripts/create-instance.sh migrated 18790
   ```

3. **验证迁移**:
   ```bash
   docker-compose up -d migrated
   docker-compose logs -f migrated
   ```

## 常见问题 (FAQ)

### Q: 为什么 venv 这么大？

A: venv 包含完整的 Python 3.12 解释器（~50MB）和所有依赖包（~250MB），这是为了保证完全兼容性和独立性。

### Q: 可以减小 venv 大小吗？

A: 可以尝试：
1. 使用 `pip install --no-deps` 跳过非必需依赖
2. 删除不必要的包
3. 使用更小的基础镜像（如 Alpine，但可能有兼容性问题）

### Q: 多个实例会互相影响吗？

A: 不会。每个实例有独立的配置、数据和端口，仅共享只读的 venv。

### Q: 如何升级到新版本的 Nanobot？

A:
```bash
# 1. 拉取最新代码
git pull

# 2. 更新 venv
./scripts/update-venv.sh

# 3. 重建镜像
docker build -f Dockerfile.multi-instance -t nanobot:latest .

# 4. 重启所有实例
docker-compose restart
```

### Q: 支持多少个并发实例？

A: 理论上无限制，实际数量取决于：
- 可用端口（65535 个）
- 系统资源（CPU、内存）
- 实例负载

建议监控系统资源，合理规划实例数量。

## 参考资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Nanobot 项目文档](README.md)
- [Python 虚拟环境](https://docs.python.org/3/library/venv.html)

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个部署方案！

## 许可证

与 Nanobot 项目相同。

---

**文档版本**: 1.0
**最后更新**: 2025-02-05
**维护者**: Nanobot 社区
