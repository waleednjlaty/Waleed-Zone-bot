from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from database import repositories as repo


@pytest.mark.asyncio
async def test_application_version_exists_is_scoped_to_app_family_and_platform(db):
    async with db.session() as session:
        original = await repo.create_application(
            session, name="CapCut", version="19.7.0", platform="Android"
        )
        await repo.create_application(
            session, name="CapCut", version="19.8.0", platform="Android"
        )
        await repo.create_application(
            session, name="CapCut", version="19.8.0", platform="Windows"
        )
        await session.commit()
        assert await repo.application_version_exists(
            session, name=original.name, platform="Android", version="19.8.0"
        )
        assert not await repo.application_version_exists(
            session, name=original.name, platform="Android", version="19.9.0"
        )
        assert not await repo.application_version_exists(
            session, name=original.name, platform="Windows", version="19.9.0"
        )


@pytest.mark.asyncio
async def test_application_version_exists_can_exclude_the_current_record(db):
    async with db.session() as session:
        original = await repo.create_application(
            session, name="CapCut", version="19.7.0", platform="Android"
        )
        await session.commit()
        assert not await repo.application_version_exists(
            session, name=original.name, platform="Android", version="19.7.0", exclude_id=original.id
        )



from app.utils.versions import (
    application_family_key,
    latest_per_family,
    release_sort_key,
    sort_application_versions,
)


def app(app_id, name, version, platform="Android", created=1):
    return SimpleNamespace(
        id=app_id, name=name, version=version, platform=platform,
        created_at=datetime.fromtimestamp(created, tz=timezone.utc),
    )


def test_family_identity_normalizes_name_and_separates_platform_tracks():
    assert application_family_key(app(1, "CapCut.apk", "1.2")) == application_family_key(app(2, "cap-cut", "1.3"))
    assert application_family_key(app(3, "CapCut", "1.3", "Android")) != application_family_key(app(4, "CapCut", "1.3", "Windows"))


def test_version_sorting_is_numeric_not_lexical():
    assert release_sort_key(app(2, "CapCut", "1.10")) > release_sort_key(app(1, "CapCut", "1.9"))
    assert [x.version for x in sort_application_versions([app(1, "CapCut", "1.9"), app(2, "CapCut", "1.10"), app(3, "CapCut", "2.0")])] == ["2.0", "1.10", "1.9"]


def test_latest_per_family_collapses_duplicates_but_keeps_os_versions_separate():
    rows = [
        app(1, "CapCut", "1.2", "Android", 3),
        app(2, "CapCut", "1.8", "Android", 1),
        app(3, "VLC", "3.0", "Android", 2),
        app(4, "CapCut", "1.10", "Windows", 4),
    ]
    assert [x.id for x in latest_per_family(rows)] == [2, 3, 4]


def test_stable_version_beats_matching_beta_then_created_time_breaks_ties():
    assert release_sort_key(app(9, "CapCut", "2.0")) > release_sort_key(app(10, "CapCut", "2.0-beta"))
    assert release_sort_key(app(4, "CapCut", "1.2", created=2)) > release_sort_key(app(3, "CapCut", "1.2", created=1))


def test_missing_names_do_not_merge_records():
    assert application_family_key(SimpleNamespace(id=1, name=None, platform=None)) != application_family_key(SimpleNamespace(id=2, name=None, platform=None))
