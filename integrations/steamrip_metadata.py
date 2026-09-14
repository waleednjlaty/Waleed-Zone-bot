"""Metadata helpers layered on top of the SteamRIP extractor.

SteamRIP changes its WordPress markup from time to time.  The low-level
extractor intentionally stays focused on links/images, while this module
normalizes user-facing metadata such as the game download size.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from .steamrip_extractor import BROWSER_HEADERS, fetch_game_data as _fetch_game_data

logger = logging.getLogger(__name__)

_SIZE_PATTERN = re.compile(
    r"\b(?:(?:download|file|game|archive|compressed|setup|repack)\s+)?"
    r"size\b\s*(?:[:\-–—]|is)?\s*"
    r"([0-9]+(?:[.,][0-9]+)?\s*(?:KB|MB|GB|TB))\b",
    re.IGNORECASE,
)


def _normalize_size(value: str) -> str:
    """Normalize spacing/unit while keeping the value shown by SteamRIP."""
    cleaned = " ".join((value or "").strip().split())
    match = re.fullmatch(
        r"([0-9]+(?:[.,][0-9]+)?)\s*(KB|MB|GB|TB)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""

    number = match.group(1)
    # A comma between digits is commonly used as a decimal separator on mirrors.
    if "," in number and "." not in number:
        number = number.replace(",", ".")
    return f"{number} {match.group(2).upper()}"


def extract_game_size(html: str) -> str:
    """Extract the game/download size from SteamRIP visible page text.

    We parse visible text instead of raw HTML so markup such as
    ``<strong>File Size:</strong> 112 GB`` is handled correctly.  The regex is
    deliberately label-based to avoid confusing RAM/storage requirements with
    the downloadable archive size.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove content that can contain unrelated sizes (scripts/styles) before
    # flattening the visible page text.
    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    visible_text = soup.get_text(" ", strip=True)
    match = _SIZE_PATTERN.search(visible_text)
    if match:
        return _normalize_size(match.group(1))

    # Some themes split the label/value across unusual wrappers.  Search a
    # small parent context around text nodes containing the word "size".
    for text_node in soup.find_all(string=re.compile(r"\bsize\b", re.IGNORECASE)):
        parent = getattr(text_node, "parent", None)
        if parent is None:
            continue
        context = parent.parent if getattr(parent, "parent", None) is not None else parent
        context_text = context.get_text(" ", strip=True)
        match = _SIZE_PATTERN.search(context_text)
        if match:
            return _normalize_size(match.group(1))

    return ""


async def fetch_game_data(page_url: str) -> dict:
    """Return SteamRIP data and fill missing game size reliably.

    The existing extractor remains the source of truth for title, image and
    download servers.  Only when its legacy size matcher returns no value do we
    fetch the same SteamRIP page once more and parse the visible text.
    """
    data = await _fetch_game_data(page_url)
    current_size = str(data.get("size") or "").strip()
    if current_size and current_size != "—":
        return data

    final_url = str(data.get("page_url") or page_url)
    try:
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            response = await client.get(final_url)
            response.raise_for_status()

        size = extract_game_size(response.text)
        if size:
            data["size"] = size
            logger.info("SteamRIP game size found: %s", size)
        else:
            logger.warning("SteamRIP game size was not found for %s", final_url)
    except Exception as exc:
        # Size is useful metadata but should never abort the whole /rip flow.
        logger.warning("SteamRIP size lookup failed for %s: %s", final_url, exc)

    return data
