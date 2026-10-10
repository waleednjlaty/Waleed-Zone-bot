"""One download resolver for normal and historical SteamRIP callbacks.

Release read transactions before public HTTP and re-read publication/revision/source
before using the result. No signed destination is stored in the catalog.
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Application
from database import repositories as repo
from app.utils.website import website_download_url
from integrations.public_http import public_url
from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link, _is_bzzhr_url, _is_steamrip_url, ProviderResolutionError

_ACTIVE: set[tuple[int, int]] = set()


def manual_url(value: str, hosts: set[str] | None = None) -> str:
    if len(value) > 2000 or any(c.isspace() for c in value):
        raise ValueError("INVALID_SOURCE")
    hosts = hosts if hosts is not None else {h.strip().lower() for h in get_settings().LEGACY_DOWNLOAD_ALLOWED_HOSTS.split(",") if h.strip()}
    if _is_bzzhr_url(value):
        parsed = urlsplit(value)
        if not re.fullmatch(r"/[A-Za-z0-9_-]+/?", parsed.path) or parsed.query:
            raise ValueError("INVALID_SOURCE")
        return value
    public_url(value, hosts)
    if urlsplit(value).netloc != urlsplit(value).hostname:
        raise ValueError("INVALID_SOURCE")
    return value


def is_steamrip_application(app: Application) -> bool:
    """Dispatch on the validated *original source*, never a category/name guess.

    A SteamRIP page or BZZHR file page is resolved inside the Telegram bot.
    Everything else (including Telegram Files Channel and approved manual
    sources) belongs to the website's existing protected download flow.
    """
    original = getattr(app, "devupload_url", None) or ""
    custom = getattr(app, "shrankme_url", None) or ""
    return _is_steamrip_url(original) or _is_bzzhr_url(custom or original)


async def resolve_application_download(session: AsyncSession, application_id: int):
    app = await repo.get_active_application(session, application_id)
    if not app:
        raise ValueError("SOURCE_REMOVED")
    source = await repo.get_delivery_source(session, app.id)
    snapshot = (app.revision, app.shrankme_url, app.devupload_url)
    original = app.devupload_url
    if not is_steamrip_application(app):
        url = website_download_url(app.id)
        if not url:
            raise ValueError("INVALID_SOURCE")
        await session.commit()
        return app, url, "website"
    # Keep a source fingerprint to reject administrative edits during provider I/O.
    source_snapshot = (source.telegram_channel_username, source.telegram_message_id) if source else None
    custom = app.shrankme_url
    await session.commit()  # No transaction (including middleware reads) across HTTP.
    direct_source = custom if custom and _is_bzzhr_url(custom) else original if not custom and original and _is_bzzhr_url(original) else None
    if direct_source:
        url = await extract_bzzhr_direct_link(direct_source, strict=True)
        if not url:
            raise ValueError("PROVIDER_UNAVAILABLE")
        provider = "bzzhr"
    elif custom:
        url, provider = manual_url(custom), "external"
    elif original and urlsplit(original).hostname in {"steamrip.com", "www.steamrip.com"}:
        public_url(original, {"steamrip.com", "www.steamrip.com"})
        async with asyncio.timeout(30):
            data = await fetch_game_data(original)
            candidates = list(dict.fromkeys(u for u in data.get("servers", {}).values() if _is_bzzhr_url(u)))[:3]
            if not candidates:
                raise ValueError("BZZHR_NOT_FOUND")
            url, failure = None, None
            for bzzhr in candidates:
                try:
                    url = await extract_bzzhr_direct_link(bzzhr, source_page_url=original, strict=True)
                    if url:
                        break
                except ProviderResolutionError as error:
                    failure = error
                    if error.code in {"PROVIDER_CHALLENGE", "PROVIDER_LOGIN_REQUIRED", "PROVIDER_RATE_LIMITED", "PROVIDER_FORBIDDEN"}:
                        raise
            if not url and failure:
                raise failure
        if not url:
            raise ValueError("PROVIDER_UNAVAILABLE")
        provider = "bzzhr"
    else:
        if not original:
            raise ValueError("SOURCE_REMOVED")
        url, provider = manual_url(original), "external"
    current = await session.scalar(select(Application).where(Application.id == application_id)
        .execution_options(populate_existing=True))
    current_source = await repo.get_delivery_source(session, application_id)
    current_source_snapshot = ((current_source.telegram_channel_username, current_source.telegram_message_id)
                               if current_source else None)
    if (not current or not current.active or not current.published
            or current_source_snapshot != source_snapshot
            or (current.revision, current.shrankme_url, current.devupload_url) != snapshot):
        await session.rollback()
        raise ValueError("SOURCE_CHANGED")
    await session.commit()
    return current, url, provider


async def send_application_download(call, session: AsyncSession, application_id: int, *, edit=False):
    from app.utils.text import final_download_message
    key = (call.from_user.id, application_id)
    if key in _ACTIVE or len(_ACTIVE) >= 32:
        await call.answer("الطلب قيد المعالجة؛ انتظر قليلًا.")
        return
    _ACTIVE.add(key)
    try:
        await call.answer("⏳ جارٍ تجهيز المصدر...")
        app, url, provider = await resolve_application_download(session, application_id)
        text = final_download_message(app, url)
        # Commit counters before sending to Telegram; never hold a transaction during API I/O.
        if provider != "website":
            await repo.increment_downloads(session, app.id)
            await repo.add_download(session, call.from_user.id, app.id)
            await session.commit()
        if edit:
            await call.message.edit_text(text, reply_markup=None)
        else:
            await call.message.answer(text)
    except ProviderResolutionError as error:
        await session.rollback()
        import logging
        logging.getLogger(__name__).warning("download failed application_id=%s stage=%s host=%s status=%s category=%s",
            application_id, error.stage, error.host, error.status, error.code)
        messages = {
            "PROVIDER_CHALLENGE": "تعذّر وصول البوت إلى SteamRIP/BZZHR بسبب تحقق المصدر. أعد المحاولة لاحقًا من البوت.",
            "SOURCE_REMOVED": "ملف المصدر محذوف أو لم يعد متاحًا.",
            "MISSING_HX_REDIRECT": "المصدر لم يُرجع رابط الملف بعد طلب التنزيل.",
            "FINAL_DESTINATION_NOT_FILE": "خادم المصدر أعاد صفحة بدل ملف قابل للتنزيل.",
        }
        await call.message.answer(messages.get(error.code, "تعذر تجهيز رابط SteamRIP داخل البوت. أعد المحاولة لاحقًا."))
    except (ValueError, TimeoutError):
        await session.rollback()
        await call.message.answer("تعذر تجهيز رابط SteamRIP داخل البوت حاليًا. حاول مجددًا بعد قليل.")
    except Exception:
        await session.rollback()
        # Never log exception text: HTTP exceptions can contain signed endpoints.
        import logging
        logging.getLogger(__name__).warning("download failed application_id=%s category=unavailable", application_id)
        await call.message.answer("تعذر تجهيز التحميل. أعد المحاولة بعد قليل.")
    finally:
        _ACTIVE.discard(key)
