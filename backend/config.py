import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.getenv("FORCEX_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("FORCEX_DB", "sqlite:///forcex.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("FORCEX_MAX_UPLOAD_MB", "500")) * 1024 * 1024
    STORAGE_DIR = os.getenv("FORCEX_STORAGE", str(ROOT / "storage"))
    VIEW_TTL = timedelta(minutes=int(os.getenv("FORCEX_VIEW_TTL_MIN", "10")))
    DOWNLOAD_TTL = timedelta(minutes=int(os.getenv("FORCEX_DOWNLOAD_TTL_MIN", "5")))
    EXPIRY_CHOICES = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
    MAX_FILES = 500
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

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = "test-secret"
