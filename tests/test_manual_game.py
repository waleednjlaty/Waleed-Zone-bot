from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import Update
from sqlalchemy import func, select

from app.handlers import manual_game as flow
from app.keyboards.admin import admin_panel_keyboard, apps_management_keyboard
from config import get_settings
from database import repositories as repo
from database.database import Database
from database.models import Application, DeliverySource


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'manual.db'}")
    await database.init_models()
    yield database
    await database.close()


def event(text=None, data=None, user=111):
    message = SimpleNamespace(
        text=text,
        photo=None,
        from_user=SimpleNamespace(id=user),
        answer=AsyncMock(),
        bot=SimpleNamespace(send_photo=AsyncMock(), send_message=AsyncMock()),
    )
    if data:
        return SimpleNamespace(
            data=data,
            from_user=message.from_user,
            message=message,
            bot=message.bot,
            answer=AsyncMock(),
        )
    return message


@pytest.fixture
def state():
    return FSMContext(MemoryStorage(), StorageKey(bot_id=123456, chat_id=111, user_id=111))


async def fill(state):
    await state.set_state(flow.ManualGameStates.confirm)
    await state.update_data(
        name="Manual <Game>",
        description="An owner-written description",
        version="1.2",
        size="5 GB",
        platform="Windows",
        category="ألعاب كمبيوتر",
        download_link="https://devuploads.com/game123",
        image_url=None,
        icon_file_id=None,
    )


def test_manual_button_in_both_admin_lists():
    for kb in (admin_panel_keyboard(), apps_management_keyboard([], 0, 1)):
        assert any(
            "add_manual_game" in (b.callback_data or "") for row in kb.inline_keyboard for b in row
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://devuploads.com/a",
        "https://evil.test/a",
        "https://127.0.0.1/a",
        "https://u:p@devuploads.com/a",
        "https://devuploads.com:443/a",
        "https://devuploads.com/a#key",
        "https://devuploads.com/a\n",
        "https://devuploads.com/a b",
        "https://devuploads.com/" + "a" * 2000,
        "https://devuploads.com.evil.test/a",
        "https://[broken/a",
    ],
)
def test_unsafe_or_unsupported_links_denied(url):
    with pytest.raises(ValueError):
        flow.validate_download_link(url)


def test_custom_host_requires_exact_allowlist(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "LEGACY_DOWNLOAD_ALLOWED_HOSTS", "files.example,devuploads.com"
    )
    assert (
        flow.validate_download_link("https://files.example/game?id=12")
        == "https://files.example/game?id=12"
    )
    with pytest.raises(ValueError):
        flow.validate_download_link("https://sub.files.example/game")


async def test_collect_complete_manual_flow(state):
    await flow.on_start(event(data="start"), state)
    await flow.on_link(event(text="https://devuploads.com/game123"), state)
    for value in ("My Game", "My description", "/skip", "5 GB", "Android"):
        await flow.on_metadata(event(text=value), state)
    await flow.on_category(event(data="manual:mobile"), state)
    message = event(text="/skip")
    await flow.on_image(message, state)
    data = await state.get_data()
    assert data["version"] is None and data["size"] == "5 GB"
    assert data["category"] == "ألعاب موبايل" and data["image_url"] is None
    assert await state.get_state() == flow.ManualGameStates.confirm.state
    assert "My description" in message.answer.call_args.args[0]


async def test_bad_input_does_not_advance(state):
    await state.set_state(flow.ManualGameStates.name)
    await flow.on_metadata(event(text="a" * 256), state)
    assert await state.get_state() == flow.ManualGameStates.name.state
    assert not await state.get_data()


@pytest.mark.parametrize("action,visible", [("site", True), ("draft", False)])
async def test_save_shared_catalog_with_external_link_and_no_file(db, state, action, visible):
    await fill(state)
    call = event(data=f"manual:{action}")
    async with db.session() as session:
        await flow.on_confirm(call, state, session)
        app = (await session.scalars(select(Application))).one()
        assert app.shrankme_url == "https://devuploads.com/game123"
        assert app.devupload_url is None and app.published is visible
        assert app.active and app.size == "5 GB" and app.version == "1.2"
        assert await session.scalar(select(func.count()).select_from(DeliverySource)) == 0
        assert bool(await repo.get_active_application(session, app.id)) is visible
        assert await state.get_state() is None
        call.bot.send_message.assert_not_awaited()


async def test_channel_failure_preserves_website_publication(db, state, monkeypatch):
    await fill(state)
    monkeypatch.setattr(get_settings(), "CHANNEL_ID", -100123)
    call = event(data="manual:channel")
    call.bot.send_message.side_effect = RuntimeError("failed")
    async with db.session() as session:
        await flow.on_confirm(call, state, session)
        app = (await session.scalars(select(Application))).one()
        assert app.published
        call.bot.send_message.assert_awaited_once()
        assert "تعذر نشر" in call.message.answer.call_args.args[0]


async def test_image_failure_keeps_form_retriable(state, monkeypatch):
    await state.set_state(flow.ManualGameStates.image)
    monkeypatch.setattr(flow.ImgBBUploader, "upload_telegram_photo", AsyncMock(return_value=""))
    message = event()
    message.photo = [SimpleNamespace(file_id="photo")]
    await flow.on_image(message, state)
    assert await state.get_state() == flow.ManualGameStates.image.state


async def test_save_failure_rolls_back_and_keeps_form(db, state, monkeypatch):
    await fill(state)
    async with db.session() as session:
        monkeypatch.setattr(session, "commit", AsyncMock(side_effect=RuntimeError("DB failed")))
        await flow.on_confirm(event(data="manual:site"), state, session)
        assert await session.scalar(select(func.count()).select_from(Application)) == 0
        assert await state.get_state() == flow.ManualGameStates.confirm.state


async def test_every_manual_step_denies_non_owner(state):
    for handler, args in [
        (flow.on_start, (event(data="start", user=999), state)),
        (flow.on_link, (event(text="https://devuploads.com/g", user=999), state)),
        (flow.on_metadata, (event(text="Game", user=999), state)),
        (flow.on_category, (event(data="manual:pc", user=999), state)),
        (flow.on_image, (event(text="/skip", user=999), state)),
        (flow.on_confirm, (event(data="manual:site", user=999), state, None)),
        (flow.on_cancel, (event(text="/cancel", user=999), state)),
    ]:
        await handler(*args)
        assert not await state.get_data() and await state.get_state() is None


async def test_dispatcher_repeated_confirmation_creates_only_one_game(db):
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dp.include_router(flow.router)
    bot = Bot("123456:TEST-TOKEN")
    bot.session.make_request = AsyncMock(return_value=True)
    state = dp.fsm.get_context(bot=bot, chat_id=111, user_id=111)
    await fill(state)
    async with db.session() as session:
        for update_id in (1, 2):
            update = Update.model_validate(
                {
                    "update_id": update_id,
                    "callback_query": {
                        "id": str(update_id),
                        "from": {"id": 111, "is_bot": False, "first_name": "Owner"},
                        "chat_instance": "test",
                        "data": "manual:site",
                        "message": {
                            "message_id": 1,
                            "date": 0,
                            "chat": {"id": 111, "type": "private"},
                        },
                    },
                }
            )
            await dp.feed_update(bot, update, session=session)
        assert await session.scalar(select(func.count()).select_from(Application)) == 1
        # Cancellation clears the draft; an old confirmation button cannot save it.
        await fill(state)
        update_data = update.model_dump(mode="json", by_alias=True)
        update_data["update_id"] = 3
        update_data["callback_query"]["id"] = "3"
        update_data["callback_query"]["data"] = "manual:cancel"
        await dp.feed_update(bot, Update.model_validate(update_data), session=session)
        assert await state.get_state() is None and not await state.get_data()
        await dp.feed_update(bot, update, session=session)
        assert await session.scalar(select(func.count()).select_from(Application)) == 1
    await bot.session.close()
