from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bot.db'}"
_SQLITE_PREFIX = "sqlite+aiosqlite:///"
CANONICAL_WEBSITE_URL = "https://www.waleedzone.xyz"


def normalize_database_url(url: str) -> str:
    """Anchor relative SQLite paths to the project root."""
    if url.startswith(_SQLITE_PREFIX):
        path = url[len(_SQLITE_PREFIX):]
        if path and not path.startswith(("/", "\\", ":")):
            return f"{_SQLITE_PREFIX}{BASE_DIR / path}"
    return url


def normalize_website_url(url: str) -> str:
    """Use the canonical public host when a legacy Railway URL is configured."""
    normalized = url.strip().rstrip("/")
    if normalized in {
        "http://waleed-zone.up.railway.app",
        "https://waleed-zone.up.railway.app",
        "http://www.waleedzone.xyz",
        "https://waleedzone.xyz",
        "http://waleedzone.xyz",
    }:
        return CANONICAL_WEBSITE_URL
    return normalized


class Settings(BaseSettings):
    """كل إعدادات البوت تُقرأ من ملف .env فقط — لا توجد أي أسرار داخل الكود."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def _normalize_settings(self) -> "Settings":
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        self.WEBSITE_BASE_URL = normalize_website_url(self.WEBSITE_BASE_URL)
        self.WEBSITE_STATS_URL = normalize_website_url(self.WEBSITE_STATS_URL)
        if self.WEBSITE_STATS_URL.rstrip("/").endswith("/api/stats"):
            self.WEBSITE_STATS_URL = self.WEBSITE_BASE_URL + "/api/stats"
        return self

    BOT_TOKEN: str = Field(repr=False)
    ADMIN_IDS: str = ""
    CHANNEL_ID: int | None = None
    CHANNEL_USERNAME: str | None = None
    GROUP_ID: int | None = None
    GROUP_USERNAME: str | None = None
    FILES_CHANNEL_ID: int | None = None
    FILES_CHANNEL_USERNAME: str | None = None

    IMGBB_API_KEY: str | None = Field(default=None, repr=False)
    DATABASE_URL: str = Field(default=DEFAULT_DB_URL, repr=False)

    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024 * 1024
    HTTP_MAX_RETRIES: int = 3
    DOWNLOAD_DIR: Path = BASE_DIR / "tmp" / "uploads"

    WEBSITE_BASE_URL: str = CANONICAL_WEBSITE_URL
    WEBSITE_STATS_URL: str = CANONICAL_WEBSITE_URL + "/api/stats"
    WEBSITE_STATS_TOKEN: str | None = Field(default=None, repr=False)

    # Direct URL imports and external download links require explicit allowlists.
    REMOTE_UPLOAD_ALLOWED_HOSTS: str = ""
    EXTERNAL_DOWNLOAD_ALLOWED_HOSTS: str = ""

    @property
    def admin_ids(self) -> list[int]:
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
