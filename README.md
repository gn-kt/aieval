# 竞品雷达 (AgentForge)

AI 驱动的竞品分析平台 — 监控竞争对手动态，自动采集、评估、生成分析报告。

## 特性

- 竞品自动采集与追踪
- AI 评估打分体系（多维度评分规则）
- 实时 WebSocket 推送
- JWT 用户认证 + 角色权限
- 异步任务队列（Celery + Redis）
- 可视化报告看板（React + TypeScript）
- Prometheus + Grafana 监控
- Docker 容器化部署

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 数据库 | PostgreSQL |
| 缓存/队列 | Redis + Celery |
| 前端 | React + TypeScript + Vite |
| 监控 | Prometheus + Grafana |
| 部署 | Docker + Nginx |

## 快速开始

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 和数据库配置

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库
alembic upgrade head

# 4. 启动 API 服务
uvicorn api:app --reload --port 8000

# 5. 启动 Celery Worker
celery -A celery_app worker -l info

# 6. 启动前端
cd frontend && npm install && npm run dev
```

## 项目结构

```
竞品雷达/
├── api.py              # FastAPI 主入口
├── auth.py             # JWT 认证
├── models.py           # 数据模型
├── schemas.py          # Pydantic 校验
├── database.py         # 数据库连接
├── celery_app.py       # Celery 配置
├── modules/evaluator/  # 核心评估模块
├── core/llm.py         # LLM 调用封装
├── migrations/         # Alembic 迁移
├── frontend/           # React 前端
└── tests/              # 测试
```
