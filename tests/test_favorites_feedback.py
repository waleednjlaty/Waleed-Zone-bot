from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import applications


def _favorite_callback(action):
    return SimpleNamespace(
        answer=AsyncMock(),
        from_user=SimpleNamespace(id=555001),
        message=SimpleNamespace(edit_reply_markup=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_repeated_add_favorite_reports_existing_state(monkeypatch):
    call = _favorite_callback("fav")
    app = SimpleNamespace(id=42, source_url=None)
    monkeypatch.setattr(applications.repo, "get_active_application", AsyncMock(return_value=app))
    add = AsyncMock(return_value=False)
    monkeypatch.setattr(applications.repo, "add_favorite", add)
    monkeypatch.setattr(applications.repo, "list_application_versions", AsyncMock(return_value=[]))

    await applications.on_toggle_favorite(
        call, SimpleNamespace(action="fav", app_id=42), session=object()
    )

    call.answer.assert_awaited_once_with("ℹ️ التطبيق موجود بالفعل في المفضلة.")
    keyboard = call.message.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[-2][0].text == "💔 إزالة من المفضلة"


@pytest.mark.asyncio
async def test_repeated_remove_favorite_reports_absent_state(monkeypatch):
    call = _favorite_callback("unfav")
    app = SimpleNamespace(id=42, source_url=None)
    monkeypatch.setattr(applications.repo, "get_active_application", AsyncMock(return_value=app))
    remove = AsyncMock(return_value=False)
    monkeypatch.setattr(applications.repo, "remove_favorite", remove)
    monkeypatch.setattr(applications.repo, "list_application_versions", AsyncMock(return_value=[]))

    await applications.on_toggle_favorite(
        call, SimpleNamespace(action="unfav", app_id=42), session=object()
    )

    call.answer.assert_awaited_once_with("ℹ️ التطبيق غير موجود في المفضلة أصلًا.")
    keyboard = call.message.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[-2][0].text == "❤️ إضافة للمفضلة"
