"""تصنيف التطبيقات والألعاب بصورة موحّدة للمصدر وواجهة المستخدم."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

PC_GAME_CATEGORY = "ألعاب كمبيوتر"
MOBILE_GAME_CATEGORY = "ألعاب موبايل"

_GENERIC_GAME_CATEGORIES = {
    "game",
    "games",
    "gaming",
    "ألعاب",
    "العاب",
}

_PC_GAME_CATEGORIES = {
    PC_GAME_CATEGORY.casefold(),
    "العاب كمبيوتر",
    "pc games",
    "computer games",
    "games pc",
}

_MOBILE_GAME_CATEGORIES = {
    MOBILE_GAME_CATEGORY.casefold(),
    "العاب موبايل",
    "mobile games",
    "phone games",
}

_PC_PLATFORMS = {
    "windows",
    "linux",
    "macos",
    "mac os",
    "pc",
}

_MOBILE_PLATFORMS = {
    "android",
    "ios",
    "iphone",
    "ipad",
}


class CatalogApp(Protocol):
    category: str | None
    platform: str | None


def _clean(value: str | None) -> str:
    return (value or "").strip().casefold()


def game_category(category: str | None, platform: str | None) -> str | None:
    """أعد التصنيف الموحد للعبة أو ``None`` إن لم تكن لعبة معروفة.

    يدعم السجلات القديمة التي كانت محفوظة باسم ``Games`` أو ``ألعاب`` ويعتمد
    على النظام لفصلها إلى كمبيوتر أو موبايل، بدون الحاجة لتعديل قاعدة البيانات.
    """

    category_key = _clean(category)
    platform_key = _clean(platform)

    if category_key in _PC_GAME_CATEGORIES:
        return PC_GAME_CATEGORY
    if category_key in _MOBILE_GAME_CATEGORIES:
        return MOBILE_GAME_CATEGORY

    if category_key not in _GENERIC_GAME_CATEGORIES:
        return None

    if platform_key in _MOBILE_PLATFORMS:
        return MOBILE_GAME_CATEGORY
    if platform_key in _PC_PLATFORMS:
        return PC_GAME_CATEGORY

    return None


def display_category(category: str | None, platform: str | None) -> str | None:
    """اسم التصنيف الذي يجب عرضه للمستخدم مع دعم السجلات القديمة."""

    return game_category(category, platform) or ((category or "").strip() or None)


def is_pc_game(app: CatalogApp) -> bool:
    return game_category(app.category, app.platform) == PC_GAME_CATEGORY


def is_mobile_game(app: CatalogApp) -> bool:
    return game_category(app.category, app.platform) == MOBILE_GAME_CATEGORY


def app_matches_category(app: CatalogApp, category: str) -> bool:
    """مطابقة تطبيق لتصنيف الواجهة، بما في ذلك التصنيفين الافتراضيين للألعاب."""

    target = _clean(category)
    if target == PC_GAME_CATEGORY.casefold():
        return is_pc_game(app)
    if target == MOBILE_GAME_CATEGORY.casefold():
        return is_mobile_game(app)

    return _clean(app.category) == target


def visible_categories(apps: Iterable[CatalogApp]) -> list[str]:
    """ابنِ قائمة التصنيفات مع فصل ألعاب الكمبيوتر عن ألعاب الموبايل."""

    categories: dict[str, str] = {}
    has_pc_games = False
    has_mobile_games = False

    for app in apps:
        canonical_game = game_category(app.category, app.platform)
        if canonical_game == PC_GAME_CATEGORY:
            has_pc_games = True
            continue
        if canonical_game == MOBILE_GAME_CATEGORY:
            has_mobile_games = True
            continue

        category = (app.category or "").strip()
        if category:
            categories.setdefault(category.casefold(), category)

    result: list[str] = []
    if has_pc_games:
        result.append(PC_GAME_CATEGORY)
    if has_mobile_games:
        result.append(MOBILE_GAME_CATEGORY)

    result.extend(sorted(categories.values(), key=str.casefold))
    return result
