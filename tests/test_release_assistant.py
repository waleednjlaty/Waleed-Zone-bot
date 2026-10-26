import asyncio
from types import SimpleNamespace

from app.utils.release_assistant import suggest_application_families


def candidate(app_id, name, version, platform="Android"):
    return SimpleNamespace(id=app_id, name=name, version=version, platform=platform,
                           category="تطبيقات", developer=None)


def test_release_assistant_suggests_matching_family_and_deduplicates_versions(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rows = [candidate(1, "CapCut", "19.7.0"), candidate(2, "Cap-Cut", "19.6.0"),
            candidate(3, "CapCut", "4.2.0", "Windows"), candidate(4, "VLC", "3.0.0")]
    result = asyncio.run(suggest_application_families("cap cut", "19.8.0", "Android", rows))
    assert result["provider"] == "similarity"
    assert result["items"]
    assert result["items"][0]["name"] in {"CapCut", "Cap-Cut"}
    assert all(item["platform"] == "Android" for item in result["items"])
    assert len({item["id"] for item in result["items"]}) == len(result["items"])


def test_release_assistant_returns_no_cross_platform_match(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = asyncio.run(suggest_application_families(
        "CapCut", "19.8.0", "Android", [candidate(3, "CapCut", "19.7.0", "Windows")]
    ))
    assert result["items"] == []
