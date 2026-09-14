"""وحدة استخراج بيانات وروابط SteamRIP وBuzzHeavier لحظياً."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Mapping
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from curl_cffi import AsyncSession as CurlAsyncSession

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

BZZHR_BROWSER_TIMEOUT_MS = 30_000
BZZHR_CLOUDFLARE_TIMEOUT_MS = 45_000

# تشغيل متصفح Chromium واحد في كل مرة حتى لا تنفجر الذاكرة على Railway/Trial.
_BZZHR_BROWSER_LOCK = asyncio.Lock()


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
                    # density descriptor؛ نعطيه وزناً حتى 2x يتغلب على 1x.
                    score = float(descriptor[:-1]) * 10_000
            except ValueError:
                pass

        candidates.append((score, image_url))

    if not candidates:
        return None

    # عند غياب descriptors نحافظ على آخر URL، وهو غالباً النسخة الأكبر في WordPress.
    return max(enumerate(candidates), key=lambda item: (item[1][0], item[0]))[1][1]


def _extract_game_image(soup: BeautifulSoup, page_url: str) -> str | None:
    """استخرج صورة اللعبة الحقيقية مع دعم lazy-loading في SteamRIP/WordPress.

    بعض صفحات SteamRIP تضع صورة PNG صغيرة داخل ``src`` بصيغة ``data:image``
    كـ placeholder، بينما الرابط الحقيقي يكون في ``data-lazy-src`` أو ``data-src``
    أو ``srcset``. لذلك لا يجوز الاعتماد على ``src`` وحده.
    """
    image_elements = list(soup.select(".entry-content img"))
    if not image_elements:
        image_elements = list(soup.select("article img, main img"))
    if not image_elements:
        image_elements = list(soup.find_all("img"))

    # أولاً: خصائص lazy-load المباشرة؛ هذه أدق من src لأن src قد يكون placeholder.
    direct_attrs = (
        "data-lazy-src",
        "data-src",
        "data-original",
        "data-orig-src",
        "data-cfsrc",
    )
    srcset_attrs = (
        "data-lazy-srcset",
        "data-srcset",
        "srcset",
    )

    for img in image_elements:
        for attr in direct_attrs:
            image_url = _normalize_image_url(img.get(attr), page_url)
            if image_url:
                return image_url

        for attr in srcset_attrs:
            image_url = _image_from_srcset(img.get(attr), page_url)
            if image_url:
                return image_url

        image_url = _normalize_image_url(img.get("src"), page_url)
        if image_url:
            return image_url

    # fallback: metadata الاجتماعية عادة تحتوي الغلاف الحقيقي حتى لو كان المحتوى lazy.
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

    return None


def _host_matches_bzzhr(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    return any(host == mirror or host.endswith("." + mirror) for mirror in BZZHR_MIRRORS)


def _is_bzzhr_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and _host_matches_bzzhr(parsed.hostname or "")


def _is_steamrip_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except Exception:
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return parsed.scheme in {"http", "https"} and host == "steamrip.com"


def _safe_url_for_log(url: str) -> str:
    """لا تسجل query الموقّع حتى لا نسرّب token رابط التحميل."""
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _looks_like_direct_download(url: str) -> bool:
    """تحقق محافظ من شكل رابط BuzzHeavier المباشر الموقّع."""
    try:
        parsed = urlsplit(url)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "d":
        return False

    # BuzzHeavier يعيد حالياً token موقّعاً باسم v.
    return bool(parse_qs(parsed.query).get("v"))


def _looks_like_cloudflare_challenge(status: int, html: str) -> bool:
    """ميّز صفحة Cloudflare الحقيقية قبل تشغيل solver الثقيل."""
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
    parsed = urlsplit(normalized)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []

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

    for element in soup.select('[hx-get*="/download"]'):
        hx_get = (element.get("hx-get") or "").strip()
        if not hx_get:
            continue

        endpoint = _normalize_url(hx_get, page_url)
        if _is_bzzhr_url(endpoint):
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


def _configured_proxy() -> str | None:
    """Proxy اختياري للبيئات التي يحجب فيها المزود IP مركز البيانات."""
    value = (os.getenv("BZZHR_PROXY_URL") or "").strip()
    return value or None


async def fetch_game_data(page_url: str) -> dict:
    """كشط صفحة SteamRIP واستخراج بيانات اللعبة وروابط الاستضافة الحالية."""
    page_url = _normalize_url(page_url)
    if not _is_steamrip_url(page_url):
        raise ValueError("الرابط يجب أن يكون من steamrip.com")

    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        timeout=25.0,
    ) as client:
        response = await client.get(page_url)
        response.raise_for_status()

    final_page_url = str(response.url)
    if not _is_steamrip_url(final_page_url):
        raise RuntimeError("SteamRIP أعاد توجيهاً خارج steamrip.com")

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

    image_url = _extract_game_image(soup, final_page_url)
    if image_url:
        logger.info("SteamRIP game image found: %s", _safe_url_for_log(image_url))
    else:
        logger.warning("SteamRIP game image was not found for %s", final_page_url)

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

        # لا نعيد روابط SteamRIP الداخلية كسيرفر تحميل.
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


async def _resolve_candidate_fast(
    candidate_url: str,
    source_page_url: str | None = None,
) -> str | None:
    """Fast path بدون Browser. ينجح إذا أعاد BZZHR الصفحة الحقيقية مباشرة."""
    session_headers = dict(HEADERS)
    referer = _source_referer(source_page_url)
    if referer:
        session_headers["Referer"] = referer

    session_kwargs: dict[str, object] = {
        "impersonate": "chrome",
        "headers": session_headers,
    }
    proxy = _configured_proxy()
    if proxy:
        session_kwargs["proxy"] = proxy

    async with CurlAsyncSession(**session_kwargs) as session:
        page_response = await session.get(
            candidate_url,
            timeout=20,
            allow_redirects=False,
        )

        logger.info(
            "BZZHR fast page HTTP %s for %s",
            page_response.status_code,
            _safe_url_for_log(candidate_url),
        )

        if page_response.status_code != 200:
            location = page_response.headers.get("Location") or page_response.headers.get("location")
            if location:
                logger.info(
                    "BZZHR fast redirect target: %s",
                    _safe_url_for_log(_normalize_url(location, candidate_url)),
                )
            return None

        page_url = str(page_response.url or candidate_url)
        if not _is_bzzhr_url(page_url):
            return None

        signed_endpoint = _extract_signed_download_endpoint(
            page_response.text,
            page_url,
        )
        if not signed_endpoint:
            return None

        hx_headers = {
            "Accept": "*/*",
            "HX-Request": "true",
            "HX-Current-URL": page_url,
            "Referer": page_url,
        }

        response = await session.get(
            signed_endpoint,
            headers=hx_headers,
            timeout=20,
            allow_redirects=False,
        )

        logger.info(
            "BZZHR fast download HTTP %s for %s",
            response.status_code,
            _safe_url_for_log(signed_endpoint),
        )

        if response.status_code not in {200, 204}:
            return None

        return _direct_link_from_headers(response.headers, signed_endpoint)


def _browser_fetch_hx_redirect(
    context: object,
    page_url: str,
    signed_download_url: str,
    timeout_ms: int,
    source_page_url: str | None = None,
) -> str | None:
    """نفذ HTMX داخل نفس Browser context والكوكيز التي فتحت صفحة الملف."""
    browser_page = context.new_page()
    try:
        referer = _source_referer(source_page_url)
        if referer:
            browser_page.set_extra_http_headers({"Referer": referer})

        browser_page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )

        if not _is_bzzhr_url(browser_page.url):
            logger.warning(
                "BZZHR browser navigation left provider: %s",
                _safe_url_for_log(browser_page.url),
            )
            return None

        result = browser_page.evaluate(
            """
            async ({ signedDownloadUrl, pageUrl }) => {
              const response = await fetch(signedDownloadUrl, {
                method: 'GET',
                credentials: 'same-origin',
                redirect: 'manual',
                headers: {
                  'Accept': '*/*',
                  'HX-Request': 'true',
                  'HX-Current-URL': pageUrl
                }
              });

              const headers = {};
              for (const [key, value] of response.headers.entries()) {
                headers[key] = value;
              }

              return {
                status: response.status,
                headers
              };
            }
            """,
            {
                "signedDownloadUrl": signed_download_url,
                "pageUrl": page_url,
            },
        )
    finally:
        browser_page.close()

    try:
        status = int(result.get("status") or 0)
    except (AttributeError, TypeError, ValueError):
        return None

    if status not in {200, 204}:
        logger.warning(
            "BZZHR browser download returned HTTP %s for %s",
            status,
            _safe_url_for_log(signed_download_url),
        )
        return None

    headers = result.get("headers")
    if not isinstance(headers, Mapping):
        return None

    return _direct_link_from_headers(headers, signed_download_url)


def _browser_page_result(
    page: object,
    candidate: str,
) -> tuple[str | None, bool]:
    """أعد signed endpoint وهل الصفحة Cloudflare challenge."""
    status = int(getattr(page, "status", 0) or 0)
    page_url = str(getattr(page, "url", "") or candidate)
    html = _page_html(page)

    if not _is_bzzhr_url(page_url):
        logger.warning(
            "BZZHR browser page redirected outside provider: %s",
            _safe_url_for_log(page_url),
        )
        return None, False

    signed_endpoint = _extract_signed_download_endpoint(html, page_url)
    if signed_endpoint:
        return signed_endpoint, False

    challenge = _looks_like_cloudflare_challenge(status, html)
    if not challenge:
        logger.warning(
            "Signed BZZHR hx-get was not found for %s (HTTP %s)",
            _safe_url_for_log(page_url),
            status or "unknown",
        )

    return None, challenge


def _resolve_candidates_with_browser_sync(
    candidates: list[str],
    source_page_url: str | None = None,
) -> str | None:
    """Browser fallback: تصفح عادي أولاً، وCloudflare solver فقط عند وجود challenge فعلي."""
    try:
        from scrapling.fetchers import StealthySession
    except ImportError:
        logger.exception(
            "Scrapling browser fetchers are not installed; "
            "cannot resolve protected BZZHR pages."
        )
        return None

    executable_path = os.getenv("SCRAPLING_EXECUTABLE_PATH") or None
    referer = _source_referer(source_page_url)
    proxy = _configured_proxy()

    session_kwargs: dict[str, object] = {
        "headless": True,
        "block_webrtc": True,
        "solve_cloudflare": False,
        "google_search": False,
    }
    if executable_path:
        session_kwargs["executable_path"] = executable_path
    if proxy:
        session_kwargs["proxy"] = proxy

    request_headers = {"Referer": referer} if referer else None

    with StealthySession(**session_kwargs) as session:
        for candidate in candidates:
            logger.info(
                "Trying BZZHR browser mirror: %s",
                _safe_url_for_log(candidate),
            )

            try:
                page = session.fetch(
                    candidate,
                    network_idle=False,
                    solve_cloudflare=False,
                    google_search=False,
                    extra_headers=request_headers,
                    timeout=BZZHR_BROWSER_TIMEOUT_MS,
                )
            except Exception as exc:
                logger.warning(
                    "BZZHR browser normal fetch failed for %s: %s",
                    _safe_url_for_log(candidate),
                    exc,
                )
                continue

            signed_endpoint, challenge = _browser_page_result(page, candidate)

            # لا نشغّل Cloudflare solver بشكل أعمى. رسالة "No Cloudflare challenge found"
            # من Scrapling تحصل عندما يُطلب solver لصفحة عادية، وتضيف تأخيراً كبيراً.
            if not signed_endpoint and challenge:
                logger.info(
                    "Cloudflare challenge detected for %s; retrying with solver.",
                    _safe_url_for_log(candidate),
                )
                try:
                    page = session.fetch(
                        candidate,
                        network_idle=False,
                        solve_cloudflare=True,
                        google_search=False,
                        extra_headers=request_headers,
                        timeout=BZZHR_CLOUDFLARE_TIMEOUT_MS,
                    )
                except Exception as exc:
                    logger.warning(
                        "BZZHR Cloudflare retry failed for %s: %s",
                        _safe_url_for_log(candidate),
                        exc,
                    )
                    continue

                signed_endpoint, _ = _browser_page_result(page, candidate)

            if not signed_endpoint:
                continue

            page_url = str(getattr(page, "url", "") or candidate)
            logger.info(
                "Signed BZZHR endpoint found for %s",
                _safe_url_for_log(page_url),
            )

            direct_link = _browser_fetch_hx_redirect(
                session.context,
                page_url,
                signed_endpoint,
                BZZHR_BROWSER_TIMEOUT_MS,
                source_page_url,
            )
            if direct_link:
                logger.info("BZZHR direct link resolved successfully via browser.")
                return direct_link

    return None


async def extract_bzzhr_direct_link(
    bzzhr_url: str,
    source_page_url: str | None = None,
) -> str | None:
    """استخرج رابط الملف المباشر من أي رابط BZZHR/BuzzHeavier صالح.

    file-id ديناميكي ويأتي من SteamRIP لكل لعبة. نجرب HTTP سريعاً أولاً ثم
    Browser stealth. الـ Cloudflare solver لا يعمل إلا إذا ظهرت challenge حقيقية.
    يمكن ضبط BZZHR_PROXY_URL اختيارياً إذا كانت IP بيئة الاستضافة محجوبة.
    """
    candidates = _bzzhr_candidates(bzzhr_url)
    if not candidates:
        logger.warning("Invalid BZZHR URL: %s", _safe_url_for_log(bzzhr_url))
        return None

    for candidate in candidates:
        try:
            logger.info(
                "Trying BZZHR fast mirror: %s",
                _safe_url_for_log(candidate),
            )
            direct_link = await _resolve_candidate_fast(candidate, source_page_url)
            if direct_link:
                logger.info("BZZHR direct link resolved successfully via fast path.")
                return direct_link
        except Exception as exc:
            logger.warning(
                "BZZHR fast mirror failed for %s: %s",
                _safe_url_for_log(candidate),
                exc,
            )

    # المتصفح ثقيل؛ لا نشغّل أكثر من نسخة في نفس process.
    async with _BZZHR_BROWSER_LOCK:
        try:
            direct_link = await asyncio.to_thread(
                _resolve_candidates_with_browser_sync,
                candidates,
                source_page_url,
            )
        except Exception:
            logger.exception(
                "BZZHR browser resolver crashed for %s",
                _safe_url_for_log(bzzhr_url),
            )
            return None

    if direct_link:
        return direct_link

    logger.warning(
        "لم يتم العثور على رابط مباشر من BZZHR بعد تجربة HTTP والمتصفح: %s",
        _safe_url_for_log(bzzhr_url),
    )
    return None
