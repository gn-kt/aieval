import asyncio
import math
import time
from contextlib import asynccontextmanager

import metrics
from auth import authenticate_user, create_access_token, create_user
from celery.result import AsyncResult
from celery_app import celery_app
from database import engine, get_db, init_db
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from logger import get_logger, setup_logging
from middleware import get_current_user
from models import User
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import ValidationError
from rate_limiter import RateLimiter
from redis_client import get_redis
from schemas import (
    AdvisorAskRequest,
    AdvisorAskResponse,
    ChatMessage,
    EvaluateRequest,
    LoginRequest,
    LoginResponse,
    PaginatedTasksResponse,
    RegisterRequest,
    SessionResponse,
    TaskCreateResponse,
    TextEvaluateRequest,
    UserResponse,
)
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks import run_evaluation, run_rag_query, run_text_evaluation
from tracing import (
    init_tracing,
    instrument_celery,
    instrument_fastapi,
    instrument_sqlalchemy,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_tracing()
    instrument_fastapi(app)
    instrument_sqlalchemy(engine)
    instrument_celery(celery_app)
    await init_db()
    redis_client = get_redis()
    app.state.redis = redis_client
    app.state.rate_limiter = RateLimiter(redis_client, max_requests=10, window_sec=60)
    logger.info("Application started, database initialized, Redis connected")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="RAG API",
    description="Production-grade RAG backend with Celery tasks and PostgreSQL",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    inprogress_name="rag_http_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info("%s %s → %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
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


@app.get("/metrics")
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/register", response_model=UserResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if result.scalar_one_or_none():
        logger.warning("Registration failed: username=%s already exists", req.username)
        raise HTTPException(status_code=400, detail="Username or email already exists")
    user = await create_user(db, req.username, req.email, req.password)
    logger.info("User registered: id=%s username=%s", user.id, user.username)
    return user


@app.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        logger.warning("Login failed for username=%s", req.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user.username})
    logger.info("User logged in: id=%s username=%s", user.id, user.username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/ask", response_model=TaskCreateResponse)
@limiter.limit("5/minute")
async def ask(
    question: str,
    session_id: str | None = None,
    request: Request = None,
):
    client_ip = request.client.host if request and request.client else "unknown"
    limiter: RateLimiter = request.app.state.rate_limiter
    user_key = f"rate_limit:ip:{client_ip}"
    if not limiter.is_allowed(user_key):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in {limiter.window_sec}s.")
    celery_task = run_rag_query.delay(question, session_id)
    task_id = celery_task.id
    remaining = limiter.remaining(user_key)

    redis_client = request.app.state.redis
    redis_client.zadd("rag:task_history", {task_id: time.time()})
    redis_client.hset(f"task_meta:{task_id}", mapping={
        "question": question[:200],
        "created_at": str(int(time.time())),
        "user": client_ip,
    })

    metrics.task_created_total.labels(status="queued").inc()
    logger.info("Celery task created: task_id=%s question=%s", task_id, question[:50])
    return {"task_id": task_id, "status": "queued", "rate_limit_remaining": remaining}


@app.post("/sessions/new", response_model=SessionResponse)
async def new_session(request: Request = None):
    from session_manager import create_session
    client_ip = request.client.host if request and request.client else "anon"
    sid = create_session(client_ip)
    logger.info("Session created: id=%s", sid)
    return {"session_id": sid, "messages": []}


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    from session_manager import get_history, get_session_user
    owner = get_session_user(session_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = get_history(session_id)
    return {"session_id": session_id, "messages": [ChatMessage(**m) for m in messages] if messages else []}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    from session_manager import delete_session, get_session_user
    owner = get_session_user(session_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"status": "deleted"}


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


@app.get("/tasks", response_model=PaginatedTasksResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    redis_client = get_redis()
    redis_data = []
    task_ids = redis_client.zrevrange("rag:task_history", 0, -1)
    for tid in task_ids:
        meta = redis_client.hgetall(f"task_meta:{tid}")
        task_result = AsyncResult(tid, app=celery_app)
        redis_data.append({
            "task_id": tid,
            "question": meta.get("question", ""),
            "status": task_result.state,
            "created_at": meta.get("created_at"),
        })

    total = len(redis_data)
    pages = math.ceil(total / size) if total > 0 else 1
    start = (page - 1) * size
    end = start + size

    return {
        "items": redis_data[start:end],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@app.websocket("/ws/{task_id}")
async def websocket_result(websocket: WebSocket, task_id: str, token: str = ""):
    await websocket.accept()
    metrics.active_websocket_connections.inc()
    logger.info("WS connected: task_id=%s", task_id)

    try:
        while True:
            await asyncio.sleep(0.5)
            await websocket.send_json({"ping": "waiting"})

            task_result = AsyncResult(task_id, app=celery_app)
            if task_result.ready():
                result = task_result.result
                if isinstance(result, dict):
                    inner = result.get("result")
                    await websocket.send_json({"task_id": task_id, "status": "completed", "result": inner})
                else:
                    await websocket.send_json({"task_id": task_id, "status": "completed", "result": str(result)})
                break

            if task_result.state == "FAILURE":
                await websocket.send_json({"task_id": task_id, "status": "failed", "result": str(task_result.info)})
                break

    except WebSocketDisconnect:
        logger.info("WS disconnected: task_id=%s user=%s", task_id, username)
    finally:
        metrics.active_websocket_connections.dec()


@app.get("/stats")
async def stats():
    redis_client = get_redis()
    task_count = redis_client.zcard("rag:task_history") or 0
    ws_active = metrics.active_websocket_connections._value.get()
    return {"active_ws": int(ws_active), "task_count": int(task_count)}


@app.post("/evaluator/analyze", response_model=TaskCreateResponse)
@limiter.limit("3/minute")
async def evaluator_analyze(
    req: EvaluateRequest,
    request: Request = None,
):
    celery_task = run_evaluation.delay(req.repo_url, req.description or "", req.n_competitors)
    task_id = celery_task.id

    redis_client = request.app.state.redis
    redis_client.zadd("evaluator:task_history", {task_id: time.time()})
    redis_client.hset(f"task_meta:{task_id}", mapping={
        "question": f"评测 {req.repo_url}",
        "created_at": str(int(time.time())),
        "user": "anon",
    })

    metrics.task_created_total.labels(status="queued").inc()
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
    redis_client = request.app.state.redis
    redis_client.zadd("evaluator:task_history", {task_id: time.time()})
    redis_client.hset(f"task_meta:{task_id}", mapping={
        "question": f"评测: {req.description[:100]}",
        "created_at": str(int(time.time())),
        "user": "anon",
    })
    metrics.task_created_total.labels(status="queued").inc()
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
        await engine.dispose()
        return {"evaluations": evaluations}
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
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            timeout=15,
        )
        if resp.status_code == 200:
            return {"status": "ok", "message": "连接成功 ✓"}
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
