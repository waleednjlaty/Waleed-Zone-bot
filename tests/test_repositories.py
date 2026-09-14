import pytest

from database import repositories as repo


@pytest.mark.asyncio
async def test_user_get_or_create(db):
    async with db.session() as session:
        user = await repo.get_or_create_user(
            session, telegram_id=999001, username="tester", first_name="T"
        )
        assert user.telegram_id == 999001
        assert user.username == "tester"

        # update username
        user2 = await repo.get_or_create_user(
            session, telegram_id=999001, username="tester2", first_name="T"
        )
        assert user2.username == "tester2"


@pytest.mark.asyncio
async def test_application_crud_and_search(db):
    async with db.session() as session:
        image_url = "https://example.com/icon.png"
        app = await repo.create_application(
            session,
            name="MyApp",
            description="Best app",
            version="1.0",
            size="10MB",
            category="Tools",
            platform="Android",
            developer="DevCo",
            image_url=image_url,
            search_text="myapp tools android",
        )
        assert app.id is not None

        got = await repo.get_application(session, app.id)
        assert got.name == "MyApp"
        assert got.image_url == image_url

        apps = await repo.list_applications(session, active_only=True, limit=10)
        assert any(a.id == app.id for a in apps)

        # search
        results = await repo.search_applications(session, "myapp", limit=5)
        assert any(r.id == app.id for r in results)


@pytest.mark.asyncio
async def test_favorites_flow(db):
    async with db.session() as session:
        user = await repo.get_or_create_user(session, telegram_id=555000, username="favuser")
        app = await repo.create_application(session, name="FavApp", search_text="favapp")

        await repo.add_favorite(session, user.telegram_id, app.id)
        is_fav = await repo.is_favorite(session, user.telegram_id, app.id)
        assert is_fav is True

        favs = await repo.list_favorites(session, user.telegram_id, limit=10)
        assert any(a.id == app.id for a in favs)

        await repo.remove_favorite(session, user.telegram_id, app.id)
        is_fav2 = await repo.is_favorite(session, user.telegram_id, app.id)
        assert is_fav2 is False
