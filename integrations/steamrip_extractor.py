"""وحدة استخراج بيانات وروابط SteamRIP لحظياً (On-Demand Extractor)."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from curl_cffi import AsyncSession


logger = logging.getLogger(__name__)


HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


KNOWN_SERVERS = {
    "buzzheavier": "⚡ BZZHR / Buzzheavier",
    "bzzhr": "⚡ BZZHR / Buzzheavier",
    "megadb": "🚀 MegaDB",
    "1fichier": "📁 1Fichier",
    "qiwi": "🥝 Qiwi",
    "gofile": "📦 Gofile",
    "torrent": "🧲 Torrent",
}

BZZHR_MIRRORS = (
    "bzzhr.to",
    "bzzhr.co",
    "buzzheavier.com",
)


def _normalize_url(url: str, base_url: str | None = None) -> str:
    """حوّل الروابط النسبية أو protocol-relative إلى رابط HTTP/HTTPS كامل."""
    value = (url or "").strip()
    if not value:
        return ""

    if value.startswith("//"):
        return "https:" + value

    if base_url:
        return urljoin(base_url, value)

    return value


def _identify_server(url: str, text: str) -> str:
    """تحديد اسم سيرفر التحميل اعتماداً على الرابط أو نص الزر."""
    combined = f"{url} {text}".lower()

    for key, name in KNOWN_SERVERS.items():
        if key in combined:
            return name

    return "🔗 رابط تحميل"


def _bzzhr_candidates(url: str) -> list[str]:
    """أنشئ قائمة مرايا BZZHR مع الحفاظ على نفس المسار والـ query."""
    normalized = _normalize_url(url)
    parsed = urlsplit(normalized)

    if not parsed.scheme or not parsed.netloc:
        return []

    hosts: list[str] = []
    original_host = parsed.netloc.lower()
    if original_host:
        hosts.append(original_host)

    for host in BZZHR_MIRRORS:
        if host not in hosts:
            hosts.append(host)

    return [
        urlunsplit(("https", host, parsed.path, parsed.query, ""))
        for host in hosts
    ]


def _is_bzzhr_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return False
    return host in BZZHR_MIRRORS


def _plain_download_endpoint(page_url: str) -> str:
    """كوّن /download من رابط صفحة BZZHR نفسها بدون التأثر بأي redirect خارجي."""
    parsed = urlsplit(page_url)
    path = parsed.path.rstrip("/") + "/download"
    return urlunsplit((parsed.scheme or "https", parsed.netloc, path, "", ""))


def _redirect_from_response(response, base_url: str, page_url: str) -> str | None:
    """اقرأ رابط التحميل النهائي من HX-Redirect أو Location."""
    direct_link = response.headers.get("HX-Redirect") or response.headers.get("hx-redirect")
    if direct_link:
        direct_link = _normalize_url(direct_link, base_url)
        if direct_link.rstrip("/") != page_url.rstrip("/"):
            return direct_link

    location = response.headers.get("Location") or response.headers.get("location")
    if location:
        location = _normalize_url(location, base_url)
        if location.rstrip("/") != page_url.rstrip("/"):
            return location

    return None


async def fetch_game_data(page_url: str) -> dict:
    """كشط بيانات صفحة اللعبة من SteamRIP واستخراج روابط السيرفرات المتوفرة."""

    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        **HEADERS,
    }

    async with httpx.AsyncClient(
        headers=browser_headers,
        follow_redirects=True,
        timeout=25.0,
    ) as client:
        response = await client.get(page_url)
        response.raise_for_status()

    final_page_url = str(response.url)
    soup = BeautifulSoup(response.text, "html.parser")

    title_el = soup.find("h1", class_="entry-title") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "Game Title"
    title = re.sub(
        r"\s*Free Download.*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    size = "—"
    size_match = re.search(
        r"Size\s*:\s*([\d\.]+\s*(?:GB|MB))",
        response.text,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1).strip()

    image_url = None
    img_el = soup.select_one(".entry-content img") or soup.find("img")
    if img_el and img_el.get("src"):
        image_url = _normalize_url(img_el["src"], final_page_url)

    download_buttons = soup.select(
        "a.shortc-button, "
        "a[href*='download'], "
        ".download-btn a, "
        ".entry-content a"
    )

    servers: dict[str, str] = {}

    for btn in download_buttons:
        raw_href = btn.get("href", "").strip()
        btn_text = btn.get_text(strip=True)

        if not raw_href or raw_href.startswith("#"):
            continue

        href = _normalize_url(raw_href, final_page_url)
        if not href:
            continue

        if "steamrip.com" in href.lower():
            continue

        server_name = _identify_server(href, btn_text)
        if server_name not in servers:
            servers[server_name] = href

    return {
        "title": title,
        "size": size,
        "image_url": image_url,
        "page_url": page_url,
        "servers": servers,
    }


async def _request_bzzhr_download(
    session: AsyncSession,
    page_url: str,
    download_endpoint: str,
) -> str | None:
    """أرسل طلب HTMX إلى endpoint التحميل وأعد الرابط النهائي إن وُجد."""
    hx_headers = {
        "Accept": "*/*",
        "HX-Request": "true",
        "HX-Current-URL": page_url,
        "Referer": page_url,
    }

    response = await session.get(
        download_endpoint,
        headers=hx_headers,
        timeout=20,
        allow_redirects=False,
    )

    logger.info(
        "BZZHR download endpoint HTTP %s for %s",
        response.status_code,
        download_endpoint,
    )

    return _redirect_from_response(response, download_endpoint, page_url)


async def _extract_from_bzzhr_candidate(candidate_url: str) -> str | None:
    """جرّب استخراج الرابط المباشر من مرآة BZZHR واحدة."""

    async with AsyncSession(
        impersonate="chrome",
        headers=HEADERS,
    ) as session:
        # أولاً نجرب endpoint القياسي مباشرة من رابط BZZHR الأصلي.
        # هذا يمنع الخطأ السابق الذي كان يبني /download من redirect إلى SteamRIP.
        plain_endpoint = _plain_download_endpoint(candidate_url)
        direct_link = await _request_bzzhr_download(
            session,
            candidate_url,
            plain_endpoint,
        )
        if direct_link:
            return direct_link

        # إذا كان endpoint القياسي غير كافٍ، نحاول قراءة hx-get من صفحة BZZHR.
        # لا نتبع redirects الخارجية حتى لا يتحول base URL إلى steamrip.com.
        page_response = await session.get(
            candidate_url,
            timeout=20,
            allow_redirects=False,
        )

        logger.info(
            "BZZHR page HTTP %s for %s",
            page_response.status_code,
            candidate_url,
        )

        if page_response.status_code != 200:
            location = page_response.headers.get("Location") or page_response.headers.get("location")
            if location:
                redirected = _normalize_url(location, candidate_url)
                logger.warning(
                    "BZZHR page redirected to %s",
                    redirected,
                )
            return None

        soup = BeautifulSoup(page_response.text, "html.parser")
        download_endpoint = None

        download_element = soup.select_one('[hx-get*="/download"]')
        if download_element:
            hx_get = download_element.get("hx-get")
            if hx_get:
                candidate_endpoint = _normalize_url(hx_get, candidate_url)
                if _is_bzzhr_url(candidate_endpoint):
                    download_endpoint = candidate_endpoint

        if not download_endpoint:
            download_element = soup.select_one('a[href*="/download"]')
            if download_element:
                href = download_element.get("href")
                if href:
                    candidate_endpoint = _normalize_url(href, candidate_url)
                    if _is_bzzhr_url(candidate_endpoint):
                        download_endpoint = candidate_endpoint

        if not download_endpoint:
            return None

        if download_endpoint == plain_endpoint:
            return None

        return await _request_bzzhr_download(
            session,
            candidate_url,
            download_endpoint,
        )


async def extract_bzzhr_direct_link(
    bzzhr_url: str,
) -> str | None:
    """استخراج رابط التحميل المباشر الحقيقي من BZZHR / Buzzheavier."""

    candidates = _bzzhr_candidates(bzzhr_url)
    if not candidates:
        logger.warning("Invalid BZZHR URL: %s", bzzhr_url)
        return None

    last_error: Exception | None = None

    for candidate in candidates:
        try:
            logger.info("Trying BZZHR mirror: %s", candidate)
            direct_link = await _extract_from_bzzhr_candidate(candidate)
            if direct_link:
                return direct_link
        except Exception as exc:
            last_error = exc
            logger.warning(
                "BZZHR mirror failed: %s (%s)",
                candidate,
                exc,
            )

    if last_error:
        logger.error(
            "فشل استخراج الرابط المباشر من جميع مرايا BZZHR: %s",
            bzzhr_url,
            exc_info=last_error,
        )
    else:
        logger.warning(
            "لم يتم العثور على رابط مباشر من أي مرآة BZZHR: %s",
            bzzhr_url,
        )

    return None
