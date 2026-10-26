"""Compatibility helpers for grouping catalog rows into version families."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable, TypeVar

T = TypeVar("T")
_VERSION_DIGITS = re.compile(r"\d+")
_EMBEDDED_VERSION = re.compile(r"(?<!\w)v?(\d+(?:\.\d+){1,5}(?:[-+][\w.-]+)?)", re.IGNORECASE)
_FILE_SUFFIX = re.compile(r"\.(apk|xapk|apks|aab|zip|exe|msi|dmg|ipa)$", re.IGNORECASE)
_PRERELEASE = re.compile(r"\b(alpha|beta|rc|preview|pre[- ]?release|dev|nightly)\b|تجريبي", re.IGNORECASE)


def _value(app: object, field: str) -> object:
    if isinstance(app, dict):
        return app.get(field)
    return getattr(app, field, None)


def normalize_application_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = _FILE_SUFFIX.sub("", text)
    text = re.sub(r"^\s*#?\d{1,3}[\s.)_-]+(?=[^\W\d_])", "", text, count=1, flags=re.UNICODE)
    text = re.sub(r"(?:^|[\s_-])v?\d+(?:\.\d+){1,5}(?:[-+][\w.-]+)?(?=$|[\s_-])", " ", text, flags=re.IGNORECASE)
    text = text.replace("_", " ").casefold()
    return "".join(char for char in text if char.isalnum())


def normalize_platform(value: object) -> str:
    platform = normalize_application_name(value)
    if not platform:
        return "unspecified"
    if "android" in platform:
        return "android"
    if "windows" in platform or platform in {"win32", "win64", "pc"}:
        return "windows"
    if platform in {"ios", "iphone", "ipad"} or platform.startswith("ios"):
        return "ios"
    if "macos" in platform or platform == "mac":
        return "macos"
    if "linux" in platform:
        return "linux"
    return platform


def application_family_key(app: object) -> str:
    name = normalize_application_name(_value(app, "name"))
    if not name:
        return "id:" + str(_value(app, "id") or "")
    return name + "::" + normalize_platform(_value(app, "platform"))


def _timestamp(app: object) -> float:
    value = _value(app, "created_at") or _value(app, "createdAt")
    if isinstance(value, datetime):
        try:
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        except (OverflowError, OSError, ValueError):
            return 0.0
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (OverflowError, OSError, ValueError):
            return 0.0
    return 0.0


def release_sort_key(app: object) -> tuple:
    """Comparable key; numeric version beats title-date guesses (1.10 > 1.9)."""
    version = str(_value(app, "version") or "").strip()
    if not version:
        match = _EMBEDDED_VERSION.search(str(_value(app, "name") or ""))
        version = match.group(1) if match else ""
    numeric = [int(part) for part in _VERSION_DIGITS.findall(version)[:12]]
    has_numeric = bool(numeric)
    numeric += [0] * (12 - len(numeric))
    stable = 0 if _PRERELEASE.search(version) else 1
    try:
        app_id = int(_value(app, "id") or 0)
    except (TypeError, ValueError):
        app_id = 0
    return (bool(version), has_numeric, tuple(numeric), stable, _timestamp(app), app_id)


def latest_per_family(apps: Iterable[T]) -> list[T]:
    """Keep the highest release in each family, preserving first family position."""
    items = list(apps)
    winners: dict[str, T] = {}
    for app in items:
        key = application_family_key(app)
        current = winners.get(key)
        if current is None or release_sort_key(app) > release_sort_key(current):
            winners[key] = app
    result: list[T] = []
    seen: set[str] = set()
    for app in items:
        key = application_family_key(app)
        if key in seen:
            continue
        seen.add(key)
        winner = winners.get(key)
        if winner is not None:
            result.append(winner)
    return result


def sort_application_versions(apps: Iterable[T]) -> list[T]:
    return sorted(apps, key=release_sort_key, reverse=True)
