"""Embedding 模块：复用统一 LLM 网关的 embedding 入口。"""
from core import llm

EMBEDDING_MODEL = llm.EMBED_MODEL


def embed(text: str) -> list[float]:
    return llm.embed(text)


def embed_batch(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    return llm.embed_batch(texts, batch_size=batch_size)
