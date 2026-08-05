"""统一 LLM 网关：所有模块的 LLM 调用入口。

统一职责：
1. DeepSeek chat 补全封装（超时/重试/用量捕获）
2. 阿里百炼 embedding 封装
3. 用量记录（写入 usage_records 表）
"""
import os
import time

import httpx
from logger import get_logger
from openai import OpenAI

from config import DATABASE_URL

logger = get_logger(__name__)

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_CHAT_URL = os.getenv("LLM_CHAT_URL", "")

# Embedding 独立配置（默认硅基流动 bge-m3）
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
EMBED_API_KEY = os.getenv("EMBED_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")

_embed_client: OpenAI | None = None

_embed_disabled = False


class LLMError(RuntimeError):
    """LLM 调用统一异常。"""


def _get_active_config() -> dict:
    try:
        from models import LLMConfig
        from sqlalchemy import create_engine as _sync_engine
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
        engine = _sync_engine(sync_url, pool_pre_ping=True, pool_size=1)
        try:
            with Session(engine) as db:
                result = db.execute(
                    select(LLMConfig).where(LLMConfig.is_active == True).limit(1)
                )
                row = result.scalar_one_or_none()
                if row and row.api_key:
                    return {
                        "api_key": row.api_key,
                        "base_url": row.base_url or DEEPSEEK_BASE_URL,
                        "model": row.model or DEEPSEEK_MODEL,
                        "provider": row.provider,
                    }
                return {}
        finally:
            engine.dispose()
    except Exception:
        return {}


def _get_chat_config() -> tuple[str, str, str]:
    cfg = _get_active_config()
    if cfg:
        return cfg["api_key"], cfg["base_url"], cfg["model"]
    return _get_api_key(), DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def _get_api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise LLMError("DEEPSEEK_API_KEY is not set")
    return key


def _get_embed_client() -> OpenAI:
    global _embed_client, _embed_disabled
    if _embed_client is not None:
        return _embed_client
    if _embed_disabled:
        raise LLMError("Embedding is not configured. Set EMBED_API_KEY or ALIYUN_API_KEY.")
    key = EMBED_API_KEY or os.getenv("ALIYUN_API_KEY", "")
    if not key:
        _embed_disabled = True
        raise LLMError("Embedding is not configured. Set EMBED_API_KEY or ALIYUN_API_KEY.")
    _embed_client = OpenAI(api_key=key, base_url=EMBED_BASE_URL)
    return _embed_client


def chat(
    messages: list[dict],
    *,
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 500,
    timeout: float = 25,
    max_retries: int = 2,
) -> dict:
    """调用 LLM chat 补全。优先使用 DB 中的自定义配置，否则 fallback 到 .env DeepSeek。"""
    api_key, base_url, db_model = _get_chat_config()
    model = model or db_model
    if not api_key:
        raise LLMError("No LLM API key configured. Set API key in settings or DEEPSEEK_API_KEY in .env")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            resp = httpx.post(
                LLM_CHAT_URL or f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = data.get("usage", {})
            return {
                "content": data["choices"][0]["message"]["content"],
                "usage": {
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0)),
                    "total_tokens": int(usage.get("total_tokens", 0)),
                },
                "latency_ms": latency_ms,
            }
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning("LLM chat attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"LLM chat failed after {max_retries + 1} attempts: {last_exc}")


def chat_simple(prompt: str, *, system_prompt: str | None = None, **kwargs) -> str:
    """便捷单轮对话，返回纯文本答案。"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, **kwargs)["content"]


def embed(text: str) -> list[float]:
    return _get_embed_client().embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def embed_batch(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    client = _get_embed_client()
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        all_embeddings.extend(item.embedding for item in resp.data)
        if i + batch_size < len(texts):
            time.sleep(0.3)
    return all_embeddings


async def record_usage(
    *,
    user_id: int | None,
    module: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    detail: str | None = None,
) -> None:
    """异步记录一次 LLM 用量。不阻塞主流程，失败仅告警。"""
    try:
        from models import UsageRecord
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker,
            create_async_engine,
        )

        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as db:
            db.add(UsageRecord(
                user_id=user_id,
                module=module,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                detail=detail,
            ))
            await db.commit()
        await engine.dispose()
    except Exception as exc:  # noqa: BLE001 — 用量记录失败不影响主流程
        logger.warning("record_usage failed: %s", exc)


async def get_usage_stats(*, user_id: int | None = None, days: int = 7) -> dict:
    """查询用量统计：总 token、次数、各模块分布。

    Args:
        user_id: None 表示全局统计。
        days: 统计最近 N 天。
    """
    import datetime

    from models import UsageRecord
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )

    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

            base = select(UsageRecord).where(UsageRecord.created_at >= since)
            if user_id is not None:
                base = base.where(UsageRecord.user_id == user_id)

            total = await db.execute(
                select(
                    func.count(UsageRecord.id),
                    func.coalesce(func.sum(UsageRecord.total_tokens), 0),
                    func.coalesce(func.sum(UsageRecord.prompt_tokens), 0),
                    func.coalesce(func.sum(UsageRecord.completion_tokens), 0),
                ).where(UsageRecord.created_at >= since, *([] if user_id is None else [UsageRecord.user_id == user_id]))
            )
            count, total_tokens, prompt_tokens, completion_tokens = total.one()

            by_module = await db.execute(
                select(UsageRecord.module, func.count(UsageRecord.id), func.coalesce(func.sum(UsageRecord.total_tokens), 0))
                .where(UsageRecord.created_at >= since, *([] if user_id is None else [UsageRecord.user_id == user_id]))
                .group_by(UsageRecord.module)
            )
            modules = {row[0]: {"calls": row[1], "tokens": int(row[2])} for row in by_module.all()}

            return {
                "days": days,
                "total_calls": count,
                "total_tokens": int(total_tokens),
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "by_module": modules,
            }
    finally:
        await engine.dispose()
