"""وحدة استخراج بيانات وروابط SteamRIP وBuzzHeavier لحظياً."""

from __future__ import annotations

import asyncio
import unicodedata
import logging
import aiohttp
import re
from yarl import URL
from collections.abc import Mapping
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from integrations.public_http import ExactHostCookieJar, fetch_public_response, public_url

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
_BZZHR_BACKOFF: dict[str, float] = {}
BZZHR_FILE_HOSTS = set(BZZHR_MIRRORS) | {"www." + h for h in BZZHR_MIRRORS} | {"fafda.to", "ts.bzzhr.co", "ts.buzzheavier.com"}


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
    return (any(marker in body for marker in ("cf-chl-", "/cdn-cgi/challenge-platform/"))
            or bool(re.search(r"<title[^>]*>\s*(just a moment|attention required)", body))
            or bool(re.search(r"<(?:div|form)[^>]+(?:class|id)=[\"\'][^\"\']*cf-turnstile", body))
            or status not in {200, 204, 206} and "verify you are human" in body)


def _identify_server(url: str, text: str) -> str:
    combined = f"{url} {text}".lower()
    for key, name in KNOWN_SERVERS.items():
        if key in combined:
            return name
    return "🔗 رابط تحميل"


def _bzzhr_candidates(url: str) -> list[str]:
    """Use the advertised host only: live mirrors do not necessarily share file IDs."""
    if not _is_bzzhr_url(url):
        return []
    parsed = urlsplit(url)
    return [url] if (re.fullmatch(r"/[A-Za-z0-9_-]+/?", parsed.path)
                    and not parsed.query) else []


def _extract_signed_download_endpoints(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base = urlsplit(page_url)
    resource = base.path.rstrip("/")
    endpoints = []
    for element in soup.select('a[hx-get], button[hx-get], a[data-hx-get], button[data-hx-get]'):
        raw = element.get("hx-get") or element.get("data-hx-get") or ""
        if len(raw) > 4096 or any(c.isspace() or unicodedata.category(c) in {"Cc", "Cf"} for c in raw):
            continue
        endpoint = urljoin(page_url, raw)
        if not _is_bzzhr_url(endpoint):
            continue
        parsed = urlsplit(endpoint)
        if (parsed.hostname != base.hostname or not parsed.path.startswith(resource + "/")
                or re.search(r"/(preview|delete|remove|login|account)(/|$)", parsed.path, re.I)
                or any(unicodedata.category(c) in {"Cc", "Cf"} or c == "\\" for c in unquote(parsed.path + parsed.query))):
            continue
        if endpoint not in endpoints:
            endpoints.append(endpoint)
        if len(endpoints) >= 3:
            break
    return endpoints


def _extract_signed_download_endpoint(html: str, page_url: str) -> str | None:
    endpoints = _extract_signed_download_endpoints(html, page_url)
    return endpoints[0] if endpoints else None


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

    payload, _, final_page_url, headers, status = await _fetch_provider(page_url,'steamrip_page',page_url,
        allowed_hosts={'steamrip.com','www.steamrip.com'},headers=BROWSER_HEADERS,raise_status=False)
    page_text=payload.decode('utf-8','replace')
    _require_success(status,page_text,headers,'steamrip_page',page_url)
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
        elif _is_bzzhr_url(href) and href not in servers.values():
            servers[server_name + " " + str(len(servers) + 1)] = href

    return {
        "title": title,
        "size": size,
        "image_url": image_url,
        "page_url": final_page_url,
        "servers": servers,
    }


class ProviderResolutionError(ValueError):
    """Only safe categories/stages: no upstream message, cookie or signature."""
    def __init__(self, code, stage, source, status=None):
        super().__init__(code)
        self.code, self.stage, self.host, self.status = code, stage, urlsplit(source).hostname, status


async def _fetch_provider(url, stage, source, **kwargs):
    try:
        return await fetch_public_response(url, **kwargs)
    except (ValueError, TimeoutError, aiohttp.ClientError) as error:
        code = "PROVIDER_TIMEOUT" if isinstance(error, TimeoutError) else "INVALID_SOURCE" if isinstance(error, ValueError) else "PROVIDER_UNAVAILABLE"
        raise ProviderResolutionError(code, stage, source) from None


def _require_success(status, body, headers, stage, source):
    if _looks_like_cloudflare_challenge(status, body) or headers.get("cf-mitigated") == "challenge":
        raise ProviderResolutionError("PROVIDER_CHALLENGE", stage, source, status)
    if status in {404, 410}:
        raise ProviderResolutionError("SOURCE_REMOVED", stage, source, status)
    if status == 429:
        raise ProviderResolutionError("PROVIDER_RATE_LIMITED", stage, source, status)
    if status == 401:
        raise ProviderResolutionError("PROVIDER_LOGIN_REQUIRED", stage, source, status)
    if status == 403:
        raise ProviderResolutionError("PROVIDER_FORBIDDEN", stage, source, status)
    if status not in {200, 204, 206, 301, 302, 303, 307, 308}:
        raise ProviderResolutionError("PROVIDER_UNAVAILABLE", stage, source, status)


async def _validate_file(destination):
    _, content_type, final, headers, status = await _fetch_provider(
        destination, 'file_probe', destination, allowed_hosts=BZZHR_FILE_HOSTS, timeout=10, raise_status=False,
        method="HEAD", headers_only=True,
    )
    if status in {405, 501}:
        _, content_type, final, headers, status = await _fetch_provider(
            destination, 'file_probe', destination, allowed_hosts=BZZHR_FILE_HOSTS, timeout=10, raise_status=False,
            headers={"Range": "bytes=0-0"}, headers_only=True,
        )
    _require_success(status, "", headers, "file_probe", destination)
    disposition = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    if (not _looks_like_direct_download(final) or status not in {200, 206}
            or (not disposition.lower().startswith("attachment") and not content_type)
            or content_type.split(";", 1)[0].lower() in {"text/html", "application/xhtml+xml", "application/json"}):
        raise ProviderResolutionError("FINAL_DESTINATION_NOT_FILE", "file_probe", destination, status)
    return final


async def _resolve_candidate_fast(candidate_url: str, source_page_url: str | None = None) -> str | None:
    hosts = set(BZZHR_MIRRORS) | {"www." + h for h in BZZHR_MIRRORS}
    public_url(candidate_url, hosts)
    headers = dict(HEADERS)
    if _source_referer(source_page_url):
        headers["Referer"] = source_page_url
    jar = ExactHostCookieJar()
    body, _, page_url, page_headers, status = await _fetch_provider(
        candidate_url, 'bzzhr_page', candidate_url, allowed_hosts=hosts, headers=headers, max_bytes=1024 * 1024,
        timeout=10, raise_status=False, cookie_jar=jar,
    )
    html = body.decode("utf-8", "replace")
    _require_success(status, html, page_headers, "bzzhr_page", page_url)
    endpoints = _extract_signed_download_endpoints(html, page_url)
    if not endpoints:
        raise ProviderResolutionError("MISSING_DOWNLOAD_ACTION", "bzzhr_page", page_url, status)
    # Normalize response cookies through the same host-only jar, including expiry/deletion.
    from http.cookies import SimpleCookie
    raw_cookies = page_headers.get("Set-Cookie") or page_headers.get("set-cookie") or []
    for raw in ([raw_cookies] if isinstance(raw_cookies, str) else raw_cookies):
        cookies = SimpleCookie()
        cookies.load(raw)
        jar.update_cookies(cookies, URL(page_url))
    failure = None
    for endpoint in endpoints:
        try:
            session = jar.filter_cookies(URL(endpoint))
            scoped_cookie = "; ".join(f"{key}={value.value}" for key, value in session.items())
            if len(scoped_cookie) > 2048 or any(ord(c) < 32 for c in scoped_cookie):
                raise ProviderResolutionError("INVALID_PROVIDER_RESPONSE", "bzzhr_handoff", page_url)
            payload, _, _, response_headers, status = await _fetch_provider(
                endpoint, 'bzzhr_handoff', page_url, allowed_hosts=hosts,
                headers={"HX-Request": "true", "HX-Current-URL": page_url, "Referer": page_url,
                         **({"Cookie": scoped_cookie} if scoped_cookie else {})},
                max_bytes=64 * 1024, timeout=10, follow=False, raise_status=False, cookie_jar=jar,
            )
            _require_success(status, payload.decode("utf-8", "replace"), response_headers, "bzzhr_handoff", page_url)
            direct = _direct_link_from_headers(response_headers, endpoint)
            if not direct:
                raise ProviderResolutionError("MISSING_HX_REDIRECT", "bzzhr_handoff", page_url, status)
            return await _validate_file(direct)
        except ProviderResolutionError as error:
            failure = error
            if error.code in {"PROVIDER_CHALLENGE", "PROVIDER_LOGIN_REQUIRED", "PROVIDER_RATE_LIMITED"}:
                raise
    if failure:
        raise failure
    return None


async def extract_bzzhr_direct_link(bzzhr_url: str, source_page_url: str | None = None, *, strict=False) -> str | None:
    """Fresh bounded HTTP only. Optional strict mode exposes safe failure diagnostics."""
    candidates = _bzzhr_candidates(bzzhr_url)
    if not candidates:
        return None
    key = candidates[0]

    async def resolve():
        try:
            async with asyncio.timeout(25):
                return await _resolve_candidate_fast(key, source_page_url)
        except ProviderResolutionError as error:
            _BZZHR_BACKOFF[key] = asyncio.get_running_loop().time() + 10
            logger.warning("BZZHR failed stage=%s host=%s status=%s category=%s",
                error.stage, error.host, error.status, error.code)
            raise
        except (ValueError, TimeoutError, aiohttp.ClientError) as error:
            _BZZHR_BACKOFF[key] = asyncio.get_running_loop().time() + 10
            category = "PROVIDER_TIMEOUT" if isinstance(error, TimeoutError) else "PROVIDER_UNAVAILABLE"
            raise ProviderResolutionError(category, "bzzhr_page", key) from None
        finally:
            _BZZHR_INFLIGHT.pop(key, None)

    task = _BZZHR_INFLIGHT.get(key)
    if task is None:
        now = asyncio.get_running_loop().time()
        for source, expiry in list(_BZZHR_BACKOFF.items()):
            if expiry <= now:
                _BZZHR_BACKOFF.pop(source, None)
        if len(_BZZHR_BACKOFF) >= 32 and key not in _BZZHR_BACKOFF:
            _BZZHR_BACKOFF.pop(next(iter(_BZZHR_BACKOFF)))
        if len(_BZZHR_INFLIGHT) >= 2 or now < _BZZHR_BACKOFF.get(key, 0):
            if strict:
                raise ProviderResolutionError("PROVIDER_BUSY", "bzzhr_page", key)
            return None
        task = asyncio.create_task(resolve())
        _BZZHR_INFLIGHT[key] = task
    try:
        return await asyncio.shield(task)
    except ProviderResolutionError:
        if strict:
            raise
        return None
