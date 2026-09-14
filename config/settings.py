from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bot.db'}"

_SQLITE_PREFIX = "sqlite+aiosqlite:///"


def normalize_database_url(url: str) -> str:
    """تثبيت مسار قاعدة بيانات SQLite على جذر المشروع دائمًا.

    يحوّل أي مسار نسبي (مثل ``sqlite+aiosqlite:///bot.db``) إلى مسار مطلق
    مرتبط بـ BASE_DIR، حتى لو شُغّل البوت من مجلد مختلف.
    """
    if url.startswith(_SQLITE_PREFIX):
        path = url[len(_SQLITE_PREFIX):]
        if path and not path.startswith(("/", "\\", ":")):
            return f"{_SQLITE_PREFIX}{BASE_DIR / path}"
    return url


class Settings(BaseSettings):
    """كل إعدادات البوت تُقرأ من ملف .env فقط — لا توجد أي أسرار داخل الكود."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _anchor_paths(self) -> "Settings":
        # المسار من .env قد يكون نسبيًا — نثبّته على جذر المشروع
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        return self

    # --- أساسي ---
    BOT_TOKEN: str
    ADMIN_IDS: str = ""

    # --- القناة والمجموعة ---
    CHANNEL_ID: int | None = None
    CHANNEL_USERNAME: str | None = None
    GROUP_ID: int | None = None
    GROUP_USERNAME: str | None = None

    # --- Dev Uploads (devuploads.com) ---
    DEVUPLOAD_API_KEY: str | None = None
    DEVUPLOAD_BASE_URL: str = "https://devuploads.com"
    DEVUPLOAD_TIMEOUT: float = 600.0

    # --- ShrinkMe.io ---
    SHRANKME_API_KEY: str | None = None
    SHRANKME_API_URL: str = "https://shrinkme.io/st"
    SHRANKME_LEGACY_API_URL: str = "https://shrinkme.io/api"
    SHRANKME_TIMEOUT: float = 60.0

    # --- ImgBB (رفع الصور) ---
    IMGBB_API_KEY: str | None = None

    # --- قاعدة البيانات ---
    DATABASE_URL: str = DEFAULT_DB_URL

    # --- سلوك عام ---
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB
    HTTP_MAX_RETRIES: int = 3
    DOWNLOAD_DIR: Path = BASE_DIR / "tmp" / "uploads"

    WEBSITE_STATS_URL: str = "https://waleed-zone.up.railway.app/api/stats"
    WEBSITE_STATS_TOKEN: str | None = None

    @property
    def admin_ids(self) -> list[int]:
        """معرفات المالكين كقائمة أرقام."""
        ids: list[int] = []
        for raw in self.ADMIN_IDS.split(","):
            raw = raw.strip()
            if raw.isdigit():
                ids.append(int(raw))
        return ids

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
