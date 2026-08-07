"""统一 LLM 网关：所有模块的 LLM 调用入口。

职责：
1. DeepSeek chat 补全封装（超时/重试）
2. .env 统一配置入口（所有 LLM 参数从 config.py 读取）
"""
import time

import httpx
from logger import get_logger

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLM_CHAT_URL

logger = get_logger(__name__)


class LLMError(RuntimeError):
    """LLM 调用统一异常。"""


def _get_chat_config() -> tuple[str, str, str]:
    api_key = DEEPSEEK_API_KEY
    if not api_key:
        raise LLMError("DEEPSEEK_API_KEY is not set")
    return api_key, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


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
