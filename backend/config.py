import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.getenv("VERCEL"))

def _database_url():
    # Neon on Vercel provides DATABASE_URL as postgresql://...; SQLAlchemy needs the psycopg driver named.
    url = os.getenv("FORCEX_DB") or os.getenv("DATABASE_URL") or "sqlite:///forcex.db"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url

class Config:
    SECRET_KEY = os.getenv("FORCEX_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_url()
    # Serverless instances sit idle between requests; test pooled connections before reuse.
    # hide_parameters keeps submitted values (emails, password hashes) out of database error messages and logs.
    SQLALCHEMY_ENGINE_OPTIONS = {"hide_parameters": True} if SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {"hide_parameters": True, "pool_pre_ping": True, "pool_recycle": 280, "pool_size": 2, "max_overflow": 3}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("FORCEX_MAX_UPLOAD_MB", "500")) * 1024 * 1024
    # Vercel's filesystem is read-only except /tmp, which only holds scratch and cache files there.
    STORAGE_DIR = os.getenv("FORCEX_STORAGE", "/tmp/forcex" if ON_VERCEL else str(ROOT / "storage"))
    # "blob" keeps files in Vercel Blob (browsers upload to it directly); "local" keeps them in STORAGE_DIR.
    STORAGE_BACKEND = os.getenv("FORCEX_STORAGE_BACKEND") or ("blob" if os.getenv("BLOB_READ_WRITE_TOKEN") else "local")
    CRON_SECRET = os.getenv("CRON_SECRET")
    VIEW_TTL = timedelta(minutes=int(os.getenv("FORCEX_VIEW_TTL_MIN", "10")))
    DOWNLOAD_TTL = timedelta(minutes=int(os.getenv("FORCEX_DOWNLOAD_TTL_MIN", "5")))
    EXPIRY_CHOICES = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
    MAX_FILES = int(os.getenv("FORCEX_MAX_FILES", "500"))
    MAX_PATH_DEPTH = 20
    MAX_PASSCODE_ATTEMPTS = 5
    INLINE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp", "video/mp4", "video/webm", "application/pdf", "text/plain"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FORCEX_COOKIE_SECURE", "0") == "1"
    COOKIE_SECURE = SESSION_COOKIE_SECURE
    ALLOW_REGISTRATION = os.getenv("FORCEX_ALLOW_REGISTRATION", "1") == "1"
    # Shared with the desktop client; receiver pages refuse any request that does not carry it.
    CLIENT_KEY = os.getenv("FORCEX_CLIENT_KEY")
    BEHIND_PROXY = os.getenv("FORCEX_BEHIND_PROXY", "0") == "1"
    DESKTOP_DOWNLOAD_URL = os.getenv("FORCEX_DESKTOP_DOWNLOAD_URL", "https://github.com/eklavya2201/ForceX/releases/latest/download/ForceX.exe")

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = "test-secret"
