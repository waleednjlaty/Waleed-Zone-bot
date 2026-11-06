from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.keyboards.admin import requests_keyboard
from app.services.group_service import GroupService
from app.utils.text import app_card


def test_request_keyboard_uses_real_request_ids_and_readable_statuses():
    requests = [
        SimpleNamespace(id=731, status="pending", app_name="CapCut"),
        SimpleNamespace(id=804, status="processing", app_name="Photoshop"),
        SimpleNamespace(id=912, status="completed", app_name="Blender"),
    ]

    keyboard = requests_keyboard(requests, page=2, total_pages=3)
    labels = [row[0].text for row in keyboard.inline_keyboard[:3]]
    callbacks = [row[0].callback_data for row in keyboard.inline_keyboard[:3]]

    assert labels == [
        "🆕 جديد · #731 · CapCut",
        "⏳ قيد المعالجة · #804 · Photoshop",
        "✅ منفّذ · #912 · Blender",
    ]
    assert callbacks == [
        "req:manage:731",
        "req:manage:804",
        "req:manage:912",
    ]


def test_app_card_explains_when_optional_metadata_is_missing():
    app = SimpleNamespace(
        id=1,
        name="Example App",
        version=None,
        size=None,
        platform=None,
        category=None,
        developer=None,
        downloads=0,
        description=None,
    )

    card = app_card(app)

    assert "لم تُضف تفاصيل إضافية لهذا التطبيق بعد" in card


@pytest.mark.asyncio
async def test_group_lock_error_explains_required_bot_permission():
    bot = SimpleNamespace(set_chat_permissions=AsyncMock(side_effect=RuntimeError("forbidden")))
    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100123),
        delete=AsyncMock(),
    )

    result = await GroupService().lock_chat(bot, message)

    assert "البوت مشرف" in result
    assert "صلاحية تغيير أذونات المجموعة" in result
    message.delete.assert_not_awaited()
