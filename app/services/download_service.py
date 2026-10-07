"""One download resolver for normal and historical SteamRIP callbacks.

Release read transactions before public HTTP and re-read publication/revision/source
before using the result. No signed destination is stored in the catalog.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Application
from database import repositories as repo
from app.utils.website import website_download_url
from integrations.public_http import public_url
from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link, _is_bzzhr_url

_ACTIVE: set[tuple[int, int]] = set()


def manual_url(value: str, hosts: set[str] | None = None) -> str:
    if len(value) > 2000 or any(c.isspace() for c in value):
        raise ValueError("INVALID_SOURCE")
    hosts = hosts if hosts is not None else {h.strip().lower() for h in get_settings().LEGACY_DOWNLOAD_ALLOWED_HOSTS.split(",") if h.strip()}
    public_url(value, hosts)
    if urlsplit(value).netloc != urlsplit(value).hostname:
        raise ValueError("INVALID_SOURCE")
    return value


async def resolve_application_download(session: AsyncSession, application_id: int):
    app = await repo.get_active_application(session, application_id)
    if not app:
        raise ValueError("SOURCE_REMOVED")
    source = await repo.get_delivery_source(session, app.id)
    snapshot = (app.revision, app.shrankme_url, app.devupload_url)
    if source:
        url = website_download_url(app.id)
        if not url:
            raise ValueError("INVALID_SOURCE")
        await session.commit()
        return app, url, "telegram"
    custom, original = app.shrankme_url, app.devupload_url
    await session.commit()  # No transaction (including middleware reads) across HTTP.
    if custom:
        url, provider = manual_url(custom), "external"
    elif original and urlsplit(original).hostname in {"steamrip.com", "www.steamrip.com"}:
        public_url(original, {"steamrip.com", "www.steamrip.com"})
        async with asyncio.timeout(30):
            data = await fetch_game_data(original)
            bzzhr = next((u for u in data.get("servers", {}).values() if _is_bzzhr_url(u)), None)
            if not bzzhr:
                raise ValueError("BZZHR_NOT_FOUND")
            url = await extract_bzzhr_direct_link(bzzhr, source_page_url=original)
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
    if (not current or not current.active or not current.published or current_source
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
        if provider != "telegram":
            await repo.increment_downloads(session, app.id)
            await repo.add_download(session, call.from_user.id, app.id)
            await session.commit()
        if edit:
            await call.message.edit_text(text, reply_markup=None)
        else:
            await call.message.answer(text)
    except (ValueError, TimeoutError):
        await session.rollback()
        await call.message.answer("تعذر تجهيز الرابط حاليًا. قد يكون المصدر تغيّر أو يحتاج تحققًا بشريًا؛ أعد المحاولة بعد قليل.")
    except Exception:
        await session.rollback()
        # Never log exception text: HTTP exceptions can contain signed endpoints.
        import logging
        logging.getLogger(__name__).warning("download failed application_id=%s category=unavailable", application_id)
        await call.message.answer("تعذر تجهيز التحميل. أعد المحاولة بعد قليل.")
    finally:
        _ACTIVE.discard(key)
