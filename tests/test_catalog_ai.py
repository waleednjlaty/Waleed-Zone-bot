from types import SimpleNamespace

from app.services.catalog_ai import (
    extract_embedded_version,
    heuristic_release_groups,
    root_application_name,
)


def app(app_id: int, name: str, version: str | None = None, platform: str = "Android"):
    return SimpleNamespace(
        id=app_id,
        name=name,
        version=version,
        platform=platform,
        revision=1,
    )


def test_extracts_version_suffix_without_guessing_missing_version():
    assert extract_embedded_version("CapCut 19.8.0") == "19.8.0"
    assert extract_embedded_version("VLC Player") is None
    assert root_application_name("CapCut 19.8.0") == "CapCut"


def test_proposes_embedded_versions_in_numeric_order_and_separates_platforms():
    groups = heuristic_release_groups([
        app(12, "CapCut 19.7.0"),
        app(13, "CapCut 19.8.0"),
        app(14, "CapCut 19.9.0", "19.9.0"),
        app(15, "CapCut 19.8.0", platform="Windows"),
    ])
    assert len(groups) == 1
    assert groups[0]["canonical_name"] == "CapCut"
    assert [item["id"] for item in groups[0]["items"]] == [12, 13, 14]
    assert [item["version_suggestion"] for item in groups[0]["items"]] == ["19.7.0", "19.8.0", None]
    assert all(len(item["revision"]) == 64 for item in groups[0]["items"])


def test_does_not_recommend_records_already_grouped_by_exact_name_and_platform():
    assert heuristic_release_groups([
        app(1, "CapCut", "19.7.0"),
        app(2, "CapCut", "19.8.0"),
    ]) == []


def test_refuses_cross_platform_groups():
    assert heuristic_release_groups([
        app(1, "CapCut 19.7.0", platform="Android"),
        app(2, "CapCut 19.8.0", platform="Windows"),
    ]) == []
