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

        with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            _, count = pipe.execute()

        if count < self.max_requests:
            member = f"{now:.6f}-{id(self)}-{uuid.uuid4().hex[:6]}"
            self.redis.zadd(key, {member: now})
            self.redis.expire(key, self.window_sec + 1)
            return True
        return False

    def remaining(self, key: str) -> int:
        now = time.time()
        cutoff = now - self.window_sec
        self.redis.zremrangebyscore(key, 0, cutoff)
        count = self.redis.zcard(key)
        return max(0, self.max_requests - count)
