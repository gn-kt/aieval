import time
from contextlib import asynccontextmanager

from celery.result import AsyncResult
from celery_app import celery_app
from database import init_db
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from logger import get_logger, setup_logging
from pydantic import ValidationError
from redis_client import get_redis
from schemas import (
    AdvisorAskRequest,
    AdvisorAskResponse,
    EvaluateRequest,
    TaskCreateResponse,
    TextEvaluateRequest,
)
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from tasks import run_evaluation, run_text_evaluation

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    redis_client = get_redis()
    app.state.redis = redis_client
    logger.info("Application started, database initialized, Redis connected")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="竞品雷达",
    description="产品竞争力评测引擎",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail, "details": None}},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "reason": error["msg"],
        })
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s", type(exc).__name__, str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": None}},
    )


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    state = task_result.state
    if state in ("PENDING", "STARTED", "RETRY") or task_result.result is None:
        return {"task_id": task_id, "status": state, "result": None}
    if state == "FAILURE":
        logger.warning("Task failed: task_id=%s", task_id)
        return {"task_id": task_id, "status": "failed", "result": {"error": str(task_result.info)}}
    result_data = task_result.result
    if isinstance(result_data, dict):
        inner = result_data.get("result")
        return {"task_id": task_id, "status": result_data.get("status", "done"), "result": inner}
    return {"task_id": task_id, "status": "done", "result": str(result_data)}


@app.post("/evaluator/analyze", response_model=TaskCreateResponse)
@limiter.limit("3/minute")
async def evaluator_analyze(
    req: EvaluateRequest,
    request: Request = None,
):
    celery_task = run_evaluation.delay(req.repo_url, req.description or "", req.n_competitors)
    task_id = celery_task.id
    logger.info("Evaluation task created: task_id=%s repo=%s",
                  task_id, req.repo_url)
    return {"task_id": task_id, "status": "queued"}


@app.post("/evaluator/analyze-text", response_model=TaskCreateResponse)
@limiter.limit("3/minute")
async def evaluator_analyze_text(
    req: TextEvaluateRequest,
    request: Request = None,
):
    celery_task = run_text_evaluation.delay(req.description, req.n_competitors)
    task_id = celery_task.id
    logger.info("Text evaluation task created: task_id=%s", task_id)
    return {"task_id": task_id, "status": "queued"}


@app.post("/advisor/ask", response_model=AdvisorAskResponse)
async def advisor_ask(req: AdvisorAskRequest):
    from core import llm
    from tasks import (
        ADVISOR_SYSTEM_PROMPT,
        _build_advisor_context,
        _query_evaluation_by_repo,
    )

    if req.eval_data:
        eval_data = {
            "repo": req.eval_data.get("repo", req.repo_url),
            "url": req.repo_url,
            "score": req.eval_data.get("weighted_total", 0),
            "positioning": req.eval_data.get("scores", {}).get("positioning", {}).get("score", 0),
            "differentiation": req.eval_data.get("scores", {}).get("differentiation", {}).get("score", 0),
            "moat": req.eval_data.get("scores", {}).get("moat", {}).get("score", 0),
            "engineering": req.eval_data.get("scores", {}).get("engineering", {}).get("score", 0),
            "sustainability": req.eval_data.get("scores", {}).get("sustainability", {}).get("score", 0),
            "summary": req.eval_data.get("overall_summary", ""),
            "strengths": "",
            "weaknesses": "",
        }
    else:
        eval_data = _query_evaluation_by_repo(req.repo_url)
        if not eval_data:
            eval_data = {}

    context = _build_advisor_context([eval_data] if eval_data else [], req.question)
    messages = [{"role": "system", "content": ADVISOR_SYSTEM_PROMPT}]
    if req.history:
        for msg in req.history[-10:]:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg.get("content", "")})
    messages.append({"role": "user", "content": context})
    result = llm.chat(messages, temperature=0.7, max_tokens=500)
    sources = [f"{eval_data.get('repo', 'unknown')} ({eval_data.get('score', 'N/A')})"] if eval_data else []

    return {"answer": result["content"], "sources": sources}


@app.get("/evaluator/history")
async def evaluator_history():
    try:
        from models import EvaluationRecord
        from sqlalchemy import desc, select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from config import DATABASE_URL

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as db:
                result = await db.execute(
                    select(EvaluationRecord).order_by(desc(EvaluationRecord.created_at)).limit(50)
                )
                records = result.scalars().all()
                evaluations = [
                    {
                        "id": r.id,
                        "repo": r.repo_full_name,
                        "url": r.repo_url,
                        "score": r.weighted_total or 0.0,
                        "positioning": r.score_positioning or 0,
                        "differentiation": r.score_differentiation or 0,
                        "moat": r.score_moat or 0,
                        "engineering": r.score_engineering or 0,
                        "sustainability": r.score_sustainability or 0,
                        "summary": r.overall_summary or "",
                        "strengths": r.top_strengths or "",
                        "weaknesses": r.top_weaknesses or "",
                        "evaluated_at": str(r.created_at) if r.created_at else "",
                    }
                    for r in records
                ]
            return {"evaluations": evaluations}
        finally:
            await engine.dispose()
    except Exception as e:
        logger.warning("History query failed: %s", e)
        return {"evaluations": []}


@app.get("/settings/llm")
async def settings_llm_get():
    try:
        from models import LLMConfig
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from config import DATABASE_URL

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == True).limit(1))
            row = result.scalar_one_or_none()
            if row:
                return {"provider": row.provider, "api_key": row.api_key[:8] + "***" if row.api_key else "", "base_url": row.base_url, "model": row.model, "has_key": bool(row.api_key)}
            return {"provider": "deepseek", "api_key": "", "base_url": "", "model": "deepseek-chat", "has_key": False}
        await engine.dispose()
    except Exception:
        return {"provider": "deepseek", "api_key": "", "base_url": "", "model": "deepseek-chat", "has_key": False}


@app.post("/settings/llm")
async def settings_llm_save(data: dict):
    try:
        from models import LLMConfig
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from config import DATABASE_URL

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == True).limit(1))
            row = result.scalar_one_or_none()
            if row:
                if data.get("api_key") and data["api_key"] != row.api_key:
                    row.api_key = data["api_key"]
                if data.get("base_url"):
                    row.base_url = data["base_url"]
                if data.get("model"):
                    row.model = data["model"]
                if data.get("provider"):
                    row.provider = data["provider"]
            else:
                db.add(LLMConfig(
                    provider=data.get("provider", "custom"),
                    api_key=data.get("api_key", ""),
                    base_url=data.get("base_url", ""),
                    model=data.get("model", ""),
                    is_active=True,
                ))
            await db.commit()
        await engine.dispose()
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings/llm/test")
async def settings_llm_test(data: dict):
    import httpx
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "deepseek-chat")
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="base_url and api_key are required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            )
        if resp.status_code == 200:
            return {"status": "ok", "message": "连接成功"}
        return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


@app.delete("/evaluator/history")
async def evaluator_history_clear():
    try:
        from models import EvaluationRecord
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from config import DATABASE_URL

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            result = await db.execute(delete(EvaluationRecord))
            await db.commit()
            count = result.rowcount
        await engine.dispose()
        return {"status": "cleared", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/evaluator/history/{eval_id}")
async def evaluator_history_delete(eval_id: int):
    try:
        from models import EvaluationRecord
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from config import DATABASE_URL

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=1)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as db:
            await db.execute(delete(EvaluationRecord).where(EvaluationRecord.id == eval_id))
            await db.commit()
        await engine.dispose()
        return {"status": "deleted", "id": eval_id}
    except Exception as e:
        logger.warning("History delete failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
