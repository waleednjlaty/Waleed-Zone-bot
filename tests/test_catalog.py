from types import SimpleNamespace

from app.utils.catalog import (
    MOBILE_GAME_CATEGORY,
    PC_GAME_CATEGORY,
    app_matches_category,
    display_category,
    visible_categories,
)


def _app(category: str | None, platform: str | None):
    return SimpleNamespace(category=category, platform=platform)


def test_legacy_games_are_split_by_platform():
    assert display_category("Games", "Windows") == PC_GAME_CATEGORY
    assert display_category("ألعاب", "Linux") == PC_GAME_CATEGORY
    assert display_category("Games", "Android") == MOBILE_GAME_CATEGORY
    assert display_category("ألعاب", "iOS") == MOBILE_GAME_CATEGORY


def test_explicit_game_categories_match_their_section():
    pc = _app(PC_GAME_CATEGORY, "Windows")
    mobile = _app(MOBILE_GAME_CATEGORY, "Android")

    assert app_matches_category(pc, PC_GAME_CATEGORY)
    assert not app_matches_category(pc, MOBILE_GAME_CATEGORY)
    assert app_matches_category(mobile, MOBILE_GAME_CATEGORY)
    assert not app_matches_category(mobile, PC_GAME_CATEGORY)


def test_visible_categories_hides_legacy_generic_games():
    categories = visible_categories(
        [
            _app("Games", "Windows"),
            _app("ألعاب", "Android"),
            _app("أدوات", "Android"),
        ]
    )

    assert categories == [PC_GAME_CATEGORY, MOBILE_GAME_CATEGORY, "أدوات"]
    assert "Games" not in categories
    assert "ألعاب" not in categories
