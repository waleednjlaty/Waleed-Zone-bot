"""وحدة استخراج بيانات وروابط SteamRIP لحظياً (On-Demand Extractor)."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import aiohttp
import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
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


async def fetch_game_data(page_url: str) -> dict:
    """كشط بيانات صفحة اللعبة من SteamRIP واستخراج روابط السيرفرات المتوفرة."""

    async with httpx.AsyncClient(
        headers=HEADERS,
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


async def extract_bzzhr_direct_link(
    bzzhr_url: str,
) -> str | None:
    """استخراج رابط التحميل المباشر الحقيقي من BZZHR / Buzzheavier."""

    bzzhr_url = _normalize_url(bzzhr_url)

    if not bzzhr_url.startswith(("http://", "https://")):
        logger.warning("Invalid BZZHR URL: %s", bzzhr_url)
        return None

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                bzzhr_url,
                timeout=20,
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "BZZHR page returned HTTP %s",
                        response.status,
                    )
                    return None

                html = await response.text()
                final_page_url = str(response.url)

            soup = BeautifulSoup(html, "html.parser")
            download_endpoint = None

            download_element = soup.select_one('[hx-get*="/download"]')
            if download_element:
                hx_get = download_element.get("hx-get")
                if hx_get:
                    download_endpoint = _normalize_url(
                        hx_get,
                        final_page_url,
                    )

            if not download_endpoint:
                download_element = soup.select_one('a[href*="/download"]')
                if download_element:
                    href = download_element.get("href")
                    if href:
                        download_endpoint = _normalize_url(
                            href,
                            final_page_url,
                        )

            if not download_endpoint:
                download_endpoint = final_page_url.rstrip("/") + "/download"

            hx_headers = {
                "HX-Request": "true",
                "HX-Current-URL": final_page_url,
                "Referer": final_page_url,
            }

            async with session.get(
                download_endpoint,
                headers=hx_headers,
                timeout=20,
                allow_redirects=False,
            ) as download_response:
                logger.debug(
                    "BZZHR download endpoint returned HTTP %s",
                    download_response.status,
                )

                direct_link = download_response.headers.get("HX-Redirect")
                if direct_link:
                    direct_link = _normalize_url(
                        direct_link,
                        download_endpoint,
                    )
                    if direct_link.rstrip("/") != final_page_url.rstrip("/"):
                        return direct_link

                location = download_response.headers.get("Location")
                if location:
                    location = _normalize_url(
                        location,
                        download_endpoint,
                    )
                    if location.rstrip("/") != final_page_url.rstrip("/"):
                        return location

            logger.warning(
                "لم يتم العثور على رابط مباشر لـ BZZHR: %s",
                bzzhr_url,
            )
            return None

    except Exception:
        logger.exception(
            "فشل استخراج الرابط المباشر من BZZHR: %s",
            bzzhr_url,
        )
        return None
