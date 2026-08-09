# 竞品雷达

输入 GitHub 仓库 / 文字描述 → AI 五维竞争力评分 + 优化建议 + 发展方向。

## 实测数据

8 个产品 LLM-as-a-Judge 五维评测结果（2026-08-09）：

| 产品 | 综合得分 | 定位 | 差异化 | 护城河 | 工程 | 可持续 | 类型 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|------|
| **requests** (52k⭐) | **1.85** | 2 | 2 | 2 | 2 | 1 | 成熟开源 |
| **Semgrep** (11k⭐) | **1.75** | 2 | 2 | 1 | 2 | 2 | 商业开源 |
| **ruff** (47k⭐) | **1.60** | 2 | 2 | 1 | 2 | 1 | 商业开源 |
| **httpx** (14k⭐) | **1.60** | 2 | 2 | 1 | 2 | 1 | 新兴开源 |
| **flask** (68k⭐) | **1.35** | 2 | 1 | 1 | 2 | 1 | 成熟开源 |
| **LangChain** (100k⭐) | **1.20** | 2 | 1 | 1 | 1 | 1 | 商业开源 |
| **MergeGate** | **0.60** | 1 | 1 | 0 | 1 | 0 | 个人开源 |
| **竞品雷达** | **0.60** | 1 | 1 | 0 | 1 | 0 | 个人开源 |

> 得分范围 0.00-2.00。成熟商业产品 1.35-1.85，个人开源项目 0.60。五维权重：差异化 25%、护城河 25%、定位 20%、工程 15%、可持续 15%。

### 关键发现

- **护城河是最大短板**：所有开源项目的 moat 得分 ≤ 2（满分 2）。requests 凭网络效应 + 迁移成本拿到 2 分，但大部分在 0-1 分——开源项目天然护城河弱
- **可持续性拖后腿**：个人项目（MergeGate/竞品雷达）0 分——无商业模式时自动归零
- **成熟开源产品有高分区间**：requests 五维中四维满分，仅可持续性扣分。说明框架有能力区分不同成熟度的项目
- **评测一致性**：8 个产品的得分分布符合直觉——知名项目高分、个人项目低分、无异常颠倒

## 与竞品对比

| 能力 | 人工咨询 | 简单 LLM 打分 | Capterra/G2 | **竞品雷达** |
|------|:--:|:--:|:--:|:--:|
| 结构化评估框架 | — | — | — | ✅ 五维 Rubric |
| 自动采集 GitHub 数据 | — | — | — | ✅ |
| 自动搜索竞品 | — | — | — | ✅ |
| LLM-as-a-Judge | — | ✅ | — | ✅ |
| 硬阈值校准 | — | — | — | ✅ |
| 追问对话 | — | — | — | ✅ |
| 异步任务队列 | — | — | — | ✅ |
| 结构化报告 + 建议 | — | — | ✅ | ✅ |
| 可本地运行 | — | — | — | ✅ |

## 前置条件

| 组件 | 用途 | 安装 |
|------|------|------|
| Python 3.10+ | 后端运行 | — |
| PostgreSQL | 评测记录持久化 | `brew install postgresql`（macOS）/ Windows 安装包 |
| Redis | Celery 任务队列 | `brew install redis`（macOS）/ Windows 安装包 |
| npm | 前端构建 | Node.js 自带 |
| DeepSeek API Key | LLM 调用（免费额度） | [注册获取](https://platform.deepseek.com/) |

### 详细安装与验证

### 1. Python

```bash
python --version         # ≥ 3.10
pip install -r requirements.txt
```

### 2. PostgreSQL

```bash
# 安装后创建数据库
createdb -U postgres backend_dev
# 或
psql -U postgres -c "CREATE DATABASE backend_dev;"

# 验证
psql -U postgres -d backend_dev -c "SELECT 1;"
```

### 3. Redis

```bash
# macOS
brew install redis && brew services start redis

# Linux
sudo apt install redis-server && sudo systemctl start redis

# Windows: 下载解压后双击 redis-server.exe

# 验证
redis-cli ping    # 应输出 PONG
```

### 4. npm

```bash
node --version    # ≥ 16
npm --version     # ≥ 8
# 若无: https://nodejs.org/ 下载 LTS 版
```

### 5. .env 配置

```bash
cp .env.example .env
```

编辑 `.env`，必填项：

```
DEEPSEEK_API_KEY=sk-你的key          # [注册获取](https://platform.deepseek.com/)
DATABASE_URL=postgresql+asyncpg://postgres:你的密码@localhost:5432/backend_dev
REDIS_URL=redis://127.0.0.1:6379/0
```

### 6. 逐项验证

```bash
# Python 能读 .env
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('DEEPSEEK_API_KEY')[:5])"

# PostgreSQL 连通
python -c "import asyncpg,asyncio;asyncio.run(asyncpg.connect('postgresql://postgres:你的密码@localhost:5432/backend_dev'));print('ok')"

# Redis 连通
python -c "import redis;print(redis.Redis.from_url('redis://127.0.0.1:6379/0').ping())"
```

---

## 快速开始

```bash
cp .env.example .env              # 1. 填入 DEEPSEEK_API_KEY（必填）
pip install -r requirements.txt   # 2. 安装 Python 依赖
alembic upgrade head              # 3. 初始化数据库表（仅首次需要）
python 启动竞品雷达.py            # 4. 一键启动 → 浏览器自动打开 http://localhost:5173
```

> 启动脚本依次拉起 Redis → Celery Worker → FastAPI(8000) → Vite(5173)。前端依赖首次自动 `npm install`（1-2 分钟）。`Ctrl+C` 关闭全部服务。

## 使用步骤

打开 `http://localhost:5173`，页面从上到下：

### 第一步：输入评测对象（三选一）

| 方式 | 操作 | 适合场景 | 典型耗时 |
|------|------|---------|:--:|
| **GitHub URL** | 输入框粘贴仓库地址，如 `https://github.com/psf/requests` | 分析已有开源项目 | 30-60s |
| **文字描述** | 切换到"文字描述"标签，输入产品名 + 一段描述 | 还没代码、快速验证想法 | 15-30s |
| **上传文件夹** | 切换到"上传文件"标签，拖入整个项目文件夹 | 分析本地私有项目 | 30-90s |

### 第二步：查看评测结果

提交后等待任务完成，页面展示：

```
┌───────────────────────────────────────────────┐
│  综合得分 1.85 / 2.00                          │
│                                               │
│  定位 ████ 2/2   差异化 ████ 2/2              │
│  护城河 ████ 2/2   工程 ████ 2/2              │
│  可持续 ██░░ 1/2                              │
│                                               │
│  📋 优化建议                                   │
│  1. 增加商业化模式（企业版 / SaaS）提高可持续性   │
│  2. 补充竞品对比文档，强化定位                   │
│                                               │
│  🧭 发展方向                                   │
│  1. 插件生态：开放第三方扩展接入                 │
│  2. 企业功能：SSO / 审计日志 / SLA             │
└───────────────────────────────────────────────┘
```

### 第三步：追问对话

底部输入框可与 AI 继续对话，例如：
- "我的产品和 requests 差距在哪？"
- "最该优先改进哪个维度？"
- "护城河怎么从 0 分提到 2 分？"

历史记录在右侧面板，可回看、删除。

---

## 评测引擎

```
用户输入（GitHub URL / 文字 / 文件夹）
    │
    ▼
collector.py    → GitHub API 采集（URL 模式）
competitor.py   → 自动搜索竞品
rubric.py       → LLM-as-a-Judge 五维打分 + 硬阈值校准
reporter.py     → 生成报告（含优化建议 + 发展方向）
    │
    ▼
前端单页展示：综合得分% + 五维方块 + 建议卡片 + 方向列表 + 追问对话
```

### 五维 Rubric

| 维度 | 权重 | 评分标准 |
|------|:--:|------|
| 差异化 | 25% | 0=功能重叠, 1=功能更多, 2=结构性差异（竞品无法通过扩展追平） |
| 护城河 | 25% | 0=stars<500, 1=stars<5000, 2=显著高于竞品+技术壁垒 |
| 定位 | 20% | 0=用户模糊, 1=基本清楚, 2=明确场景+代码示例+竞品对比 |
| 工程健康度 | 15% | 0=活跃<5天 或 issue关闭率<30%, 1=<15天 或 <70%, 2=高频提交+高关闭率 |
| 可持续性 | 15% | 0=>12月未更新 或 无商业模式, 1=有组织支持, 2=商业公司+活跃社区 |

> 核心原则：**宁低勿高**——2 分 = "突出"，不是"还不错"。硬阈值会强制校准偏离的 LLM 打分。

## API 端点（8 个）

| 端点 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `POST /evaluator/analyze` | 提交 GitHub 仓库评测（Celery 异步） |
| `POST /evaluator/analyze-text` | 提交文字描述评测（Celery 异步） |
| `GET /result/{task_id}` | 轮询任务结果 |
| `POST /advisor/ask` | 追问评测结果（同步） |
| `GET /evaluator/history` | 评测历史（最近 50 条） |
| `DELETE /evaluator/history` | 清空评测历史 |
| `DELETE /evaluator/history/{eval_id}` | 删除单条评测记录 |

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 数据库 | PostgreSQL（1 表：evaluation_records） |
| 缓存/队列 | Redis + Celery |
| 前端 | React 18 + TypeScript + Vite |
| LLM | DeepSeek（可配置 .env） |

## 项目结构

```
竞品雷达/
├── 启动竞品雷达.py          # 一键启动（Redis → Celery → FastAPI → Vite → 浏览器）
├── api.py                  # FastAPI 主入口（8 个端点）
├── config.py               # 环境变量统一配置（.env → Pydantic Settings）
├── models.py               # 数据模型（1 表：evaluation_records）
├── schemas.py              # Pydantic 校验
├── database.py             # 数据库连接
├── celery_app.py           # Celery 配置
├── tasks.py                # Celery 异步任务
├── redis_client.py         # Redis 连接客户端
├── logger.py               # 结构化日志
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── alembic.ini             # 数据库迁移配置
├── migrations/             # Alembic 迁移版本
├── core/
│   └── llm.py              # 统一 LLM 网关
├── modules/evaluator/      # 核心评测引擎
│   ├── collector.py        # GitHub API 采集
│   ├── competitor.py       # 自动搜索竞品
│   ├── rubric.py           # 五维 Rubric + LLM-as-a-Judge
│   └── reporter.py         # Markdown 报告生成
├── frontend/
│   └── src/pages/          # React 前端（单页应用）
├── tests/                  # pytest（36 个测试）
└── logs/                   # 运行日志
```
