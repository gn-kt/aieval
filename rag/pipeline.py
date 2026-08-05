import os

from core import llm

from rag.retriever import search

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

RAG_SYSTEM_PROMPT = """你是 AI Agent 学习助手。根据以下检索到的笔记内容回答用户问题。

要求：
1. 只依据提供的笔记内容回答，不要编造
2. 如果笔记内容不足以回答，诚实告知
3. 回答简洁，控制在 300 字以内"""

CHAT_SYSTEM_PROMPT = """你是 AI Agent 学习助手。根据检索到的笔记内容回答用户问题。

要求：
1. 只依据提供的笔记内容回答，不要编造
2. 如果笔记内容不足以回答，诚实告知
3. 保持对话连贯，理解上下文中的指代（如"刚才那个"、"前面提到的"）"""


def _build_prompt(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return query
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(f"[来源{i+1}: {chunk['source']}]\n{chunk['text']}")
    context = "\n\n---\n\n".join(parts)

    return f"""【检索到的笔记内容】

{context}

【用户问题】

{query}"""


def _call_llm(messages: list[dict]) -> dict:
    return llm.chat(messages, temperature=0.3, max_tokens=500)


def ask(query: str, k: int = 3, history: list[dict] | None = None) -> dict:
    chunks = search(query, k=k)
    user_content = _build_prompt(query, chunks)

    messages = []
    if history:
        system_prompt = CHAT_SYSTEM_PROMPT
    else:
        system_prompt = RAG_SYSTEM_PROMPT

    messages.append({"role": "system", "content": system_prompt})

    if history:
        for msg in history:
            messages.append(msg)

    messages.append({"role": "user", "content": user_content})
    llm_result = _call_llm(messages)

    return {
        "answer": llm_result["content"],
        "usage": llm_result["usage"],
        "sources": [
            {"file": c["source"], "chunk": c["chunk_index"], "score": round(c["score"], 4)}
            for c in chunks
        ],
    }
