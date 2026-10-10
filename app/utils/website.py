"""روابط التكامل مع موقع Waleed Zone.

البوت والموقع يقرآن ويعدلان نفس جدول applications.
هذه الوحدة تبني روابط عامة ثابتة فقط ولا تحمل أي سر.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from config import get_settings


def website_app_url(app_id: int, base_url: str | None = None) -> str | None:
    """Return the stable legacy app URL used by the website redirect layer.

    Invalid configuration fails closed and returns None so publishing to Telegram
    never depends on the website being configured correctly.
    """
    if not isinstance(app_id, int) or isinstance(app_id, bool) or not 0 < app_id <= 2147483647:
        return None

    raw = (base_url if base_url is not None else get_settings().WEBSITE_BASE_URL).strip()
    if not raw:
        return None

    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None

    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if parsed.path not in {"", "/"} or port not in {None, 443}:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None

    clean_path = parsed.path.rstrip("/")
    base = urlunsplit((parsed.scheme, parsed.netloc, clean_path, "", "")).rstrip("/")
    return f"{base}/app/{app_id}"


def website_download_url(app_id: int, base_url: str | None = None) -> str | None:
    url = website_app_url(app_id, base_url)
    return url.replace("/app/", "/download/") if url else None


def bot_application_url(app_id: int, username: str | None = None) -> str | None:
    """Stable Telegram app deep link: SteamRIP downloads stay inside the bot."""
    import re
    if not isinstance(app_id, int) or isinstance(app_id, bool) or not 0 < app_id <= 2147483647:
        return None
    name = username if username is not None else getattr(get_settings(), "BOT_USERNAME", "WaleedZone_bot")
    name = str(name or "").removeprefix("@")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", name):
        return None
    return f"https://t.me/{name}?start=app_{app_id}"
