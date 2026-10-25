from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import download_service
from integrations.steamrip_extractor import ProviderResolutionError


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[tuple[str, dict]] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append((text, kwargs))


class FakeCall:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=123456)
        self.message = FakeMessage()
        self.answers: list[tuple[tuple, dict]] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answers.append((args, kwargs))


@pytest.mark.asyncio
async def test_provider_challenge_uses_website_fallback_without_orphan_token(monkeypatch) -> None:
    website_url = "https://waleed-zone.up.railway.app/download/54"
    challenge = ProviderResolutionError(
        "PROVIDER_CHALLENGE",
        "steamrip",
        "https://steamrip.com/example-game",
        403,
    )
    monkeypatch.setattr(
        download_service,
        "resolve_application_download",
        AsyncMock(side_effect=challenge),
    )
    monkeypatch.setattr(
        download_service,
        "website_download_url",
        lambda application_id: website_url if application_id == 54 else None,
    )
    create_pending = AsyncMock(side_effect=AssertionError("challenge must not create a dead-end token"))
    monkeypatch.setattr(download_service.repo, "create_pending_download", create_pending)

    call = FakeCall()
    session = SimpleNamespace(rollback=AsyncMock())

    await download_service.send_application_download(call, session, 54)

    session.rollback.assert_awaited_once()
    create_pending.assert_not_awaited()
    assert len(call.message.answers) == 1
    text, kwargs = call.message.answers[0]
    button = kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.url == website_url
    assert "?token=" not in button.url
    assert "لا يعيد رابط الملف إلى البوت تلقائيًا" in text
