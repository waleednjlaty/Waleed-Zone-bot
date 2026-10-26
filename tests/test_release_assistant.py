import asyncio
from types import SimpleNamespace

from app.utils.release_assistant import suggest_release_candidates


def app(app_id, name, version, platform, *, active=True):
    return SimpleNamespace(
        id=app_id,
        name=name,
        version=version,
        platform=platform,
        category="Apps",
        developer="Test Studio",
        description="Test catalog app",
        active=active,
        created_at=None,
    )


def test_suggestions_keep_same_app_family_and_same_platform(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rows = [
        app(1, "CapCut", "19.7.0", "Android"),
        app(2, "CapCut", "19.8.0", "Android"),
        app(3, "CapCut", "19.8.0", "Windows"),
        app(4, "DaVinci Resolve", "20.0", "Windows"),
    ]
    provider, matches = asyncio.run(
        suggest_release_candidates(
            rows, name="cap cut", version="19.9.0", platform="Android"
        )
    )
    assert provider == "similarity"
    assert matches
    assert matches[0]["id"] == 2
    assert matches[0]["version"] == "19.8.0"
    assert all(item["platform"] == "Android" for item in matches)


def test_unrelated_app_does_not_match(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rows = [app(10, "DaVinci Resolve", "20.0", "Windows")]
    provider, matches = asyncio.run(
        suggest_release_candidates(
            rows, name="CapCut", version="19.8.0", platform="Android"
        )
    )
    assert provider == "similarity"
    assert matches == []


def test_inactive_rows_are_not_suggested(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rows = [app(11, "CapCut", "19.7.0", "Android", active=False)]
    provider, matches = asyncio.run(
        suggest_release_candidates(
            rows, name="CapCut", version="19.8.0", platform="Android"
        )
    )
    assert provider == "similarity"
    assert matches == []
