from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import requests
from app.utils.text import request_prompt


def _message(text):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=12345, username="requester"),
        answer=AsyncMock(),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )


def test_request_prompt_explains_text_input_and_cancellation():
    prompt = request_prompt()
    assert "كنص" in prompt
    assert "إلغاء" in prompt
    assert "CapCut Pro" in prompt


@pytest.mark.asyncio
async def test_non_text_request_input_is_explained_and_keeps_state(monkeypatch):
    message = _message(None)
    state = SimpleNamespace(clear=AsyncMock())
    create_request = AsyncMock()
    monkeypatch.setattr(requests.repo, "create_app_request", create_request)

    await requests.on_request_message(message, object(), state)

    assert "كنص" in message.answer.await_args.args[0]
    state.clear.assert_not_awaited()
    create_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_confirmation_includes_request_id_and_status_expectation(monkeypatch):
    message = _message("CapCut Pro")
    state = SimpleNamespace(clear=AsyncMock())
    created = SimpleNamespace(id=314)
    create_request = AsyncMock(return_value=created)
    monkeypatch.setattr(requests.repo, "create_app_request", create_request)
    monkeypatch.setattr(
        requests,
        "get_settings",
        lambda: SimpleNamespace(admin_ids=[]),
    )

    await requests.on_request_message(message, object(), state)

    state.clear.assert_awaited_once()
    confirmation = message.answer.await_args.args[0]
    assert "#314" in confirmation
    assert "إشعارًا عند تحديث حالته" in confirmation
    create_request.assert_awaited_once()
