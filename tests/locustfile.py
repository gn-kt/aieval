import random
import string

from locust import HttpUser, between, task


class RegisterUser(HttpUser):
    """压测场景 1: 并发注册"""
    weight = 2
    wait_time = between(0.5, 2)

    @task
    def register(self):
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        payload = {
            "username": f"loadtest_{suffix}",
            "email": f"loadtest_{suffix}@test.com",
            "password": "test123456",
        }
        with self.client.post("/register", json=payload, catch_response=True) as resp:
            if resp.status_code == 400 and "already exists" in resp.text:
                resp.success()
            elif resp.status_code != 200:
                resp.failure(f"register returned {resp.status_code}: {resp.text}")


class RAGUser(HttpUser):
    """压测场景 2: 完整 RAG 流程 — 注册 → 登录 → 提交任务 → 查历史"""
    weight = 3
    wait_time = between(1, 3)

    def on_start(self):
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.username = f"loadtest_{suffix}"
        self.email = f"loadtest_{suffix}@test.com"
        self.password = "test123456"
        self.token = None

        resp = self.client.post("/register", json={
            "username": self.username,
            "email": self.email,
            "password": self.password,
        })

        if resp.status_code in (200, 400):
            resp = self.client.post("/login", json={
                "username": self.username,
                "password": self.password,
            })
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
            else:
                resp.failure("login failed")

    @task(5)
    def submit_ask(self):
        if not self.token:
            return
        questions = [
            "什么是机器学习",
            "Python异步编程原理",
            "Docker容器化最佳实践",
            "PostgreSQL索引类型",
            "Redis缓存策略",
        ]
        q = random.choice(questions)
        headers = {"Authorization": f"Bearer {self.token}"}
        with self.client.post(f"/ask?question={q}", headers=headers, catch_response=True) as resp:
            if resp.status_code == 429:
                resp.success()
            elif resp.status_code != 200:
                resp.failure(f"ask returned {resp.status_code}")

    @task(2)
    def list_tasks(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        page = random.randint(1, 3)
        self.client.get(f"/tasks?page={page}&size=10", headers=headers, name="/tasks")

    @task(1)
    def get_stats(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/stats", headers=headers)


class LightUser(HttpUser):
    """压测场景 3: 轻量级 — 仅 /health 和 /metrics"""
    weight = 1
    wait_time = between(0.1, 0.5)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(1)
    def metrics(self):
        self.client.get("/metrics")
