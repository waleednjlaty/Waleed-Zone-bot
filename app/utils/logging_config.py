"""إعداد التسجيل (Logging) — بدون أي بيانات حساسة في المخرجات."""

from __future__ import annotations

import logging
import sys
import re
from config import get_settings

_CONFIGURED = False


class SecretRedactingFormatter(logging.Formatter):
    def format(self, record):
        rendered = super().format(record)
        try:
            settings = get_settings()
            for secret in (settings.BOT_TOKEN, settings.DATABASE_URL, settings.WEBSITE_STATS_TOKEN, settings.IMGBB_API_KEY):
                if secret:
                    rendered = rendered.replace(secret, "[REDACTED]")
        except Exception:
            pass
        rendered = re.sub(r"https?://api\.telegram\.org/(?:file/)?bot[^\s'\"]+", "[TELEGRAM_URL_REDACTED]", rendered)
        rendered = re.sub(r"postgres(?:ql)?(?:\+asyncpg)?://[^\s'\"]+", "[DATABASE_URL_REDACTED]", rendered)
        return rendered



def setup_logging(level: int = logging.INFO) -> None:
    """تهيئة logging مرة واحدة. لا نطبع أبدًا مفاتيح API أو توكنات."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        SecretRedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # خفض ضجيج المكتبات
    for noisy in ("aiogram", "httpx", "sqlalchemy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
