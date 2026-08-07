import os

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_CHAT_URL = os.getenv("LLM_CHAT_URL", "")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_VERIFY_SSL = os.getenv("GITHUB_VERIFY_SSL", "true").lower() not in ("0", "false", "no")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/backend_dev")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_JSON = os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes")
