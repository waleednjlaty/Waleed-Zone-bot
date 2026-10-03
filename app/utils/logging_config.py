"""إعداد التسجيل (Logging) — بدون أي بيانات حساسة في المخرجات."""

from __future__ import annotations

import logging
import os
import re
import sys

from config import get_settings

_CONFIGURED = False


def redact(value: str) -> str:
    for key, secret in os.environ.items():
        if secret and re.search(
            r"TOKEN|PASSWORD|SECRET|SIGNING_KEY|API_KEY|DATABASE_URL|PROXY_URL", key, re.I
        ):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(
        r'https?://api\.telegram\.org/(?:file/)?bot[^\s\'"<>]+',
        "[TELEGRAM_URL_REDACTED]",
        value,
        flags=re.I,
    )
    value = re.sub(
        r'postgres(?:ql)?(?:\+asyncpg)?://[^\s\'"<>]+', "[DATABASE_URL_REDACTED]", value, flags=re.I
    )
    value = re.sub(r'https?://[^\s\'"<>]+[?][^\s\'"<>]+', "[URL_QUERY_REDACTED]", value, flags=re.I)
    value = re.sub(
        r'https?://[^\s/@\'"<>]+:[^\s/@\'"<>]+@[^\s\'"<>]+',
        "[URL_CREDENTIALS_REDACTED]",
        value,
        flags=re.I,
    )
    value = re.sub(
        r'(?i)(authorization|cookie|password|bot_token|database_url|[\w]*signing_key|website_stats_token|[\w]*secret_access_key|api_key)([\'"\s]*[:=][\'"\s]*)(?:Bearer\s+)?[^\s,;\'"}]+',
        r"\1\2[REDACTED]",
        value,
    )
    # Cookies contain multiple values; strip the entire header line.
    value = re.sub(r'(?im)(cookie[\s\'"=:]+)[^\r\n]+', r"\1[REDACTED]", value)
    value = re.sub(r"(?im)(cookie\s*:\s*)[^\r\n]+", r"\1[REDACTED]", value)
    return value


class SecretRedactingFormatter(logging.Formatter):
    def format(self, record):
        rendered = super().format(record)
        try:
            settings = get_settings()
            for secret in (
                settings.BOT_TOKEN,
                settings.DATABASE_URL,
                settings.WEBSITE_STATS_TOKEN,
                settings.IMGBB_API_KEY,
            ):
                if secret:
                    rendered = rendered.replace(secret, "[REDACTED]")
        except Exception:
            pass
        return redact(rendered)


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
