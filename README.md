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

## 快速开始

```bash
cp .env.example .env          # 填入 DEEPSEEK_API_KEY
pip install -r requirements.txt
alembic upgrade head
python 启动竞品雷达.py        # 一键启动（Redis → Celery → FastAPI → Vite）
```

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
├── api.py                  # FastAPI 主入口（8 个端点）
├── models.py               # 数据模型（1 表）
├── schemas.py              # Pydantic 校验
├── database.py             # 数据库连接
├── celery_app.py           # Celery 配置
├── tasks.py                # Celery 异步任务
├── config.py               # 环境变量统一配置
├── core/llm.py             # 统一 LLM 网关
├── modules/evaluator/      # 核心评测引擎
│   ├── collector.py        # GitHub API 采集
│   ├── competitor.py       # 竞品搜索
│   ├── rubric.py           # 五维 Rubric + LLM-as-a-Judge
│   └── reporter.py         # Markdown 报告生成
├── frontend/               # React 前端
│   └── src/pages/EvaluatorPage.tsx  # 主页面
└── tests/                  # pytest（36 个测试）
```
