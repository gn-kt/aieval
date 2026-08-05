import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/backend_dev")
_key = os.getenv("SECRET_KEY", "")
if not _key:
    raise RuntimeError("SECRET_KEY environment variable is required")
SECRET_KEY: str = _key
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_JSON = os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes")
