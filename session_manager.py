import json

from redis_client import get_redis

SESSION_TTL = 3600
HISTORY_MAX = 10


def _key(session_id: str) -> str:
    return f"session:{session_id}:messages"


def create_session(user: str) -> str:
    import uuid
    session_id = str(uuid.uuid4())[:12]
    redis = get_redis()
    redis.setex(f"session:{session_id}:user", SESSION_TTL, user)
    return session_id


def add_message(session_id: str, role: str, content: str) -> None:
    redis = get_redis()
    redis.rpush(_key(session_id), json.dumps({"role": role, "content": content}))
    redis.expire(_key(session_id), SESSION_TTL)


def get_history(session_id: str, max_turns: int = HISTORY_MAX) -> list[dict]:
    redis = get_redis()
    raw = redis.lrange(_key(session_id), 0, -1)
    messages = [json.loads(m) for m in raw]
    if len(messages) > max_turns * 2:
        messages = messages[-(max_turns * 2):]
    return messages


def delete_session(session_id: str) -> None:
    redis = get_redis()
    redis.delete(_key(session_id), f"session:{session_id}:user")


def get_session_user(session_id: str) -> str | None:
    redis = get_redis()
    user = redis.get(f"session:{session_id}:user")
    return user.decode() if isinstance(user, bytes) else user
