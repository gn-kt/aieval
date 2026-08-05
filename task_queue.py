import uuid

from redis import Redis


class TaskQueue:
    def __init__(self, redis: Redis, queue_name: str = "rag:tasks"):
        self.redis = redis
        self.queue_name = queue_name

    def enqueue(self, task_data: dict) -> str:
        task_id = uuid.uuid4().hex[:12]
        data = {**task_data, "task_id": task_id, "status": "queued"}
        self.redis.hset(f"task:{task_id}", mapping=data)
        self.redis.rpush(self.queue_name, task_id)
        return task_id

    def get_status(self, task_id: str) -> dict | None:
        data = self.redis.hgetall(f"task:{task_id}")
        return dict(data) if data else None

    def update_status(self, task_id: str, status: str, result: str | None = None):
        update = {"status": status}
        if result is not None:
            update["result"] = result
        self.redis.hset(f"task:{task_id}", mapping=update)
