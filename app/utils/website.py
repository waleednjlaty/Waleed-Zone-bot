"""روابط التكامل مع موقع Waleed Zone.

نبقي الربط بسيطًا ورخيصًا: البوت يملك كتالوج التطبيقات، والموقع يقرأ
نفس جدول applications. هذه الوحدة تبني روابط عامة فقط ولا تحمل أي سر.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from config import get_settings


def website_app_url(app_id: int, base_url: str | None = None) -> str | None:
    """Return the stable legacy app URL used by the website redirect layer.

    Invalid configuration fails closed and returns None so publishing to Telegram
    never depends on the website being configured correctly.
    """
    if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0:
        return None

    raw = (base_url if base_url is not None else get_settings().WEBSITE_BASE_URL).strip()
    if not raw:
        return None

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None

    clean_path = parsed.path.rstrip("/")
    base = urlunsplit((parsed.scheme, parsed.netloc, clean_path, "", "")).rstrip("/")
    return f"{base}/app/{app_id}"
