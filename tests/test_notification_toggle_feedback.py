from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import start


@pytest.mark.asyncio
async def test_repeated_enable_notifications_reports_already_enabled(monkeypatch):
    call = SimpleNamespace(
        from_user=SimpleNamespace(id=123),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )
    session = object()
    monkeypatch.setattr(
        start.repo, "get_user",
        AsyncMock(return_value=SimpleNamespace(notifications_enabled=True)),
    )
    set_notifications = AsyncMock()
    monkeypatch.setattr(start.repo, "set_user_notifications", set_notifications)

    await start.on_notifications(call, SimpleNamespace(enabled=1), session=session)

    call.answer.assert_awaited_once_with("ℹ️ الإشعارات مفعّلة بالفعل.")
    set_notifications.assert_awaited_once_with(session, 123, True)
    keyboard = call.message.edit_text.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].text == "🔔 تفعيل ✅"


@pytest.mark.asyncio
async def test_repeated_disable_notifications_reports_already_disabled(monkeypatch):
    call = SimpleNamespace(
        from_user=SimpleNamespace(id=456),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )
    monkeypatch.setattr(
        start.repo, "get_user",
        AsyncMock(return_value=SimpleNamespace(notifications_enabled=False)),
    )
    monkeypatch.setattr(start.repo, "set_user_notifications", AsyncMock())

    await start.on_notifications(call, SimpleNamespace(enabled=0), session=object())

    call.answer.assert_awaited_once_with("ℹ️ الإشعارات متوقفة بالفعل.")
    keyboard = call.message.edit_text.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][1].text == "🔕 إيقاف ✅"


@pytest.mark.asyncio
async def test_enable_notifications_reports_state_change(monkeypatch):
    call = SimpleNamespace(
        from_user=SimpleNamespace(id=789),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )
    monkeypatch.setattr(
        start.repo, "get_user",
        AsyncMock(return_value=SimpleNamespace(notifications_enabled=False)),
    )
    monkeypatch.setattr(start.repo, "set_user_notifications", AsyncMock())

    await start.on_notifications(call, SimpleNamespace(enabled=1), session=object())

    call.answer.assert_awaited_once_with("🔔 تم تفعيل الإشعارات")
