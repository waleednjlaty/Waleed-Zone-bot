from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def _anchor_paths(self) -> "Settings":
        # المسار من .env قد يكون نسبيًا — نثبّته على جذر المشروع
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        return self

    # --- أساسي ---
    BOT_TOKEN: str = Field(repr=False)
    ADMIN_IDS: str = ""

    # --- القناة والمجموعة ---
    CHANNEL_ID: int | None = None
    CHANNEL_USERNAME: str | None = None
    GROUP_ID: int | None = None
    GROUP_USERNAME: str | None = None

    # Public file storage channel. A partial pair never falls back to main channel.
    FILES_CHANNEL_ID: int | None = None
    FILES_CHANNEL_USERNAME: str | None = None

    # --- ImgBB (رفع الصور) ---
    IMGBB_API_KEY: str | None = Field(default=None,repr=False)

    # --- قاعدة البيانات ---
    DATABASE_URL: str = Field(default=DEFAULT_DB_URL,repr=False)

    # --- سلوك عام ---
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB
    HTTP_MAX_RETRIES: int = 3
    DOWNLOAD_DIR: Path = BASE_DIR / "tmp" / "uploads"

    WEBSITE_BASE_URL: str = "https://waleed-zone.up.railway.app"
    WEBSITE_STATS_URL: str = "https://waleed-zone.up.railway.app/api/stats"
    WEBSITE_STATS_TOKEN: str | None = Field(default=None,repr=False)

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
