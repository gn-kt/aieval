import time
import uuid

from redis import Redis


class RateLimiter:
    def __init__(self, redis: Redis, max_requests: int = 5, window_sec: int = 60):
        self.redis = redis
        self.max_requests = max_requests
        self.window_sec = window_sec

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_sec
        member = f"{now:.6f}-{uuid.uuid4().hex}"

        with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zadd(key, {member: now})
            pipe.expire(key, self.window_sec + 1)
            _, count, _, _ = pipe.execute()

        return count < self.max_requests

    def remaining(self, key: str) -> int:
        now = time.time()
        cutoff = now - self.window_sec
        self.redis.zremrangebyscore(key, 0, cutoff)
        count = self.redis.zcard(key)
        return max(0, self.max_requests - count)
