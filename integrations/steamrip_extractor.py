"""وحدة استخراج بيانات وروابط SteamRIP لحظياً (On-Demand Extractor)."""

from __future__ import annotations

import re
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

KNOWN_SERVERS = {
    "buzzheavier": "⚡ Buzzheavier",
    "megadb": "🚀 MegaDB",
    "1fichier": "📁 1Fichier",
    "qiwi": "🥝 Qiwi",
    "gofile": "📦 Gofile",
    "torrent": "🧲 Torrent",
}

def _identify_server(url: str, text: str) -> str:
    combined = (url + " " + text).lower()
    for key, name in KNOWN_SERVERS.items():
        if key in combined:
            return name
    return "🔗 رابط تحميل"


async def fetch_game_data(page_url: str) -> dict:
    """كشط بيانات صفحة اللعبة من SteamRIP واستخراج الروابط اللحظية."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=25.0) as client:
        response = await client.get(page_url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 1. استخراج العنوان
    title_el = soup.find("h1", class_="entry-title") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "Game Title"
    title = re.sub(r"\s*Free Download.*", "", title, flags=re.IGNORECASE).strip()

    # 2. استخراج الحجم
    size = "—"
    size_match = re.search(r"Size\s*:\s*([\d\.]+\s*(?:GB|MB))", response.text, re.IGNORECASE)
    if size_match:
        size = size_match.group(1).strip()

    # 3. استخراج صورة الغلاف
    image_url = None
    img_el = soup.select_one(".entry-content img") or soup.find("img")
    if img_el and img_el.get("src"):
        image_url = img_el["src"]

    # 4. استخراج روابط السيرفرات المتوفرة
    download_buttons = soup.select("a.shortc-button, a[href*='download'], .download-btn a, .entry-content a")
    servers = {}

    for btn in download_buttons:
        href = btn.get("href", "").strip()
        btn_text = btn.get_text(strip=True)
        if not href or href.startswith("#") or "steamrip.com" in href:
            continue
        
        server_name = _identify_server(href, btn_text)
        if server_name not in servers:
            servers[server_name] = href

        if len(servers) >= 4:
            break

    return {
        "title": title,
        "size": size,
        "image_url": image_url,
        "page_url": page_url,
        "servers": servers,
    }
import aiohttp
from bs4 import BeautifulSoup

async def extract_bzzhr_direct_link(bzzhr_url: str) -> str | None:
    """
    الدخول إلى صفحة BZZHR واستخراج رابط التحميل المباشر من زر 'Copy download link'
    """
    try:
        async with aiohttp.ClientSession() as session:
            # إضافة ترويسة (Headers) لتبدو كمتصفح حقيقي وتفادي الحظر
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            async with session.get(bzzhr_url, headers=headers, timeout=20) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # البحث عن الزر بجميع الطرق الممكنة في BZZHR
                for el in soup.find_all(['a', 'button']):
                    text = el.get_text(strip=True).lower()
                    
                    if "copy download link" in text or "copy" in text or "download" in text:
                        if el.name == 'a' and el.get('href') and not el['href'].startswith('#'):
                            return el['href']
                        elif el.get('data-clipboard-text'):
                            return el['data-clipboard-text']
                            
                return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"فشل استخراج الرابط من BZZHR: {e}")
        return None