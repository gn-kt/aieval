# 竞品雷达

输入 GitHub 仓库 / 文字描述 / 文件夹 → AI 五维竞争力评分 + 优化建议 + 发展方向。

## 特性

- GitHub 仓库自动采集（API 元数据 + README + commits + issues）
- 竞品自动搜索对比
- LLM-as-a-Judge 五维打分（定位/差异化/护城河/工程健康度/可持续性）+ 硬阈值校准
- 追问对话（带上下文的深度分析）
- 异步任务队列（Celery + Redis）
- React 单页评测面板（TypeScript + Vite）
- LLM 通过 `.env` 配置（支持任意 OpenAI 兼容接口）

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 数据库 | PostgreSQL（evaluation_records） |
| 缓存/队列 | Redis + Celery |
| 前端 | React 18 + TypeScript + Vite |
| LLM | DeepSeek（可配置） |

## 快速开始

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库
alembic upgrade head

# 4. 一键启动（Redis → Celery → FastAPI → Vite → 浏览器）
python 启动竞品雷达.py
```

## 环境变量

所有配置集中在 `.env` 文件，示例见 `.env.example`。

| 变量 | 必填 | 说明 |
|------|:--:|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | — | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | — | 默认 `deepseek-chat` |
| `LLM_CHAT_URL` | — | 可选：自定义 chat API 地址 |
| `DATABASE_URL` | — | 默认本机 PostgreSQL |
| `REDIS_URL` | — | 默认本机 Redis |
| `GITHUB_TOKEN` | — | GitHub API token，提高频率上限 |

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

### 五维权重

| 维度 | 权重 | 说明 |
|------|:--:|------|
| 差异化 | 25% | 与竞品相比的独特价值 |
| 护城河 | 25% | 技术壁垒 + 社区活跃度 |
| 定位 | 20% | 目标用户/场景是否清晰 |
| 工程健康度 | 15% | 提交频率 + issue 关闭率 |
| 可持续性 | 15% | 组织支持 + 商业模式 |

核心原则：**宁低勿高** — 2 分 = "突出"，不是"还不错"。

## 项目结构

```
竞品雷达/
├── api.py                  # FastAPI 主入口（8 个端点）
├── models.py               # 数据模型（1 表）
├── schemas.py              # Pydantic 校验
├── database.py             # 数据库连接 + Alembic 自动迁移
├── celery_app.py           # Celery 配置
├── tasks.py                # Celery 异步任务 + 追问辅助函数
├── redis_client.py         # Redis 连接
├── logger.py               # 结构化日志
├── config.py               # 环境变量统一配置（所有 os.getenv 单入口）
├── 启动竞品雷达.py          # 一键启动脚本
├── core/
│   └── llm.py              # 统一 LLM 网关（chat + chat_simple）
├── modules/evaluator/      # 核心评测引擎
│   ├── collector.py        # GitHub API 采集
│   ├── competitor.py       # 竞品搜索
│   ├── rubric.py           # 五维 Rubric LLM-as-a-Judge
│   └── reporter.py         # Markdown 报告生成
├── migrations/             # Alembic 迁移
├── frontend/               # React 前端
│   └── src/pages/EvaluatorPage.tsx  # 主页面（三种输入模式）
└── tests/                  # pytest 测试（36 个）
```
