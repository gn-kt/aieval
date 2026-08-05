"""本地免费 embedding 服务（OpenAI 兼容 /v1/embeddings）。

使用 sentence-transformers + BAAI/bge-small-zh-v1.5，完全离线免费。
供 OmniRoute 作为本地 provider_node 接入。

用法:
    python local_embed_server.py            # 启动在 127.0.0.1:8765
"""
# 环境变量必须在 import sentence_transformers 之前设置
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HOME"] = r"D:\IT_environment\HuggingFace"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.getenv("EMBED_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5")
MODEL_DIM = int(os.getenv("EMBED_LOCAL_DIM", "512"))
HOST = os.getenv("EMBED_LOCAL_HOST", "127.0.0.1")
PORT = int(os.getenv("EMBED_LOCAL_PORT", "8765"))

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


app = FastAPI(title="Local Embedding Server")


class EmbeddingRequest(BaseModel):
    model: str | None = None
    input: str | list[str] | list[list[int]]


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "dimensions": MODEL_DIM}


@app.post("/v1/embeddings")
async def embeddings(req: EmbeddingRequest):
    model = _get_model()
    texts = req.input if isinstance(req.input, list) else [req.input]
    texts = [t if isinstance(t, str) else "" for t in texts]

    vectors = model.encode(texts, normalize_embeddings=True)

    data = []
    for i, vec in enumerate(vectors):
        data.append({
            "object": "embedding",
            "index": i,
            "embedding": [float(x) for x in vec.tolist()],
        })

    return JSONResponse({
        "object": "list",
        "data": data,
        "model": MODEL_NAME,
        "usage": {
            "prompt_tokens": sum(len(t) for t in texts),
            "total_tokens": sum(len(t) for t in texts),
        },
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
