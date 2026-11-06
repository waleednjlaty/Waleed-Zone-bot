from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import search


def _message(text):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=12345),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_empty_search_input_explains_text_requirement():
    message = _message(None)
    session = object()
    state = SimpleNamespace(clear=AsyncMock())

    await search.on_search_query(message, session, state)

    message.answer.assert_awaited_once()
    assert "كنص" in message.answer.await_args.args[0]
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_search_results_offer_editing_query_and_clear_state(monkeypatch):
    message = _message("unknown-app")
    session = object()
    state = SimpleNamespace(clear=AsyncMock())
    monkeypatch.setattr(search.repo, "search_applications", AsyncMock(return_value=[]))
    monkeypatch.setattr(search.repo, "log_search", AsyncMock())

    await search.on_search_query(message, session, state)

    state.clear.assert_awaited_once()
    text, = message.answer.await_args.args
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert "تهجئة مختلفة" in text
    assert "جزءًا من الاسم" in text
    assert keyboard.inline_keyboard[0][0].text == "✏️ تعديل عبارة البحث"


@pytest.mark.asyncio
async def test_search_results_explain_how_to_refine_query(monkeypatch):
    message = _message("capcut")
    session = object()
    state = SimpleNamespace(clear=AsyncMock())
    app = SimpleNamespace(id=7, name="CapCut")
    monkeypatch.setattr(search.repo, "search_applications", AsyncMock(return_value=[app]))
    monkeypatch.setattr(search.repo, "log_search", AsyncMock())

    await search.on_search_query(message, session, state)

    state.clear.assert_awaited_once()
    text, = message.answer.await_args.args
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert "يمكنك تعديل عبارة البحث" in text
    assert keyboard.inline_keyboard[-1][0].text == "✏️ تعديل البحث"


@pytest.mark.asyncio
async def test_long_search_query_keeps_search_state():
    message = _message("x" * 81)
    session = object()
    state = SimpleNamespace(clear=AsyncMock())

    await search.on_search_query(message, session, state)

    assert "80 حرفًا" in message.answer.await_args.args[0]
    state.clear.assert_not_awaited()
