from redis import Redis

from config import REDIS_URL


# 本机 Redis 5.x 仅支持 RESP2。redis-py 需 ≤5.x（5.x 默认 RESP2，8.x 默认 RESP3 会发 HELLO 被拒）。
# 这里显式 protocol=2 兜底，防环境升级 redis-py 后回归。
def get_redis() -> Redis:
    return Redis.from_url(REDIS_URL, decode_responses=True, protocol=2)


_redis_instance: Redis | None = None


def get_redis_singleton() -> Redis:
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = get_redis()
    return _redis_instance
