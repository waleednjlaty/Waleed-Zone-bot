"""وحدة استخراج بيانات وروابط SteamRIP وBuzzHeavier لحظياً."""

from __future__ import annotations

import asyncio
import unicodedata
import logging
import aiohttp
import re
from collections.abc import Mapping
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from integrations.public_http import fetch_public_bytes, fetch_public_response, public_url

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    **HEADERS,
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

# Only two public HTTP resolutions per instance; no browser or challenge solver.
_BZZHR_INFLIGHT: dict[str, asyncio.Task] = {}
_BZZHR_BACKOFF_UNTIL = 0.0
BZZHR_FILE_HOSTS = set(BZZHR_MIRRORS) | {"www." + h for h in BZZHR_MIRRORS} | {"fafda.to", "ts.buzzheavier.com"}


def _normalize_url(url: str, base_url: str | None = None) -> str:
    """حوّل الروابط النسبية و//host إلى URL كامل."""
    value = (url or "").strip()
    if not value:
        return ""

    if value.startswith("//"):
        return "https:" + value

    if base_url:
        return urljoin(base_url, value)

    return value


def _normalize_image_url(url: str | None, base_url: str) -> str | None:
    """طبّع رابط صورة حقيقي وتجاهل placeholders مثل data:image/base64."""
    value = (url or "").strip()
    if not value or value.lower().startswith(("data:", "blob:", "javascript:")):
        return None

    normalized = _normalize_url(value, base_url)
    try:
        parsed = urlsplit(normalized)
    except Exception:
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return normalized


def _image_from_srcset(value: str | None, base_url: str) -> str | None:
    """اختر أكبر صورة صالحة من srcset/data-srcset."""
    if not value:
        return None

    candidates: list[tuple[float, str]] = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue

        pieces = item.split()
        raw_url = pieces[0]
        image_url = _normalize_image_url(raw_url, base_url)
        if not image_url:
            continue

        score = 0.0
        if len(pieces) > 1:
            descriptor = pieces[1].lower()
            try:
                if descriptor.endswith("w"):
                    score = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    score = float(descriptor[:-1]) * 10_000
            except ValueError:
                pass

        candidates.append((score, image_url))

    if not candidates:
        return None

    return max(enumerate(candidates), key=lambda item: (item[1][0], item[0]))[1][1]


def _image_from_element(img: object, page_url: str) -> str | None:
    """استخرج أفضل URL من عنصر img مع دعم lazy-loading وsrcset."""
    getter = getattr(img, "get", None)
    if getter is None:
        return None

    for attr in (
        "data-lazy-src",
        "data-src",
        "data-original",
        "data-orig-src",
        "data-cfsrc",
    ):
        image_url = _normalize_image_url(getter(attr), page_url)
        if image_url:
            return image_url

    for attr in (
        "data-lazy-srcset",
        "data-srcset",
        "srcset",
    ):
        image_url = _image_from_srcset(getter(attr), page_url)
        if image_url:
            return image_url

    return _normalize_image_url(getter("src"), page_url)


def _is_screenshot_image(img: object) -> bool:
    """استبعد الصور الموجودة داخل أقسام screenshots/gallery/carousel."""
    markers = ("screenshot", "screenshots", "gallery", "carousel", "slider")

    for parent in getattr(img, "parents", []):
        name = getattr(parent, "name", None)
        if name in {"article", "main", "body", "html"}:
            break

        parent_id = str(getattr(parent, "get", lambda *_: "")("id") or "").lower()
        classes = getattr(parent, "get", lambda *_: [] )("class") or []
        if isinstance(classes, str):
            classes = [classes]
        signature = " ".join([parent_id, *[str(c).lower() for c in classes]])
        if any(marker in signature for marker in markers):
            return True

    find_previous = getattr(img, "find_previous", None)
    if find_previous:
        heading = find_previous(["h2", "h3", "h4", "h5", "h6"])
        if heading:
            heading_text = heading.get_text(" ", strip=True).lower()
            if "screenshot" in heading_text:
                return True

    return False


def _extract_game_image(soup: BeautifulSoup, page_url: str) -> str | None:
    """استخرج الغلاف/الصورة الرئيسية للعبة، وليس صور الـScreenshots.

    SteamRIP قد يضع الغلاف خارج ``.entry-content`` بينما تكون صور الـScreenshots
    داخله؛ لذلك لا يجوز أخذ أول صورة من المحتوى. الأولوية تكون للصورة المميزة
    في القالب، ثم Open Graph، ثم صورة محتوى صالحة قبل قسم Screenshots.
    """

    # 1) صورة الغلاف/Featured image في قوالب WordPress الشائعة.
    featured_selectors = (
        "img.wp-post-image",
        ".post-thumbnail img",
        ".featured-image img",
        ".featured-media img",
        ".entry-image img",
        ".single-featured-image-header img",
        ".post-image img",
        ".thumbnail img",
    )
    for selector in featured_selectors:
        for img in soup.select(selector):
            image_url = _image_from_element(img, page_url)
            if image_url:
                return image_url

    # 2) WordPress/SEO plugins عادة تضع صورة الغلاف الحقيقية في metadata.
    # نعطي og:image أولوية على صور .entry-content حتى لا نلتقط screenshot.
    for selector in (
        'meta[property="og:image"]',
        'meta[property="og:image:secure_url"]',
        'meta[name="twitter:image"]',
        'meta[property="twitter:image"]',
    ):
        meta = soup.select_one(selector)
        if meta:
            image_url = _normalize_image_url(meta.get("content"), page_url)
            if image_url:
                return image_url

    # 3) fallback محافظ: صور المقال فقط، مع استبعاد أقسام screenshots/gallery.
    image_elements = list(soup.select(".entry-content img"))
    if not image_elements:
        image_elements = list(soup.select("article img, main img"))
    if not image_elements:
        image_elements = list(soup.find_all("img"))

    for img in image_elements:
        if _is_screenshot_image(img):
            continue
        image_url = _image_from_element(img, page_url)
        if image_url:
            return image_url

    return None


def _host_matches_bzzhr(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    return any(host == mirror or host.endswith("." + mirror) for mirror in BZZHR_MIRRORS)


def _is_bzzhr_url(url: str) -> bool:
    try:
        public_url(url,set(BZZHR_MIRRORS) | {'www.'+host for host in BZZHR_MIRRORS})
        return True
    except ValueError:
        return False


def _is_steamrip_url(url: str) -> bool:
    try:
        public_url(url,{'steamrip.com','www.steamrip.com'})
        return True
    except ValueError:
        return False


def _safe_url_for_log(url: str) -> str:
    """لا تسجل query الموقّع حتى لا نسرّب token رابط التحميل."""
    try:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.hostname or '', parsed.path, "", ""))
    except ValueError:
        return '[INVALID_URL]'


def _looks_like_direct_download(url: str) -> bool:
    """تحقق محافظ من شكل رابط BuzzHeavier المباشر الموقّع."""
    try:
        parsed = urlsplit(url)
    except Exception:
        return False

    if len(url) > 2000:
        return False
    try:
        public_url(url, BZZHR_FILE_HOSTS)
    except ValueError:
        return False

    if not re.fullmatch(r"/d/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.%()-]+)*", parsed.path):
        return False
    if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path + parsed.query):
        return False
    values = parse_qs(parsed.query).get("v", [])
    return len(values) == 1 and bool(values[0]) and not any(unicodedata.category(c) in {"Cc", "Cf"} or c == "\\" for c in unquote(parsed.path + parsed.query))



def _looks_like_cloudflare_challenge(status: int, html: str) -> bool:
    """ميّز التحقق البشري لإغلاق المعالجة بأمان."""
    body = (html or "").lower()
    markers = (
        "cf-chl-",
        "challenge-platform",
        "cf-turnstile",
        "just a moment",
        "verify you are human",
        "cloudflare ray id",
    )
    return status in {403, 429, 503} and any(marker in body for marker in markers)


def _identify_server(url: str, text: str) -> str:
    combined = f"{url} {text}".lower()
    for key, name in KNOWN_SERVERS.items():
        if key in combined:
            return name
    return "🔗 رابط تحميل"


def _bzzhr_candidates(url: str) -> list[str]:
    """جرّب نفس file-id على المرايا الرسمية بدون افتراض id ثابت."""
    normalized = _normalize_url(url)
    if not _is_bzzhr_url(normalized):
        return []
    parsed = urlsplit(normalized)

    original_host = (parsed.hostname or "").lower()
    if not _host_matches_bzzhr(original_host):
        return []

    hosts: list[str] = []
    if original_host:
        hosts.append(original_host)

    for host in BZZHR_MIRRORS:
        if host not in hosts:
            hosts.append(host)

    return [
        urlunsplit(("https", host, parsed.path, parsed.query, ""))
        for host in hosts
    ]


def _extract_signed_download_endpoint(html: str, page_url: str) -> str | None:
    """استخرج hx-get الحقيقي؛ لا نخترع /download لأنه يحتاج token موقّع."""
    soup = BeautifulSoup(html, "html.parser")

    for element in soup.select('[hx-get]'):
        hx_get = (element.get("hx-get") or "").strip()
        if not hx_get or any(c.isspace() or ord(c) < 32 for c in hx_get):
            continue

        endpoint = _normalize_url(hx_get, page_url)
        base, parsed = urlsplit(page_url), urlsplit(endpoint)
        file_id = base.path.strip('/').split('/')[0]
        if (_is_bzzhr_url(endpoint) and parsed.hostname == base.hostname
                and file_id and parsed.path.startswith('/' + file_id + '/')
                and not re.search(r'/(preview|delete|remove|login|account)(/|$)', parsed.path, re.I)):
            return endpoint

    return None


def _direct_link_from_headers(
    headers: Mapping[str, str],
    base_url: str,
) -> str | None:
    """اقرأ HX-Redirect/Location وتأكد أنه رابط ملف مباشر موقّع."""
    raw = (
        headers.get("HX-Redirect")
        or headers.get("hx-redirect")
        or headers.get("Location")
        or headers.get("location")
    )
    if not raw:
        return None

    if any(c.isspace() or ord(c) < 32 for c in raw) or "#" in raw or "\\" in raw:
        return None
    direct_link = _normalize_url(raw, base_url)
    if not _looks_like_direct_download(direct_link):
        return None

    return direct_link


def _page_html(page: object) -> str:
    body = getattr(page, "body", b"")
    if isinstance(body, bytes):
        encoding = getattr(page, "encoding", None) or "utf-8"
        return body.decode(encoding, "replace")
    return str(body or getattr(page, "html_content", "") or "")


def _source_referer(source_page_url: str | None) -> str | None:
    if source_page_url and _is_steamrip_url(source_page_url):
        return source_page_url
    return None


async def fetch_game_data(page_url: str) -> dict:
    """كشط صفحة SteamRIP واستخراج بيانات اللعبة وروابط الاستضافة الحالية."""
    page_url = _normalize_url(page_url)
    if not _is_steamrip_url(page_url):
        raise ValueError("الرابط يجب أن يكون من steamrip.com")

    payload, _, final_page_url = await fetch_public_bytes(page_url,
        allowed_hosts={'steamrip.com','www.steamrip.com'},headers=BROWSER_HEADERS)
    page_text=payload.decode('utf-8','replace')
    soup = BeautifulSoup(page_text, "html.parser")

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
        page_text,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1).strip()

    image_url = _extract_game_image(soup, final_page_url)
    if image_url:
        logger.info("SteamRIP game image found: %s", _safe_url_for_log(image_url))
    else:
        logger.warning("SteamRIP game image unavailable host=%s", urlsplit(final_page_url).hostname)

    download_buttons = soup.select(
        "a.shortc-button, "
        "a[href*='download'], "
        ".download-btn a, "
        ".entry-content a"
    )

    servers: dict[str, str] = {}

    for btn in download_buttons:
        raw_href = (btn.get("href") or "").strip()
        btn_text = btn.get_text(strip=True)

        if not raw_href or raw_href.startswith("#"):
            continue

        href = _normalize_url(raw_href, final_page_url)
        if not href:
            continue

        if _is_steamrip_url(href):
            continue

        server_name = _identify_server(href, btn_text)
        if server_name not in servers:
            servers[server_name] = href

    return {
        "title": title,
        "size": size,
        "image_url": image_url,
        "page_url": final_page_url,
        "servers": servers,
    }


async def _resolve_candidate_fast(candidate_url: str, source_page_url: str | None = None) -> str | None:
    hosts = set(BZZHR_MIRRORS) | {"www." + h for h in BZZHR_MIRRORS}
    public_url(candidate_url, hosts)
    headers = dict(HEADERS)
    if _source_referer(source_page_url):
        headers["Referer"] = source_page_url
    body, _, page_url, page_headers, status = await fetch_public_response(
        candidate_url, allowed_hosts=hosts, headers=headers, max_bytes=1024 * 1024,
        timeout=10, raise_status=False,
    )
    html = body.decode("utf-8", "replace")
    if status != 200 or _looks_like_cloudflare_challenge(status, html):
        return None
    endpoint = _extract_signed_download_endpoint(html, page_url)
    if not endpoint or urlsplit(endpoint).hostname != urlsplit(page_url).hostname:
        return None
    base = urlsplit(page_url)
    parsed = urlsplit(endpoint)
    if not parsed.path.startswith(base.path.rstrip("/") + "/") or re.search(r"/(preview|delete|remove|login|account)(/|$)", parsed.path, re.I):
        return None
    from http.cookies import SimpleCookie
    cookies = SimpleCookie()
    cookies.load(page_headers.get("Set-Cookie") or page_headers.get("set-cookie") or "")
    cookie_header = "; ".join(f"{key}={value.value}" for key, value in cookies.items())
    if len(cookie_header) > 2048 or any(ord(c) < 32 for c in cookie_header):
        return None
    _, _, _, response_headers, status = await fetch_public_response(
        endpoint, allowed_hosts=hosts,
        headers={"HX-Request": "true", "HX-Current-URL": page_url, "Referer": page_url,
                 **({"Cookie": cookie_header} if cookie_header else {})},
        max_bytes=64 * 1024, timeout=10, follow=False, raise_status=False,
    )
    if status not in {200, 204, 301, 302, 303, 307, 308}:
        return None
    direct = _direct_link_from_headers(response_headers, endpoint)
    if direct:
        _, content_type, _, _, final_status = await fetch_public_response(
            direct, allowed_hosts=BZZHR_FILE_HOSTS, method='HEAD', timeout=10,
            raise_status=False,
        )
        if final_status not in {200, 204} or not content_type or content_type in {
            'text/html', 'application/xhtml+xml', 'application/json'
        }:
            return None
    return direct


async def extract_bzzhr_direct_link(bzzhr_url: str, source_page_url: str | None = None) -> str | None:
    """Fresh bounded HTTP only. Challenges fail closed; never cache completed signed URLs."""
    global _BZZHR_BACKOFF_UNTIL
    candidates = _bzzhr_candidates(bzzhr_url)
    if not candidates:
        return None
    key = candidates[0]
    if key in _BZZHR_INFLIGHT:
        return await asyncio.shield(_BZZHR_INFLIGHT[key])
    if len(_BZZHR_INFLIGHT) >= 2 or asyncio.get_running_loop().time() < _BZZHR_BACKOFF_UNTIL:
        return None

    async def resolve():
        global _BZZHR_BACKOFF_UNTIL
        try:
            async with asyncio.timeout(25):
                for candidate in candidates:
                    try:
                        direct = await _resolve_candidate_fast(candidate, source_page_url)
                        if direct:
                            return direct
                    except (ValueError, TimeoutError, aiohttp.ClientError):
                        logger.warning("BZZHR public HTTP unavailable host=%s", urlsplit(candidate).hostname)
            _BZZHR_BACKOFF_UNTIL = asyncio.get_running_loop().time() + 10
            return None
        except TimeoutError:
            _BZZHR_BACKOFF_UNTIL = asyncio.get_running_loop().time() + 10
            return None
        finally:
            _BZZHR_INFLIGHT.pop(key, None)

    task = asyncio.create_task(resolve())
    _BZZHR_INFLIGHT[key] = task
    return await asyncio.shield(task)
