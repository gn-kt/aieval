import asyncio
import os
import sys

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/backend_test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["TESTING"] = "1"
os.environ["CELERY_ALWAYS_EAGER"] = "True"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

sys.path.insert(0, _PROJECT_DIR)

import fakeredis
import models  # noqa: F401
import pytest
import pytest_asyncio
from database import AsyncSessionLocal, Base, engine


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("redis_client.get_redis", lambda: fake)
    monkeypatch.setattr("redis_client.get_redis_singleton", lambda: fake)
    monkeypatch.setattr("api.get_redis", lambda: fake)
    return fake


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from config import DATABASE_URL

    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(alembic_cfg, "head")
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(lambda c: c.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE")))


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as db:
        yield db
