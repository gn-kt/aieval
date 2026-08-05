import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from config import DATABASE_URL

_IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")

_engine_kwargs = {"echo": False} if _IS_TESTING else {
    "echo": False,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}
if _IS_TESTING:
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


async def init_db():
    import asyncio

    from alembic import command
    from alembic.config import Config
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Alembic migration failed: %s", e)
        raise
